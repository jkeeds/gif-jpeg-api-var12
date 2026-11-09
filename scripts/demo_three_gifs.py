"""Generate three GIF examples and prove their conversion to JPEG."""

import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from src.converter import convert_gif


EXAMPLES = (
    ("red", (220, 25, 25), (64, 48)),
    ("blue", (30, 70, 200), (100, 40)),
    ("green", (25, 160, 70), (32, 96)),
)


def main():
    """Generate inputs and check all three JPEG outputs in a temp folder."""
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        for name, color, size in EXAMPLES:
            gif_file = root / f"{name}.gif"
            jpg_file = root / f"{name}.jpg"
            image = Image.new("RGB", size, color)
            ImageDraw.Draw(image).rectangle((3, 3, 12, 12), fill="white")
            image.save(gif_file, format="GIF")
            convert_gif(gif_file, jpg_file)
            with Image.open(jpg_file) as output:
                assert output.format == "JPEG"
                assert output.size == size
            print(f"PASS: {gif_file.name} -> {jpg_file.name}, {size}")


if __name__ == "__main__":
    main()
