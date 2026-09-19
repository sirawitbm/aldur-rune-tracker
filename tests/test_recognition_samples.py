import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from src.capture import CaptureResult
from src.recognition_samples import save_recognition_sample


class _SampleConfig:
    collect_recognition_samples = True

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir


class RecognitionSampleTests(unittest.TestCase):
    def test_saves_ocr_and_passability_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            capture = CaptureResult(
                image=Image.new("RGB", (100, 80)),
                icon=Image.new("RGB", (20, 20)),
                cursor_x=50,
                cursor_y=40,
                box=(0, 0, 100, 80),
            )
            with patch("src.recognition_samples.CONFIG", _SampleConfig(data_dir)):
                metadata_path = save_recognition_sample(
                    capture,
                    None,
                    resolved_name="Arcane Rune",
                    outcome="added",
                    parsed_name="Arcane Rune",
                    has_passable_text=True,
                    raw_ocr_lines=["Arcane Rune", "The Runic Modifier will be added"],
                )

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["schema_version"], 2)
            self.assertEqual(metadata["ocr_name"], "Arcane Rune")
            self.assertTrue(metadata["has_passable_text"])
            self.assertEqual(len(metadata["raw_ocr_lines"]), 2)


if __name__ == "__main__":
    unittest.main()