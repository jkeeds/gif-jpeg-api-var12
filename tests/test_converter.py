"""Unit tests for the standalone converter, separate from API MBT coverage."""

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.converter import convert_gif


class ConverterTests(unittest.TestCase):
    """Check basic GIF-to-JPEG behavior and invalid input handling."""

    def test_gif_converts_to_jpeg(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            original = path / "input.gif"
            target = path / "output.jpg"
            Image.new("RGB", (20, 10), "red").save(original, "GIF")
            convert_gif(original, target)
            with Image.open(target) as picture:
                self.assertEqual(picture.format, "JPEG")
                self.assertEqual(picture.size, (20, 10))

    def test_rejects_non_gif(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            source = path / "fake.gif"
            Image.new("RGB", (10, 10), "blue").save(source, "PNG")
            with self.assertRaises(ValueError):
                convert_gif(source, path / "output.jpg")
