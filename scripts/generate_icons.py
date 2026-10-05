"""Render the Stockwise vector app mark into platform icon formats."""

from pathlib import Path
import io
import re
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "assets" / "icons"
SVG = ICON_DIR / "stockwise.svg"


def render(size: int) -> Image.Image:
    # Rasterize the simple vector mark using Pillow primitives at high resolution.
    scale = size / 256
    image = Image.new("RGBA", (size, size))
    draw = ImageDraw.Draw(image)

    def point(x: float, y: float) -> tuple[int, int]:
        return round(x * scale), round(y * scale)

    for y in range(size):
        blend = y / max(1, size - 1)
        left = (15 * (1 - blend) + 11 * blend, 118 * (1 - blend) + 18 * blend, 110 * (1 - blend) + 32 * blend)
        for x in range(size):
            image.putpixel((x, y), (*map(round, left), 255))
    draw = ImageDraw.Draw(image)
    mask = Image.new("L", (size, size))
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=round(58 * scale), fill=255)
    image.putalpha(mask)
    draw.line([point(49, 184), point(207, 184)], fill="#5eead4", width=max(1, round(11 * scale)))
    for x, y, w, h in [(65, 137, 29, 37), (109, 97, 29, 77), (153, 117, 29, 57)]:
        draw.rounded_rectangle((round(x*scale), round(y*scale), round((x+w)*scale), round((y+h)*scale)), radius=max(1, round(3*scale)), outline="#ecfeff", width=max(1, round(13*scale)))
    draw.line([point(64, 102), point(104, 74), point(138, 89), point(187, 46)], fill="#fbbf24", width=max(1, round(12*scale)), joint="curve")
    draw.line([point(171, 45), point(189, 45), point(189, 63)], fill="#fbbf24", width=max(1, round(12*scale)), joint="curve")
    return image


def main() -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    # Preserve the vector as the source of truth and rasterize its matching geometry.
    ET.parse(SVG)
    image = render(1024)
    image.save(ICON_DIR / "stockwise.png", optimize=True)
    image.save(ICON_DIR / "stockwise.ico", format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    image.save(ICON_DIR / "stockwise.icns", format="ICNS")
    print(f"Generated Windows, macOS, and Linux icons in {ICON_DIR}")


if __name__ == "__main__":
    main()
