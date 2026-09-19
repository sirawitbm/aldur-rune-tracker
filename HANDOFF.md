# Technical Handoff — PoE2 Grand Expedition Rune Tracker

Written for another AI agent picking this up cold. No prior context assumed
beyond what's in this doc and the repo itself. Goal: you should be able to
form an independent opinion on the identification/accuracy design, spot
gaps I might be blind to, and suggest next steps — not just rubber-stamp
what's here.

## 1. What this app is

A Windows overlay for Path of Exile 2's "Grand Expedition" content. In that
content, during a setup phase, you walk to a sequence of "Remnants." Each
Remnant offers a small set of "Aldur Rune" choices (e.g. "Electrocuting
Rune," "Soul Rune" — flavor-wise these buff the monsters you'll fight,
which is the point of the mode). Exactly one slot at each Remnant is
marked **passable**: picking it means its effect carries forward and stacks
onto every subsequent Remnant in the chain. By the last Remnant in a
10-Remnant run you can be juggling 9+ stacked modifiers with **no in-game
UI to review what you already picked**. Picking the wrong (non-passable)
slot at any point means that step's modifier doesn't carry forward — worth
knowing immediately, not discovering three Remnants later.

This app is a passive tracking/verification layer for that: hover a
Remnant slot, press a hotkey, it records what you picked and tells you
whether it was actually the passable one. **It never recommends or
optimizes anything** — that's an explicit, repeated user requirement, not
an oversight. If you're evaluating this and thinking "couldn't it suggest
the best combo" — no, that's out of scope by design.

This is a from-scratch build (no PoE1 tooling reused, despite a couple of
comments elsewhere referencing "carried over from PoE1 tooling" for one
unrelated heuristic — that's just describing where the *idea* for that one
heuristic came from, not shared code).

## 2. The core design constraint — read this first

This is the single most load-bearing decision in the codebase, stated
directly by the user, and it shapes almost every other choice:

> "we will not rely on screen capture for any information except input...
> never use input as an output — always use prepared image/information."

Concretely: **the screenshot captured at hotkey-press is only ever used to
figure out *which* database entry applies.** The name, icon, and effect
text that actually get shown/stored/displayed always come from a
pre-built, curated database (scraped once from poe2db.tw — see §4), never
directly from OCR text or raw screenshot pixels. This was violated once by
accident (see §7, "display icon self-correction") and the user caught it
and had it removed immediately — treat this constraint as non-negotiable,
not a style preference.

**The one explicit, deliberate exception**: whether a specific capture was
in the "passable" slot is per-instance game state (which slot you're
looking at *right now*), not a property of "Soul Rune" as a database
concept — it genuinely cannot come from any prepared database, so it's the
one thing read fresh from the tooltip text every time (`tooltip_parse.py`,
`_PASSABLE_FRAGMENTS`/`_spans_passable_phrase`).

## 3. Identification pipeline (main.py::identify)

Runs in strict priority order, and — this is important — **never silently
guesses**. Every path either resolves confidently or explicitly asks / gives
up and returns `None` (capture skipped, nothing recorded).

1. **Image similarity (primary).** `IconLibrary.find_match()` in
   `src/icon_db.py`. The icon crop at the cursor is compared by appearance
   against every entry's signature history (§5). Declines (returns `None`)
   rather than picking if the best score doesn't clear `MATCH_THRESHOLD`,
   or if the top two candidates are within `AMBIGUITY_MARGIN` of each
   other (a close call, handled at step 3, not guessed here).
2. **OCR as a lookup key (secondary).** `IconLibrary.resolve_ocr_guess()`.
   OCR (Windows' built-in `winocr`, chosen to avoid bundling an external
   Tesseract binary) reads the tooltip text, but **that raw text is never
   shown or stored** — it's purely a key into the same name database:
   checked against a learned-alias table first (§6), then exact string
   match, then `difflib` fuzzy match (cutoff `OCR_RESOLVE_CUTOFF = 0.6`).
   An alias hit or exact match is treated as confident (`is_exact=True`)
   and can settle an image-match ambiguity outright without asking.
