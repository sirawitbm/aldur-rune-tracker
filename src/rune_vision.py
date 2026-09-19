import colorsys
from dataclasses import dataclass

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
    cursor_x, cursor_y = cursor
    image_width, image_height = image.size
    search_left = max(0, round(cursor_x - icon_size * 0.75))
    search_top = max(0, round(cursor_y - icon_size * 0.85))
    search_right = min(image_width, round(cursor_x + icon_size * 0.75) + 1)
    search_bottom = min(image_height, round(cursor_y - icon_size * 0.2) + 1)
    if search_left >= search_right or search_top >= search_bottom:
        return None

    search = image.convert("RGB").crop((search_left, search_top, search_right, search_bottom))
    width, height = search.size
    pixels = search.load()
    yellow = [False] * (width * height)
    for y in range(height):
        for x in range(width):
            red, green, blue = pixels[x, y]
            hue, saturation, value = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
            yellow[y * width + x] = (
                17 / 180 <= hue <= 38 / 180
                and saturation >= 145 / 255
                and value >= 180 / 255
            )

    components = _connected_components(_morphological_close(yellow, width, height), width, height)
    expected_marker_y = cursor_y - icon_size * 0.5
    best: tuple[float, tuple[int, int, int, int], float] | None = None

    min_area = max(6, round(icon_size * icon_size * 0.002))
    max_area = round(icon_size * icon_size * 0.12)
    for x, y, component_width, component_height, area, center_x, center_y in components:
        x += search_left
        y += search_top
        center_x += search_left
        center_y += search_top
        if not min_area <= area <= max_area:
            continue
        if component_width > icon_size * 0.75 or component_height > icon_size * 0.3:
            continue
        if component_width < 2 or component_height < 1:
            continue
        if abs(center_x - cursor_x) > icon_size * 0.48:
            continue
        if not cursor_y - icon_size * 0.8 <= center_y <= cursor_y - icon_size * 0.25:
            continue
        fill_ratio = area / (component_width * component_height)
        if fill_ratio < 0.15:
            continue

        x_error = abs(center_x - cursor_x) / icon_size
        y_error = abs(center_y - expected_marker_y) / icon_size
        thinness_bonus = min(component_width / max(component_height, 1), 4.0) / 4.0
        score = x_error * 1.4 + y_error - min(fill_ratio, 1.0) * 0.1 - thinness_bonus * 0.08
        confidence = max(0.0, min(1.0, 1.0 - score / 1.5))
        marker_box = (x, y, x + component_width, y + component_height)
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
    if icon_box[0] < 0 or icon_box[1] < 0 or icon_box[2] > image_width or icon_box[3] > image_height:
        return None
    return PassableRuneDetection(marker_box, icon_box, confidence)


def _morphological_close(mask: list[bool], width: int, height: int) -> list[bool]:
    offsets = ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1))
    dilated = [False] * len(mask)
    for y in range(height):
        for x in range(width):
            dilated[y * width + x] = any(
                0 <= x + dx < width
                and 0 <= y + dy < height
                and mask[(y + dy) * width + x + dx]
                for dx, dy in offsets
            )

    closed = [False] * len(mask)
    for y in range(height):
        for x in range(width):
            closed[y * width + x] = all(
                not (0 <= x + dx < width and 0 <= y + dy < height)
                or dilated[(y + dy) * width + x + dx]
                for dx, dy in offsets
            )
    return closed


def _connected_components(
    mask: list[bool],
    width: int,
    height: int,
) -> list[tuple[int, int, int, int, int, float, float]]:
    visited = [False] * len(mask)
    components = []
    for start in range(len(mask)):
        if not mask[start] or visited[start]:
            continue

        stack = [start]
        visited[start] = True
        points = []
        while stack:
            index = stack.pop()
            x, y = index % width, index // width
            points.append((x, y))
            for neighbor_y in range(max(0, y - 1), min(height, y + 2)):
                for neighbor_x in range(max(0, x - 1), min(width, x + 2)):
                    neighbor = neighbor_y * width + neighbor_x
                    if mask[neighbor] and not visited[neighbor]:
                        visited[neighbor] = True
                        stack.append(neighbor)

        min_x = min(x for x, _ in points)
        max_x = max(x for x, _ in points)
        min_y = min(y for _, y in points)
        max_y = max(y for _, y in points)
        area = len(points)
        components.append(
            (
                min_x,
                min_y,
                max_x - min_x + 1,
                max_y - min_y + 1,
                area,
                sum(x for x, _ in points) / area,
                sum(y for _, y in points) / area,
            )
        )
    return components


def crop_detected_icon(image: Image.Image, detection: PassableRuneDetection) -> Image.Image:
    return image.crop(detection.icon_box)