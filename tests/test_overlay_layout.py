import unittest

from src.overlay import _grid_shape


class OverlayGridTests(unittest.TestCase):
    def test_short_chain_stays_in_one_column(self):
        self.assertEqual(_grid_shape(10, available_height=600, row_height=44), (10, 1))

    def test_long_chain_wraps_before_screen_bottom(self):
        self.assertEqual(_grid_shape(24, available_height=600, row_height=44), (13, 2))

    def test_tiny_available_height_still_places_entries(self):
        self.assertEqual(_grid_shape(3, available_height=10, row_height=44), (1, 3))


if __name__ == "__main__":
    unittest.main()