3. **One-click disambiguation.** If step 1 found a close call between 2+
   visually similar icons and step 2 didn't resolve it outright, a small
   dialog (`DisambiguationDialog`) shows those candidates as icon+name
   buttons. If step 2 found a *fuzzy* (non-exact) guess not already among
   the image candidates, it's folded in as an extra button labeled "OCR
   guess" — a decent signal on its own, just not confident enough to
   auto-accept over an image ambiguity. Explicitly clicking none of the
   options is a deliberate "none of these are right," and does **not**
   silently fall back to using the fuzzy OCR guess anyway (this exact bug
   existed once — see §7).
4. **Manual pick (last resort).** A dialog lists all known names (from the
   same database, not free-typed) plus a debug string showing exactly why
   steps 1–3 failed (`closest icon match: 'X' (score N, needs <=140)` and
   `OCR saw: [...]`), so a bad capture can be diagnosed by reading the
   popup instead of exchanging screenshots with the user.

Whichever step resolves it, the result feeds back into two learning
mechanisms (§5, §6) before being recorded via `TRACKER.add()`.

## 4. The rune database (data/rune_icon_seed.json)

33 verified Remnant rune types, scraped once from individual poe2db.tw
pages (`tools/scrape_remnant_runes.py`) and checked into the repo as
read-only seed data (`data/rune_icon_seed.json` + `data/seed_icons/*.webp`).

Two non-obvious scraping details, in case this needs re-running (e.g. GGG
adds new rune types):
- **poe2db's `og:title` meta tag can be an internal/legacy codename** —
  e.g. the page slug `Gasp_Rune` has `og:title` "Gasp Rune" but the actual
  in-game display name is "Volcanic Rune." The **first `{...}` segment of
  `og:description`** is the authoritative display name; the scraper always
  trusts that, never `og:title`.
- One icon (`Volcanic Rune`) needed a manual URL override
  (`ICON_URL_OVERRIDES` in the scraper) because even the fallback icon
  lookup didn't resolve correctly for that specific page.
- A 34th icon on poe2db's own "Runeshape Combinations" legend, "Bait
  Rune," is **deliberately excluded** — it shares "Power Rune"'s icon
  verbatim on poe2db and the user confirmed in-game it's "a kind of
  gimmick/meme thing," not a real distinct rune players encounter.

If poe2db's data is ever wrong in a way that matters (one confirmed case:
its "Opulent Rune" icon renders blue, the real in-game one is gold), the
mitigation is **not** to fix the seed icon by swapping in a live screenshot
(that was tried and reverted — see §7) — it'd need a manual fix to the seed
asset/data itself, or just living with it since the capture toast already
shows the resolved name as text.

## 5. Image matching: masked diff + per-entry history (the recent work)

### The comparison itself

Not a generic perceptual hash (avoided `imagehash`/numpy/etc. specifically
to keep the PyInstaller bundle small and dependency-light). Custom masked
average color diff in `src/icon_db.py`:

- Both the seed icon and the live capture are resized to a fixed
  `SIG_SIZE x SIG_SIZE` (48x48) grid.
- The seed icon is a transparent PNG/WebP; the live capture is always an
  **opaque** screenshot with the real game background behind the rune
  glyph. Comparing them naively (e.g. hashing both after compositing onto
  some synthetic flat backing) mostly measures *background* mismatch, not
  rune identity — this was the actual root cause of a near-total matching
  failure in early field testing (2/90 correct), not a flaw in the
  diffing math itself.
