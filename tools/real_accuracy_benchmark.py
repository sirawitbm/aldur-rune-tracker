import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

from src.config import CONFIG
from src.icon_db import ICON_LIBRARY
from src.tooltip_parse import parse_tooltip


def ratio(correct: int, total: int) -> str:
    return f"{correct}/{total} ({correct / total:.1%})" if total else "no verified samples"


sample_dir = CONFIG.data_dir / "recognition_samples"
sample_files = sorted(sample_dir.glob("*.json")) if sample_dir.exists() else []
marker_true_positive = 0
marker_true_negative = 0
marker_positive = 0
marker_negative = 0
identity_correct = 0
identity_total = 0
top1_correct = 0

for metadata_path in sample_files:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("exclude_from_calibration"):
        continue
    verified_passable = metadata.get("verified_passable", metadata.get("verified_marker"))
    if verified_passable is None:
        continue
    capture = Image.open(sample_dir / metadata["capture_file"])
    passable_detected = parse_tooltip(capture).has_passable_text

    if verified_passable:
        marker_positive += 1
        marker_true_positive += passable_detected
    else:
        marker_negative += 1
        marker_true_negative += not passable_detected

    verified_name = metadata.get("verified_name")
    if not verified_passable or not verified_name:
        continue
    identity_total += 1
    icon = Image.open(sample_dir / metadata["icon_file"])
    accepted = ICON_LIBRARY.find_match(icon)
    identity_correct += accepted is not None and accepted.name == verified_name
    ranked = ICON_LIBRARY.ranked_matches(icon)
    top1_correct += bool(ranked and ranked[0][0].name == verified_name)

print(f"Verified samples: {marker_positive + marker_negative}")
print(f"Passability recall:    {ratio(marker_true_positive, marker_positive)}")
print(f"Passability specificity: {ratio(marker_true_negative, marker_negative)}")
print(f"Identity accepted accuracy: {ratio(identity_correct, identity_total)}")
print(f"Identity top-1 accuracy:     {ratio(top1_correct, identity_total)}")