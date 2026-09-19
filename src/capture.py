from dataclasses import dataclass

from PIL import Image, ImageGrab
from pynput.mouse import Controller as MouseController

from .config import CONFIG

_mouse = MouseController()


@dataclass
class CaptureResult:
    image: Image.Image        # full region, for OCR
    icon: Image.Image         # small crop centered on the cursor, for display
    cursor_x: int
    cursor_y: int
    box: tuple[int, int, int, int]


def capture_around_cursor() -> CaptureResult:
    cx, cy = _mouse.position
    box_cx = cx + CONFIG.capture_offset_x
    box_cy = cy + CONFIG.capture_offset_y

    half_w = CONFIG.capture_width // 2
    half_h = CONFIG.capture_height // 2
    box = (box_cx - half_w, box_cy - half_h, box_cx + half_w, box_cy + half_h)

    image = ImageGrab.grab(bbox=box, all_screens=True)

    # Cursor sits on the icon when hovering it (that's what triggers the
    # tooltip), so crop a small square directly at the cursor's position
    # within this same grab - no separate lookup/database needed.
    icon_half = CONFIG.icon_crop_size // 2
    cursor_in_image = (cx - box[0], cy - box[1])
    icon_box = (
        cursor_in_image[0] - icon_half,
        cursor_in_image[1] - icon_half,
        cursor_in_image[0] + icon_half,
        cursor_in_image[1] + icon_half,
    )
    icon = image.crop(icon_box)

    return CaptureResult(image=image, icon=icon, cursor_x=cx, cursor_y=cy, box=box)