- Fix: each **reference** signature's own alpha channel is used as a mask.
  Only pixels where the reference's alpha ≥ `ALPHA_MASK_THRESHOLD` (32)
  are compared at all; the average is `|dR|+|dG|+|dB|` over just those
  pixels (`_masked_avg_diff`). A signature with fewer than
  `MIN_MASK_PIXELS` (40) qualifying pixels is treated as unusable (too
  thin a crop / bad reference) — `_masked_avg_diff` returns `None` rather
  than a misleadingly-computed score in that case.
- `MATCH_THRESHOLD = 140` (out of a 0–765 possible range for
  |dR|+|dG|+|dB|), calibrated so real matches score up to ~115 and the
  worst cross-confusion among visually similar icons scores 172+ — see
  the calibration data below.

### Per-entry signature HISTORY (this session's change)

**Before**: each `LibraryEntry` had exactly one `signature`, and every
confirmed capture **overwrote** it (`existing.signature = new_signature`).

**Problem this caused**: a rune's real in-game appearance isn't one fixed
image — a hovered/active icon can get a brightness/glow boost the poe2db
seed render doesn't have, and different Remnant locations plausibly put
different backgrounds/lighting behind it. A single overwritable reference
can only represent one appearance state at a time. Confirming a
bright/glowing capture would silently degrade matching for the normal
state afterward (or vice versa) — there was no way for the reference to
represent "this rune, in either of the ways it can actually look."

**Change**: `LibraryEntry.signature` → `LibraryEntry.signatures: list[...]`
— a bounded history. Index 0 is the seed reference (from poe2db), kept
permanently. Confirmed live captures are **appended**, and the list is
capped at `HISTORY_SIZE = 6` total, FIFO-evicting the oldest *live* entry
(never the seed one) once full. Matching now takes the **minimum** diff
across an entry's whole history (`_best_diff`, nearest-neighbor style) —
whichever historical exemplar is closest to the current capture wins.

This is deliberately framed as **online/incremental learning via a
growing per-class exemplar set**, not literal reinforcement learning (no
reward signal, no policy, no sequential decision-making here) — that
framing was floated by the user but doesn't actually fit the problem; this
is closer to k-NN with a growing, capped reference set per class.

**Validation done this session** (all in `tools/accuracy_benchmark.py` and
ad-hoc scripts, not committed as a formal test suite — see §9 open
question about that):
- Full re-run of the synthetic accuracy battery: all 33 real seed icons ×
  4 background colors × 3 brightness levels × 2 resize-jitter offsets =
  **792/792 correct**, no regression from the schema change.
- Direct test of the multi-modal hypothesis: a synthetic "glow" capture
  (brightness 2.4x, warm background) that the seed signature *alone*
  cannot match (score 159.6, over the 140 threshold) becomes matchable
  after being registered once — and the original normal-brightness
  capture continues to match correctly afterward too. This is the
  concrete, reproducible case the whole feature is justified by.
- FIFO cap behavior verified (stays at `HISTORY_SIZE`, seed entry at index
  0 never evicted).
- Old (pre-history) single-`signature` JSON format is migrated into a
  length-1 history on load rather than dropped, so existing users don't
  lose already-learned corrections when this ships.

**Cost**: worst-case per-`identify()` call is now up to 33 entries × 6
signatures × 2304 pixels ≈ 456K masked-pixel comparisons, pure Python. Not
benchmarked for wall-clock latency this session — see §9.

## 6. Learned OCR aliases (this session's change, complementary)

New: `data/ocr_aliases.json`, a flat `{garbled_text_lowercased:
resolved_name}` map, persisted separately from the icon library.

Motivation: a real field case showed OCR consistently misreading a
tooltip as `"~ Otime Rune"` for what was actually "Time Rune" (a
decorative glyph before the title apparently confusing the OCR engine).
Previously this had to be re-resolved via fuzzy matching (cutoff 0.6) or
the disambiguation dialog every single time it happened.

