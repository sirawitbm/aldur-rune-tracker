"""Ad-hoc accuracy benchmark (not part of the app - run directly with
python). Re-validates the masked-diff matcher against every real seed icon
across a battery of synthetic backgrounds/brightness/size-jitter, the same
kind of variation real field captures showed (different UI backgrounds
behind the tooltip, screen brightness/hover glow, slight capture-box
misalignment). Run after any change to icon_db.py's matching or schema."""
import itertools
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageEnhance

from src.icon_db import ICON_LIBRARY, MATCH_THRESHOLD

random.seed(42)

BACKGROUNDS = [(30, 28, 35), (60, 55, 50), (10, 40, 60), (90, 70, 40)]
BRIGHTNESSES = [0.85, 1.0, 1.2]
JITTER_PX = [0, 3]


def make_variant(icon: Image.Image, background, brightness, jitter):
    icon_rgba = icon.convert("RGBA")
    w, h = icon_rgba.size
    bg = Image.new("RGB", (w + jitter, h + jitter), background)
    bg.paste(icon_rgba, (jitter // 2, jitter // 2), icon_rgba)
    return ImageEnhance.Brightness(bg).enhance(brightness)


total = 0
correct = 0
failures = []

for entry in ICON_LIBRARY.entries:
    seed_icon = entry.load_icon()
    for background, brightness, jitter in itertools.product(BACKGROUNDS, BRIGHTNESSES, JITTER_PX):
        total += 1
        capture = make_variant(seed_icon, background, brightness, jitter)
        match = ICON_LIBRARY.find_match(capture)
        if match is not None and match.name == entry.name:
            correct += 1
        else:
            ranked = ICON_LIBRARY.ranked_matches(capture)
            top = ranked[0] if ranked else None
            failures.append((entry.name, background, brightness, jitter, top[0].name if top else None, top[1] if top else None))

print(f"{correct}/{total} correct")
if failures:
    print(f"\n{len(failures)} failures:")
    for name, bg, br, jit, got, score in failures[:40]:
        print(f"  {name} (bg={bg}, brightness={br}, jitter={jit}) -> got {got!r} score={score}")
