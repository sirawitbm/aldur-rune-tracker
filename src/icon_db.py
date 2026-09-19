"""The rune database: name, effect text, and icon all come from here -
never from the screen. Screen capture only ever supplies the *input* used
to figure out *which* database entry you're looking at:

1. Image similarity (primary): the captured icon crop is compared by
   appearance against this library. Pre-seeded from poe2db.tw's individual
   rune pages (tools/scrape_remnant_runes.py -> data/rune_icon_seed.json +
   data/seed_icons/) for the 33 known Remnant rune types.
2. OCR (secondary, a lookup key only): if image matching isn't confident,
   OCR's text guess (see tooltip_parse.py) is resolved against this same
   database - first against a small *learned alias* table (see
   learn_ocr_alias), then by fuzzy string match - the OCR text itself is
   never shown or stored, only used to pick which prepared entry it most
   likely refers to.
3. If neither finds a confident answer, the user picks a name once from
   the same prepared list (see name_prompt.py) - never free-typed info.

Passability is per-instance game state, so rune_vision.py detects the
yellow marker above the hovered rune before this identity matcher runs.

Matching is a masked average color difference, not a generic perceptual
hash: the poe2db seed icons are transparent-background PNGs/WebPs, while
a live capture is an opaque screenshot with the *real* in-game background
behind it (a hex slot, other UI, whatever). Comparing them naively -
e.g. hashing both after compositing onto some arbitrary flat backing -
mostly measures background mismatch, not rune identity, since the seed's
synthetic backing looks nothing like the game's actual background. Instead
each seed's own alpha channel is kept as a mask of "which pixels are
actually the icon glyph", and only those pixels are compared against the
corresponding region of the live capture - background pixels (in the
reference) are excluded from the comparison entirely, on both sides.

Each entry keeps a small ROLLING HISTORY of signatures (the seed's,
permanently, plus up to HISTORY_SIZE-1 of its most recent confirmed live
captures) rather than a single one that gets overwritten - matching takes
the best (lowest-diff) score across all of them. This is the "learn over
time" piece: a rune's appearance in practice can be bimodal (e.g. an
active/hovered icon gets a brightness/glow boost the seed render doesn't
have), and a single fixed reference can't represent that, but a small
nearest-neighbor-style set of real examples can. Every successful
identification - whichever path resolved it - both adds to this history
and, if OCR's raw guess differs from the resolved name, teaches
learn_ocr_alias that mapping, so a recurring OCR misreading (e.g. a
decorative glyph before the title consistently garbling it) gets fixed
outright next time instead of needing image matching or the user again.
"""
import difflib
import json
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from .config import CONFIG

SIG_SIZE = 48  # signature grid is SIG_SIZE x SIG_SIZE pixels
ALPHA_MASK_THRESHOLD = 32  # seed pixels less opaque than this are treated as "background", excluded from matching
MATCH_THRESHOLD = 140  # max avg per-pixel |dR|+|dG|+|dB| (0-765) to accept a match.
# Calibrated against the 33 real seed icons composited onto several
# simulated backgrounds + brightness/glow + resize jitter: true matches
# scored up to ~115, wrong matches (including the ~10 visually-similar
# "rare tier" purple icons confused with each other, the worst case found)
# scored 172+. Re-validated after adding per-entry history (below): still
# 0 false positives across the same battery, and the extra exemplars per
# entry only ever tighten best-match scores, never worsen them.
MIN_MASK_PIXELS = 40  # a signature with fewer "icon" pixels than this is too thin to trust (e.g. bad/empty crop)
AMBIGUITY_MARGIN = 25  # if the 2nd-best score is within this of the best, it's a close call - ask instead of guessing
OCR_RESOLVE_CUTOFF = 0.6  # difflib similarity ratio to accept an OCR-text-to-name resolution
HISTORY_SIZE = 6  # signatures kept per entry: the permanent seed one + up to HISTORY_SIZE-1 recent live captures

if getattr(sys, "frozen", False):
    BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    BUNDLE_ROOT = Path(__file__).resolve().parent.parent

SEED_JSON = BUNDLE_ROOT / "data" / "rune_icon_seed.json"


def _display_icon(icon: Image.Image, size: int = 96) -> Image.Image:
    """Composites a (possibly transparent) icon onto a solid dark backing
    purely for DISPLAY in the overlay, so it stays visible regardless of
    what's behind it there. Never used for matching (see module docstring)."""
    icon = icon.convert("RGBA").resize((size, size), Image.LANCZOS)
    backing = Image.new("RGBA", (size, size), (30, 28, 35, 255))
    backing.alpha_composite(icon)
    return backing.convert("RGB")


