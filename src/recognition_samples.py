import json
import time
import uuid
from pathlib import Path

from PIL import Image

from .capture import CaptureResult
from .config import CONFIG
from .rune_vision import PassableRuneDetection


def save_recognition_sample(
    capture: CaptureResult,
    detection: PassableRuneDetection | None,
    *,
    resolved_name: str | None,
    outcome: str,
    parsed_name: str | None = None,
    has_passable_text: bool | None = None,
    raw_ocr_lines: list[str] | None = None,
) -> Path | None:
    if not getattr(CONFIG, "collect_recognition_samples", False):
        return None

    samples_dir = CONFIG.data_dir / "recognition_samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    sample_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    capture_file = f"{sample_id}-capture.png"
    icon_file = f"{sample_id}-icon.png"
    metadata_file = samples_dir / f"{sample_id}.json"

    capture.image.save(samples_dir / capture_file)
    capture.icon.save(samples_dir / icon_file)
    metadata = {
        "schema_version": 2,
        "predicted_name": resolved_name,
        "ocr_name": parsed_name,
        "has_passable_text": has_passable_text,
        "raw_ocr_lines": raw_ocr_lines or [],
        "verified_name": None,
        "verified_marker": None,
        "outcome": outcome,
        "cursor_screen": [capture.cursor_x, capture.cursor_y],
        "capture_box": list(capture.box),
        "capture_file": capture_file,
        "icon_file": icon_file,
        "marker_detected": detection is not None,
        "marker_box": list(detection.marker_box) if detection else None,
        "icon_box": list(detection.icon_box) if detection else None,
        "marker_confidence": detection.confidence if detection else None,
    }
    metadata_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata_file