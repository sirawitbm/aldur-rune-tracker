import unittest

from PIL import Image, ImageDraw

from src.rune_vision import crop_detected_icon, detect_passable_rune


class PassableRuneDetectionTests(unittest.TestCase):
    def setUp(self):
        self.cursor = (100, 110)
        self.image = Image.new("RGB", (200, 200), (24, 24, 28))

    def draw_marker(self, center_x=100, center_y=80):
        draw = ImageDraw.Draw(self.image)
        draw.rounded_rectangle(
            (center_x - 8, center_y - 2, center_x + 8, center_y + 2),
            radius=2,
            fill=(255, 220, 25),
        )

    def test_detects_marker_above_hovered_rune(self):
        self.draw_marker()

        detection = detect_passable_rune(self.image, self.cursor, 60)

        self.assertIsNotNone(detection)
        self.assertGreater(detection.confidence, 0.8)
        self.assertEqual(crop_detected_icon(self.image, detection).size, (60, 60))

    def test_rejects_capture_without_yellow_marker(self):
        self.assertIsNone(detect_passable_rune(self.image, self.cursor, 60))

    def test_ignores_unrelated_yellow_below_cursor(self):
        draw = ImageDraw.Draw(self.image)
        draw.rectangle((92, 135, 108, 145), fill=(255, 210, 30))

        self.assertIsNone(detect_passable_rune(self.image, self.cursor, 60))

    def test_ignores_unrelated_yellow_far_from_cursor(self):
        self.draw_marker(center_x=25)

        self.assertIsNone(detect_passable_rune(self.image, self.cursor, 60))

    def test_ignores_marker_on_adjacent_rune(self):
        self.draw_marker(center_x=158)

        self.assertIsNone(detect_passable_rune(self.image, self.cursor, 60))

    def test_ignores_large_floating_world_glyph(self):
        draw = ImageDraw.Draw(self.image)
        draw.ellipse((82, 15, 118, 47), outline=(255, 210, 25), width=5)

        self.assertIsNone(detect_passable_rune(self.image, self.cursor, 60))

    def test_ignores_dim_gold_slot_decoration(self):
        draw = ImageDraw.Draw(self.image)
        draw.rectangle((92, 78, 108, 82), fill=(135, 105, 50))

        self.assertIsNone(detect_passable_rune(self.image, self.cursor, 60))


if __name__ == "__main__":
    unittest.main()