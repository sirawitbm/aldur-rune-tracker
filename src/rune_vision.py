from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class PassableRuneDetection:
    marker_box: tuple[int, int, int, int]
    icon_box: tuple[int, int, int, int]
    confidence: float


def detect_passable_rune(
    image: Image.Image,
    cursor: tuple[int, int],
    icon_size: int,
) -> PassableRuneDetection | None:
    """Find the yellow passable marker above the rune under the cursor."""
    rgb = np.asarray(image.convert("RGB"))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    yellow = cv2.inRange(
        hsv,
        np.array((17, 145, 180), dtype=np.uint8),
        np.array((38, 255, 255), dtype=np.uint8),
    )
    yellow = cv2.morphologyEx(
        yellow,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    )

    count, _labels, stats, centroids = cv2.connectedComponentsWithStats(yellow)
    cursor_x, cursor_y = cursor
    expected_marker_y = cursor_y - icon_size * 0.5
    best: tuple[float, tuple[int, int, int, int], float] | None = None

    min_area = max(6, round(icon_size * icon_size * 0.002))
    max_area = round(icon_size * icon_size * 0.12)
    for index in range(1, count):
        x, y, width, height, area = (int(value) for value in stats[index])
        center_x, center_y = centroids[index]
        if not min_area <= area <= max_area:
            continue
        if width > icon_size * 0.75 or height > icon_size * 0.3:
            continue
        if width < 2 or height < 1:
            continue
        if abs(center_x - cursor_x) > icon_size * 0.48:
            continue
        if not cursor_y - icon_size * 0.8 <= center_y <= cursor_y - icon_size * 0.25:
            continue
        fill_ratio = area / (width * height)
        if fill_ratio < 0.15:
            continue

        x_error = abs(center_x - cursor_x) / icon_size
        y_error = abs(center_y - expected_marker_y) / icon_size
        thinness_bonus = min(width / max(height, 1), 4.0) / 4.0
        score = x_error * 1.4 + y_error - min(fill_ratio, 1.0) * 0.1 - thinness_bonus * 0.08
        confidence = max(0.0, min(1.0, 1.0 - score / 1.5))
        marker_box = (x, y, x + width, y + height)
        if best is None or score < best[0]:
            best = (score, marker_box, confidence)

    if best is None:
        return None

    _score, marker_box, confidence = best
    marker_center_x = (marker_box[0] + marker_box[2]) / 2
    marker_center_y = (marker_box[1] + marker_box[3]) / 2
    icon_center_x = round(cursor_x * 0.25 + marker_center_x * 0.75)
    marker_icon_center_y = marker_center_y + icon_size * 0.5
    icon_center_y = round(cursor_y * 0.25 + marker_icon_center_y * 0.75)
    half = icon_size // 2
    icon_box = (
        icon_center_x - half,
        icon_center_y - half,
        icon_center_x - half + icon_size,
        icon_center_y - half + icon_size,
    )
    image_width, image_height = image.size
    if icon_box[0] < 0 or icon_box[1] < 0 or icon_box[2] > image_width or icon_box[3] > image_height:
        return None
    return PassableRuneDetection(marker_box, icon_box, confidence)


def crop_detected_icon(image: Image.Image, detection: PassableRuneDetection) -> Image.Image:
    return image.crop(detection.icon_box)