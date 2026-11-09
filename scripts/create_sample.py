"""Create a sample GIF in the server input directory for manual API demos."""

from pathlib import Path

from PIL import Image, ImageDraw


def main():
    """Write an animated GIF so API conversion is easy to demonstrate."""
    folder = Path(__file__).resolve().parent.parent / "data" / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    images = []
    for color in ("#1868cf", "#d35400", "#28a745"):
        frame = Image.new("RGB", (160, 100), color)
        ImageDraw.Draw(frame).ellipse((50, 20, 110, 80), fill="white")
        images.append(frame)
    path = folder / "sample.gif"
    images[0].save(
        path, format="GIF", save_all=True, append_images=images[1:],
        duration=200, loop=0,
    )
    print(f"Created: {path}")


if __name__ == "__main__":
    main()