def _make_signature(icon: Image.Image) -> list[list[int]]:
    """RGBA pixel grid at a fixed small size. For seed icons the alpha
    channel is real transparency (used as the match mask). For live
    captures / user-registered icons there's no real alpha (screenshots
    are opaque) - alpha is just 255 everywhere, which degrades matching
    against THAT signature to "compare every pixel", the best that's
    possible without transparency info - but since the seed's own
    transparent signature is always kept in history too (see HISTORY_SIZE),
    the masked comparison is still available via that one."""
    img = icon.convert("RGBA").resize((SIG_SIZE, SIG_SIZE), Image.LANCZOS)
    return [list(p) for p in img.getdata()]


def _candidate_pixels(icon: Image.Image) -> list[tuple[int, int, int]]:
    img = icon.convert("RGB").resize((SIG_SIZE, SIG_SIZE), Image.LANCZOS)
    return list(img.getdata())


def _masked_avg_diff(candidate: list[tuple[int, int, int]], signature: list[list[int]]) -> float | None:
    """Average per-pixel |dR|+|dG|+|dB| over only the pixels the reference
    signature considers "icon" (alpha >= threshold). None if the signature
    has too few such pixels to give a meaningful comparison."""
    total = 0
    count = 0
    for (cr, cg, cb), (sr, sg, sb, sa) in zip(candidate, signature):
        if sa < ALPHA_MASK_THRESHOLD:
            continue
        total += abs(cr - sr) + abs(cg - sg) + abs(cb - sb)
        count += 1
    if count < MIN_MASK_PIXELS:
        return None
    return total / count


def _best_diff(candidate: list[tuple[int, int, int]], signatures: list[list[list[int]]]) -> float | None:
    """Nearest-neighbor over an entry's whole signature history - the
    closest exemplar wins, so an icon that looks different in two real
    states (e.g. hovered/glowing vs. not) can still match via whichever
    exemplar resembles the current capture, instead of being compared
    against a single reference that can only represent one of them."""
    best = None
    for sig in signatures:
        diff = _masked_avg_diff(candidate, sig)
        if diff is not None and (best is None or diff < best):
            best = diff
    return best


@dataclass
class LibraryEntry:
    name: str
    signatures: list[list[list[int]]]  # history of SIG_SIZE x SIG_SIZE RGBA grids; [0] is the permanent seed one
    icon_file: str  # relative to data_dir - the clean/display icon
    mods: list[str] = field(default_factory=list)  # from the database; [] for user-named unknowns

    def load_icon(self) -> Image.Image:
        return Image.open(CONFIG.data_dir / self.icon_file)


