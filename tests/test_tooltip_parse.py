import unittest

from src.tooltip_parse import _contains_passable_phrase


class PassableTooltipTests(unittest.TestCase):
    def test_detects_exact_wrapped_sentence(self):
        lines = [
            "The Runic Modifier in this slot will be added",
            "to all Monsters unearthed after this Remnant",
        ]

        self.assertTrue(_contains_passable_phrase(lines))

    def test_tolerates_partial_ocr_sentence(self):
        lines = ["The Runic Modifier in this slot will be added", "after this Remnant"]

        self.assertTrue(_contains_passable_phrase(lines))

    def test_rejects_normal_modifier_text(self):
        lines = ["Rage Rune", "Monsters gain:", "Periodically Enrage"]

        self.assertFalse(_contains_passable_phrase(lines))


if __name__ == "__main__":
    unittest.main()