"""Parses a Grand Expedition remnant-rune tooltip via OCR.

There is no fixed database to match against here (unlike a normal item
list, these are dynamically-composed modifier combos) so we just read the
rune's name straight off the tooltip title. The effect-text lines below it
(small, multi-color, "Monsters gain: ...") are too OCR-noisy to be worth
showing, so only the name is kept.

Tooltip layout (from an in-game screenshot), top to bottom:
    Electrocuting Rune                              <- name (kept)
    Monsters gain:                                  <- (ignored)
    Extra Lightning Damage                          <- (ignored)
    ...
    The Runic Modifier in this slot will be added   <- "passable" marker
    to all Monsters unearthed after this Remnant
"""
import re
from dataclasses import dataclass

import winocr
from PIL import Image

from .config import CONFIG

# Distinctive phrase GGG uses on whichever slot carries forward to the next
# Remnant. Matched loosely (both key fragments, case-insensitive) so minor
# OCR noise doesn't break detection.
_PASSABLE_FRAGMENTS = ("unearthed", "remnant")


@dataclass
class ParsedTooltip:
    name: str | None
    is_passable: bool
    raw_lines: list[str]


def _line_y(line: dict) -> float:
    """winocr line dicts don't carry their own bounding_rect - only their
    words do - so use the first word's top y as the line's vertical position."""
    words = line.get("words") or []
    if not words:
        return 0.0
    return words[0]["bounding_rect"]["y"]


def _ocr_lines(image: Image.Image) -> list[str]:
    result = winocr.recognize_pil_sync(image, lang=CONFIG.ocr_lang)
    lines = [line for line in result["lines"] if line["text"].strip()]
    # Windows.Media.Ocr doesn't guarantee lines come back in visual reading
    # order (mixed fonts/colors/icon glyphs in a tooltip can confuse it) -
    # sort top-to-bottom by position so "first line is the name" below is
    # reliable regardless of engine-internal ordering.
    lines.sort(key=_line_y)
    return [line["text"].strip() for line in lines]


def _clean_name(raw: str) -> str:
    """OCR sometimes drops the case of just the first letter (e.g. "power
    Rune" instead of "Power Rune") - title-case fixes that without needing
    a name database to compare against."""
    return raw.title()


def parse_tooltip(image: Image.Image) -> ParsedTooltip:
    lines = _ocr_lines(image)
    if not lines:
        return ParsedTooltip(name=None, is_passable=False, raw_lines=[])

    is_passable = any(
        all(frag in line.lower() for frag in _PASSABLE_FRAGMENTS) for line in lines
    ) or _spans_passable_phrase(lines)

    # Every one of these rune names ends in "Rune" - prefer a line matching
    # that pattern over blindly trusting "topmost line", since a generous
    # capture box (needed because the tooltip can render on either side of
    # the cursor depending on screen-edge proximity) can sweep in unrelated
    # HUD text above the real tooltip (an FPS counter has actually been
    # observed becoming the "name" this way).
    # If nothing ends in "rune" at all, there's no reasonable name
    # candidate on this screen - report no guess (None) rather than
    # falling back to some arbitrary line, since that guess doesn't just
    # get compared and discarded on a miss: a confident resolution
    # downstream can teach it into the OCR alias table (see
    # icon_db.learn_ocr_alias) as a *permanent* lookup for that exact
    # garbage text, which is far worse than one bad capture.
    name_line = next((l for l in lines if l.lower().endswith("rune")), None)
    name = _clean_name(name_line) if name_line else None
    return ParsedTooltip(name=name, is_passable=is_passable, raw_lines=lines)


def _spans_passable_phrase(lines: list[str]) -> bool:
    """The marker sentence wraps across 2 OCR lines - check the joined text too."""
    joined = " ".join(lines).lower()
    joined = re.sub(r"\s+", " ", joined)
    return "unearthed after this remnant" in joined or (
        "runic modifier" in joined and "added" in joined and "remnant" in joined
    )