`IconLibrary.learn_ocr_alias(raw_guess, resolved_name)` is called from
`main.py::identify()`'s `finish()` helper on **every** successful
resolution path — including the bare image-match win, which is the most
valuable case, since that's independent ground truth unaffected by OCR
quality at all. If the raw OCR text differs from the resolved name, the
mapping is recorded. `resolve_ocr_guess()` checks this alias table first
(before exact/fuzzy string matching) and treats an alias hit as
confident/exact — so a recurring misreading gets fixed outright after the
*first* time it's correctly resolved by any means, not just OCR.

Not yet validated against real recurring OCR noise from an actual PoE2
client (only the mechanism itself is unit-tested with synthetic inputs) —
see §9.

## 7. Bugs found and fixed (chronological, for context on why things look the way they do)

1. **Wrong game mechanic entirely**, initially. First build targeted
   generic socketable equipment "Runes," not Grand Expedition Aldur
   Runes. Caught by the user via screenshot; fully rebuilt against the
   correct mechanic and poe2db pages.
2. **poe2db `og:title` vs `og:description` mismatch** — see §4.
3. **Missing runes in seed data** — initially found 30 of the real 33;
   cross-checked multiple rune pages' sidebars to find the missing
   "Rage Rune" (slug quirk: icon alt says `RemnantRuneEnrage`, real page
   slug is `/Rage_Rune`, not `/Enrage_Rune`) and "Toxic Rune."
4. **Image matching failed almost completely in real field testing**
   (2/90 correct) — root cause was the background-compositing mismatch
   described in §5, not a threshold or algorithm bug per se. Fixed by
   introducing the alpha-mask approach.
5. **`MATCH_THRESHOLD` badly miscalibrated** (originally 40) — self-match
   diffs in clean synthetic tests alone were already 46–72. Recalibrated
   twice (→110, then →140 after the SIG_SIZE bump below).
6. **Purple "rare tier" icons too visually similar at low resolution** —
   at `SIG_SIZE=24`, the 10 purple-and-glow icons (Soul, Death, Power,
   Sky, Oath, Bond, Ward, Time, Life, Earth — same outer style, differing
   only in an inner swirl) confused each other with only ~2-point safety
   margin against real-world noise. Fixed by bumping `SIG_SIZE` to 48 and
   `MATCH_THRESHOLD` to 140, widening the margin to ~57.
