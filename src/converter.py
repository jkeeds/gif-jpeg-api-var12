"""Command-line GIF-to-JPEG converter (first GIF frame, white background)."""

import argparse
from pathlib import Path

from PIL import Image, UnidentifiedImageError


JPEG_QUALITY = 90
BACKGROUND_COLOR = (255, 255, 255, 255)


def convert_gif(input_path: Path, output_path: Path) -> Path:
    """Save the first frame of a GIF as a JPEG on a white background."""
    source = Path(input_path)
    target = Path(output_path)
    if not source.is_file():
        raise FileNotFoundError(f"Input GIF does not exist: {source}")
    if source.resolve() == target.resolve():
        raise ValueError("Input and output paths must be different")
    with Image.open(source) as picture:
        if picture.format != "GIF":
            raise ValueError("Input must contain an actual GIF image")
        picture.seek(0)
        rgba = picture.convert("RGBA")
        background = Image.new("RGBA", rgba.size, BACKGROUND_COLOR)
        background.alpha_composite(rgba)
        rgb = background.convert("RGB")
        target.parent.mkdir(parents=True, exist_ok=True)
        rgb.save(target, format="JPEG", quality=JPEG_QUALITY)
    return target


def main(argv=None) -> int:
    """Parse the CLI arguments and execute a conversion."""
    parser = argparse.ArgumentParser(description="Convert GIF to JPEG")
    parser.add_argument("input", type=Path, help="Input .gif file")
    parser.add_argument("output", type=Path, help="Output .jpg file")
    args = parser.parse_args(argv)
    try:
        saved = convert_gif(args.input, args.output)
    except (OSError, ValueError, UnidentifiedImageError) as error:
        parser.exit(1, f"Conversion failed: {error}\n")
    print(f"Saved: {saved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