class IconLibrary:
    def __init__(self):
        self.entries: list[LibraryEntry] = []
        self.ocr_aliases: dict[str, str] = {}
        self._load()
        self._load_aliases()
        self._ensure_seeded()

    # -- lookups ----------------------------------------------------------
    def names(self) -> list[str]:
        return sorted(e.name for e in self.entries)

    def find_by_name(self, name: str) -> LibraryEntry | None:
        low = name.lower()
        return next((e for e in self.entries if e.name.lower() == low), None)

    def ranked_matches(self, icon: Image.Image) -> list[tuple[LibraryEntry, float]]:
        """Every entry with a usable score, best (lowest diff) first."""
        candidate = _candidate_pixels(icon)
        scored = []
        for entry in self.entries:
            diff = _best_diff(candidate, entry.signatures)
            if diff is not None:
                scored.append((entry, diff))
        scored.sort(key=lambda pair: pair[1])
        return scored

    def best_match_debug(self, icon: Image.Image) -> tuple[LibraryEntry | None, float | None]:
        """Closest entry and its score regardless of threshold - for
        surfacing *why* a match failed (score too high vs. no signal at
        all) instead of just a flat "unrecognized"."""
        ranked = self.ranked_matches(icon)
        return ranked[0] if ranked else (None, None)

    def find_match(self, icon: Image.Image) -> LibraryEntry | None:
        """Primary identification path: compare the captured icon's
        appearance against the database. Never looks at OCR text. Returns
        None (rather than guessing) if the best match doesn't clear the
        threshold, or if it's ambiguous - see find_close_candidates."""
        ranked = self.ranked_matches(icon)
        if not ranked or ranked[0][1] > MATCH_THRESHOLD:
            return None
        if len(ranked) > 1 and ranked[1][1] - ranked[0][1] <= AMBIGUITY_MARGIN:
            return None  # too close to call - let find_close_candidates handle it
        return ranked[0][0]

    def find_close_candidates(self, icon: Image.Image) -> list[tuple[LibraryEntry, float]] | None:
        """When find_match declines because of a close call, this returns
        the small group of plausible candidates (best match + anything
        within AMBIGUITY_MARGIN of it) to ask the user about directly,
        instead of silently guessing between visually similar icons."""
        ranked = self.ranked_matches(icon)
        if not ranked or ranked[0][1] > MATCH_THRESHOLD:
            return None
        best_score = ranked[0][1]
        close = [pair for pair in ranked if pair[1] - best_score <= AMBIGUITY_MARGIN]
        return close if len(close) > 1 else None

    def resolve_ocr_guess(self, guess: str | None) -> tuple[LibraryEntry | None, bool]:
        """Secondary path: OCR's raw text is only ever used as a lookup key
        against the prepared name list - the resolved database entry (not
        the OCR text) is what gets used/shown/registered.

        Checks the learned-alias table first (see learn_ocr_alias) - a
        recurring OCR misreading that's already been confirmed once
        (against independent evidence, not just OCR itself) is treated as
        exact/confident from then on - then falls back to fuzzy string
        matching for anything not seen before.

        Returns (entry, is_exact). is_exact distinguishes an
        exact/aliased/high-confidence match (independent confirmation of
        identity) from a fuzzy near-miss."""
        if not guess:
            return None, False
        exact = self.find_by_name(guess)
        if exact is not None:
            return exact, True
        aliased_name = self.ocr_aliases.get(guess.strip().lower())
        if aliased_name is not None:
            aliased = self.find_by_name(aliased_name)
            if aliased is not None:
                return aliased, True
        close = difflib.get_close_matches(guess, self.names(), n=1, cutoff=OCR_RESOLVE_CUTOFF)
        return (self.find_by_name(close[0]), False) if close else (None, False)

    def learn_ocr_alias(self, raw_guess: str, resolved_name: str):
        """Called after ANY confident identification (image match, exact
        OCR, disambiguation pick, or manual pick) with whatever OCR
        actually read this same capture as (even if OCR wasn't what
        resolved it). If they differ, remembers "this text really means
        this rune" for an instant, confident lookup next time - most
        valuable for the image-match-primary case, since that's
        independent ground truth unaffected by OCR's own quality, so a
        recurring garbled reading (e.g. a decorative glyph before the
        title consistently confusing OCR) gets fixed outright instead of
        relying on fuzzy matching (or the user) every single time."""
        key = raw_guess.strip().lower()
        if not key or key == resolved_name.strip().lower():
            return
        if self.ocr_aliases.get(key) == resolved_name:
            return
        self.ocr_aliases[key] = resolved_name
        self._save_aliases()

    # -- mutation -----------------------------------------------------------
    def register_capture(self, name: str, live_icon: Image.Image, *, trust_visual: bool) -> LibraryEntry:
        """Records this capture as `name`. `trust_visual` must be True only
        when image matching *itself* already corroborated this identity -
        a bare image-match hit, or a disambiguation pick that was one of
        image matching's own close candidates - and False whenever the
        name came from text alone (an OCR alias/fuzzy guess with no image
        candidate behind it, a "none of these, but OCR guessed X" pick, or
        the last-resort manual list). Only a `trust_visual=True` capture is
        added to `name`'s signature HISTORY (the permanent seed signature
        plus up to HISTORY_SIZE-1 most recent live ones - see module
        docstring); a text-only resolution updates the tracker/alias table
        but never touches image-matching data for this entry.

        This distinction matters: a bare OCR/manual resolution has *no*
        evidence the captured icon actually looks like `name` - that's
        exactly why image matching didn't (or couldn't) confirm it. Adding
        such a capture's icon to `name`'s history anyway was a real,
        reproduced bug: one honest OCR/fuzzy misidentification injects a
        foreign icon into the wrong entry's history, which then makes that
        entry an easier nearest-neighbor "catch-all" for the *next*
        capture too (regardless of what it actually was) - each wrong hit
        adds another unrelated exemplar, snowballing within a handful of
        captures into one entry silently absorbing everything. A capture
        resolved by image matching itself carries no such risk by
        construction: "image match succeeded" already means the icon
        visually resembles this entry, so folding it into history can only
        refine future matching, never poison it.

        The DISPLAY icon (what shows in the overlay) is deliberately never
        touched here - always the clean database asset, never a live
        screenshot crop. An earlier version of this self-corrected the
        display icon when OCR confirmed a name but the stored reference
        looked wrong (a real poe2db data bug: its "Opulent Rune" icon is
        blue, the real in-game one is gold) - removed because the capture
        toast now shows the identified name as text, which already
        confirms identity without needing the icon itself to be visually
        perfect, and swapping in noisy screenshot crops isn't worth it."""
        existing = self.find_by_name(name)
        if existing is None:
            # No history to protect yet either way - this capture IS the
            # only evidence of what `name` looks like so far.
            return self._add(name, live_icon, mods=[])
        if not trust_visual:
            return existing
        existing.signatures.append(_make_signature(live_icon))
        if len(existing.signatures) > HISTORY_SIZE:
            # Keep index 0 (the permanent seed reference, if this entry has
            # one) and the most recent live ones - drop the oldest live one.
            existing.signatures = [existing.signatures[0]] + existing.signatures[-(HISTORY_SIZE - 1):]
        self._save()
        return existing

    def _save_display_icon(self, source_icon: Image.Image) -> str:
        icons_dir = CONFIG.data_dir / "icon_library"
        icons_dir.mkdir(parents=True, exist_ok=True)
        icon_filename = f"icon_library/{uuid.uuid4().hex}.png"
        _display_icon(source_icon).save(CONFIG.data_dir / icon_filename)
        return icon_filename

    def _add(self, name: str, source_icon: Image.Image, mods: list[str]) -> LibraryEntry:
        entry = LibraryEntry(
            name=name,
            signatures=[_make_signature(source_icon)],
            icon_file=self._save_display_icon(source_icon),
            mods=mods,
        )
        self.entries.append(entry)
        self._save()
        return entry

    def _ensure_seeded(self):
        if not SEED_JSON.exists():
            return
        try:
            seed_data = json.loads(SEED_JSON.read_text(encoding="utf-8"))
        except Exception:
            return

        known_names = {e.name.lower() for e in self.entries}
        added_any = False
        for item in seed_data:
            if item["name"].lower() in known_names:
                continue
            seed_icon_path = BUNDLE_ROOT / "data" / item["icon_file"]
            if not seed_icon_path.exists():
                continue
            try:
                icon = Image.open(seed_icon_path)
                self._add(item["name"], icon, mods=item.get("mods", []))
                added_any = True
            except Exception:
                continue
        if added_any:
            self._save()

    # -- persistence ------------------------------------------------------
    def _path(self) -> Path:
        return CONFIG.data_dir / "icon_library.json"

    def _aliases_path(self) -> Path:
        return CONFIG.data_dir / "ocr_aliases.json"

    def _load(self):
        p = self._path()
        if not p.exists():
            return
        expected_len = SIG_SIZE * SIG_SIZE
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            self.entries = [e for e in (self._entry_from_json(raw, expected_len) for raw in data) if e is not None]
        except Exception:
            pass

    @staticmethod
    def _entry_from_json(e: dict, expected_len: int) -> "LibraryEntry | None":
        # New format: "signatures" (a history list). Old format (from before
        # per-entry history was added): a single "signature" - migrated into
        # a length-1 history rather than dropped, to keep existing users'
        # learned data. Either way, anything with the wrong pixel-grid size
        # (e.g. after a SIG_SIZE bump) is dropped rather than compared
        # against mismatched-length candidates, which would corrupt
        # matching instead of just erroring - a dropped seed-derived entry
        # gets transparently re-added by _ensure_seeded() right after.
        if "signatures" in e:
            sigs = [s for s in e["signatures"] if len(s) == expected_len]
        elif "signature" in e and len(e["signature"]) == expected_len:
            sigs = [e["signature"]]
        else:
            sigs = []
        if not sigs:
            return None
        return LibraryEntry(name=e["name"], signatures=sigs, icon_file=e["icon_file"], mods=e.get("mods", []))

    def _save(self):
        data = [
            {"name": e.name, "signatures": e.signatures, "icon_file": e.icon_file, "mods": e.mods}
            for e in self.entries
        ]
        self._path().write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load_aliases(self):
        p = self._aliases_path()
        if not p.exists():
            return
        try:
            self.ocr_aliases = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass

    def _save_aliases(self):
        self._aliases_path().write_text(json.dumps(self.ocr_aliases, indent=2), encoding="utf-8")


ICON_LIBRARY = IconLibrary()