7. **Capture region direction was backwards.** Originally assumed the
   PoE2 tooltip always renders *below* the cursor with a fixed offset.
   Real screenshots showed it renders *above*, and separately that PoE2
   seems to reposition the tooltip depending on proximity to a screen
   edge (user: "if i move to the left and let remnant be at the very
   right it can't recognize but if im centered it work"). Fixed by making
   the OCR capture region large (900×700) and centered (offset 0,0)
   rather than chasing a moving target with a directional offset.
8. **OCR picked up HUD noise ("118 FPS") as the rune name** once the
   capture box above got bigger. Fixed in `tooltip_parse.py` by preferring
   a line that ends in the word "rune" over blindly trusting the
   topmost-positioned OCR line.
9. **"Display icon self-correction" regression** — added to work around
   the poe2db "Opulent Rune is blue but should be gold" data error, this
   feature replaced the *displayed* icon with a live screenshot crop when
   OCR confirmed identity but the stored reference "looked wrong." It
   ended up triggering on essentially every normal successful capture,
   degrading clean database icons into noisy raw screenshots for the
   common case. The user caught this immediately ("why is we using input
   capture as the result shown again?") and, once told about the new
   capture-toast text confirmation, said the whole color-correction
   mechanism was no longer needed at all. **Fully removed** — the display
   icon is now permanently fixed to the seed/original asset, full stop.
   This is directly why §2's constraint is phrased so absolutely — this
   is the concrete incident that constraint is protecting against.
10. **Disambiguation-rejection silently fell through to a wrong guess.**
    `if close_candidates: <show dialog>` was followed unconditionally by
    a second `if ocr_entry is not None: return ...` — after the user
    explicitly rejected the dialog (none of the shown options were
    right), execution fell into that second `if` anyway and silently used
    the fuzzy OCR guess. Fixed by making it `if/elif` — mutually
    exclusive with having shown the dialog at all.
11. **Good fuzzy OCR guesses were fully discarded when disambiguation
    also triggered for an unrelated reason** — a case where OCR correctly
    fuzzy-resolved to "Time Rune" (0.857 similarity) but the
    disambiguation dialog (triggered by an unrelated image-match
    ambiguity between two *other* icons) didn't offer it as an option,
    forcing an unnecessary fall-through to the full 33-name manual list.
    Fixed by folding a fuzzy (non-exact) OCR guess into the
    disambiguation options as an extra "OCR guess" button when it isn't
    already one of the image candidates.
12. **Signature-history snowball — every capture after the first
    resolved to the same wrong rune.** Found immediately after shipping
    the per-entry history feature above, from the packaged exe's actual
    `data/icon_library.json`/`ocr_aliases.json` after one real play
    session: the *first* capture ("Rebirth Rune") was correct, but every
    one of the next 7 — all different actual runes — also resolved as
    "Rebirth Rune," and its signature history had grown to the
    `HISTORY_SIZE` cap (6) while every other entry still had exactly 1.
    Root cause: `register_capture` appended *any* resolved capture's icon
    into that entry's signature history, regardless of which
    identification path resolved it. One honest OCR/fuzzy
    misidentification (there's no way to fully prevent an occasional one
    — that's inherent to reading noisy game text) injected a foreign
    icon into the wrong entry's history; because matching is
    nearest-neighbor (minimum diff across the whole history), that entry
    then became an *easier* catch-all match for the *next* capture too —
    regardless of what it actually was — which added another unrelated
    exemplar, compounding within a handful of presses. The alias table
    ended up with 10 distinct garbled-OCR-text entries all pointing at
    "Rebirth Rune" as a downstream symptom of this, not the trigger: each
    wrongly-image-matched capture still had `learn_ocr_alias` called on
    it with whatever OCR happened to read that time.

    Fixed by adding a `trust_visual` flag to `register_capture` /
    `identify()`'s `finish()` helper: an entry's signature history is now
    only ever grown by a capture that image matching *itself* already
    corroborated (a bare image-match hit, or a disambiguation pick that
    was one of image matching's own close candidates) — never by a
    resolution that came from OCR alone (alias hit, fuzzy guess, the
    disambiguation dialog's bolted-on "OCR guess" button) or a manual
    pick, since none of those carry any evidence the captured icon
    actually *looks like* that entry. This was exactly open question #4
    from an earlier draft of this doc ("history could learn a wrong
    exemplar") — turned out to be not just possible but the single most
    severe bug found in the whole project, reproducing within ~2
    captures in the field. Verified with a reproduction test: repeatedly
    forcing `trust_visual=False` registrations of 5 different real
    runes' icons onto one entry no longer grows its history at all, and
    all 5 of those runes continue to self-match correctly by image
    afterward. Full accuracy benchmark re-run clean (792/792) after the
    fix. The corrupted `icon_library.json`/`ocr_aliases.json` from the
    field session can't be repaired in place (the damage is baked into
    the signature data) — the fix ships with a rebuilt exe, and existing
    installs need those two (gitignored, auto-regenerating) files
    deleted once to clear the poisoned state.
13. **Capture sometimes returned the previous rune's identity.** Traced
    to PoE2 having a short hover-render delay before the tooltip actually
    updates to a newly-hovered target — capturing instantly on keypress
    could grab the *previous* tooltip still rendered. Fixed with
    `capture_delay_ms` (default 150ms) + `QTimer.singleShot` (must be a
    Qt timer, not `time.sleep`, since the latter would freeze the whole
    event loop including the overlay).

## 8. Non-negotiable UX decisions (so you don't "fix" these)

- **Never recommends anything.** Pure passive tracking. Do not add
  "optimal combo" suggestions even if it seems like an obvious win.
- **Reset on new map, not on hideout visits** — players commonly return
  to hideout mid-Expedition-run to stash/restock, and that must not wipe
  the in-progress tracked chain. Detected via `LogWatcher` tailing
  `Client.txt` with an "is this a hideout vs. a freshly generated map"
  heuristic (the map-detection heuristic itself is unverified against a
  real client — see §9).
- **Overlay is click-through by default** during normal play, unlockable
  via the control panel to drag/discard entries — a click-through window
  fundamentally cannot receive mouse events, hence the cursor-position
  polling hack for hover tooltips (`HoverInfoPopup`) instead of native Qt
  hover events.
- **Newest capture appends at the bottom** of the list (top-to-bottom =
  first-to-last pick order) — this was flipped once at explicit request.
- **Default hotkeys are `Ctrl+3` / `Ctrl+4`** (record/undo) — chosen
  specifically *because* they're unlikely to double as flask/skill keys
  during normal play; went through two earlier iterations (F9/F8, then
  plain 3/4) before landing here, both changed at explicit user request.
- **No PyInstaller `--onefile`, uses `--onedir`.** Ships as a folder, not
  a single exe — `config.json` and `data/` live next to the exe (not
  inside the PyInstaller bundle) specifically so user data survives
  rebuilds/updates.

## 9. Open questions / things worth a second opinion on

These are the things I'd most want pushback or ideas on:

1. **Signature-history cost at scale.** `HISTORY_SIZE=6` was picked
   somewhat arbitrarily (balancing JSON file size against match
   robustness) — not load-tested for actual per-capture latency in the
   packaged exe, only correctness-tested in a plain Python REPL. Worth
   profiling a real `identify()` call end-to-end (33 entries × up to 6
   signatures × 2304-pixel masked comparisons, pure Python, no numpy) to
   confirm it stays comfortably under, say, 100ms — if not, an easy win
   would be vectorizing `_masked_avg_diff` with `numpy` (previously
   avoided purely to keep the PyInstaller bundle small; might be worth
   revisiting that tradeoff now).
2. **No automated regression test suite** — everything in §5/§6/§7 was
   validated via ad-hoc `python -c "..."` scripts during the session, not
   committed as `pytest`/`unittest` files. `tools/accuracy_benchmark.py`
   is the one persisted, re-runnable check. Is it worth setting up a real
   test suite given the project's now-nontrivial bug history (12 distinct
   fixed bugs, several of them logic regressions in the identification
   pipeline specifically)?
3. **Alias table has no eviction/decay.** `ocr_aliases.json` grows
   unboundedly and never expires an entry. Probably fine at this scale
   (at most a few dozen distinct garbled readings across 33 rune names
   realistically), but worth a sanity check — is there a failure mode
   where a *wrong* alias gets learned once (e.g. from a bad manual pick)
   and then permanently poisons future resolutions for that OCR pattern?
   There's currently no way to un-learn an alias short of deleting the
   whole file.
4. ~~**History could, in principle, learn a wrong exemplar.**~~ **Found
   and fixed this session — see bug §7 item 12.** This was worse than
   "in principle": it reproduced in the very first real play session and
   snowballed within ~2 captures (one bare text-only resolution → every
   subsequent capture, regardless of actual rune, misidentified as the
   same wrong entry). Fixed via a `trust_visual` gate: an entry's
   signature history now only grows from captures image matching itself
   corroborated. Residual, smaller-blast-radius version of the same risk
   still exists though, worth a second opinion on: a *bare image-match
   hit* (`trust_visual=True`, step 1) is trusted unconditionally, with no
   cross-check against, say, `AMBIGUITY_MARGIN` beyond what `find_match`
   already applies. Could a single unlucky borderline-but-not-quite-
   ambiguous image match (score just under `MATCH_THRESHOLD`, just
   outside `AMBIGUITY_MARGIN` of the runner-up) still start a *slower*
   version of the same drift, just gated by needing several such
   borderline hits in a row instead of one text-only one? The blast
   radius is much smaller now (a wrong image match must itself already
   look plausible, by construction, so any contamination it adds is at
   least visually similar to begin with) but it's not structurally
   impossible.
5. **Still entirely unvalidated against a real, live PoE2 client** — all
   792 accuracy-benchmark cases are synthetic (real seed icons composited
   onto synthetic backgrounds/brightness/jitter in Pillow), not actual
   game screenshots. The field-testing history in §7 (items 4, 7, 8, 12)
   all came from real usage and none of them were things the synthetic
   benchmark would have caught in advance. Recommend treating any
   synthetic-benchmark number as a floor, not a real-world accuracy
   estimate.
6. **"Likely map" reset-detection heuristic** (`Generating level ...` log
   line in `Client.txt`) is carried over conceptually from prior PoE1
   tooling experience but has never been checked against an actual PoE2
   `Client.txt`. Low risk since there's always a manual reset button as a
   fallback, but worth flagging.
7. **Is nearest-neighbor-over-history the right long-term shape at all**,
   versus something like an incrementally-updated mean+variance per
   entry, or clustering multiple modes explicitly (e.g. detect "this is
   probably the hover-glow state" as a first-class flag rather than an
   implicit second exemplar)? Nearest-neighbor was chosen for simplicity
   and directly matching the user's own framing ("keep history of
   snapshots"), not because it was rigorously compared against
   alternatives.

## 10. Project layout reference

```
main.py                       entry point; identify() pipeline + Qt app wiring
build.ps1                     PyInstaller build script -> dist/PoE2RuneTracker/
config.json                   all tunables (editable directly, or via Settings dialog)
data/rune_icon_seed.json      checked-in seed data (name/mods/icon) for all 33 known runes
data/seed_icons/*.webp        checked-in seed icons, scraped from poe2db.tw
data/icon_library.json        LIVE, self-growing icon library incl. signature history (auto-created, gitignored)
data/icon_library/*.png       clean display icons backing the live library (auto-created, gitignored)
data/ocr_aliases.json         learned "garbled OCR text -> resolved name" map (auto-created, gitignored)
data/session.json             current run state (auto-created, gitignored)
data/history.jsonl            completed runs, one JSON object per line (auto-created, gitignored)
data/captured_icons/*.png     per-entry icon copies shown in the overlay (auto-created, gitignored)
data/positions.json           remembered overlay window positions (auto-created, gitignored)
tools/scrape_remnant_runes.py one-off scraper -> data/rune_icon_seed.json + seed_icons/
tools/accuracy_benchmark.py   synthetic image-matching accuracy test (re-run after any matching change)
src/capture.py                cursor-centered screenshot grab + icon crop
src/tooltip_parse.py          OCR -> name-guess (a DB lookup key, never shown) + passable-flag
src/icon_db.py                the self-growing icon library: appearance matching + display assets
src/name_prompt.py            NamePromptDialog (last resort, full list) + DisambiguationDialog (close call)
src/log_watcher.py            Client.txt tail + area-type classification, live-restartable
src/hotkeys.py                global hotkey listener, live-rebuildable
src/hotkey_capture.py         "press a key" widget -> pynput hotkey string
src/settings_dialog.py        live settings dialog (hotkey, log path, capture region, icon size)
src/tray.py                   system tray icon + right-click menu
src/tracker_state.py          in-memory run state + persistence
src/overlay.py                the five PySide6 windows (list, control panel, hover popup, capture toast, map popup)
src/winutil.py                click-through / no-activate win32 window styles
src/positions.py              drag-to-move position persistence
```

See `README.md` for full user-facing documentation (all config options,
setup, how each identification step works day-to-day). This document is
meant to complement it with the *why* and the *what to double-check*, not
duplicate it.
