"""Generate the CreatorForge app icon: a 'CF' monogram.

Rounded-square tile, teal -> violet diagonal gradient, white 'CF'
letters centered, subtle inner highlight. Deterministic output --
re-running produces byte-identical PNGs (except embedded mtime-free
metadata, which we strip).

Run: python3 assets/make_icon.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Brand colors
TEAL = (45, 212, 191)      # #2dd4bf
VIOLET = (124, 92, 255)    # #7c5cff
DEEP = (24, 18, 48)

SIZES = [16, 32, 48, 64, 128, 256, 512]


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int],
          t: float) -> tuple[int, int, int]:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _gradient_tile(size: int) -> Image.Image:
    """Diagonal teal->violet gradient on a rounded-square tile."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    grad = Image.new("RGBA", (size, size))
    px = grad.load()
    assert px is not None
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * size - 2) if size > 1 else 0
            px[x, y] = _lerp(TEAL, VIOLET, t) + (255,)
    # rounded corners mask
    radius = int(size * 0.24)
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    img.paste(grad, (0, 0), mask)
    # subtle inner highlight: soft white arc at the top
    hi = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hi)
    hd.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius,
                         outline=(255, 255, 255, 70), width=max(1, size // 128))
    img = Image.alpha_composite(img, hi)
    return img


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    px = max(8, int(size * 0.44))
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default()


def make_icon(size: int) -> Image.Image:
    tile = _gradient_tile(size)
    draw = ImageDraw.Draw(tile)
    font = _font(size)
    text = "CF"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x, y = (size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]
    # soft shadow, then crisp white letters
    draw.text((x + size * 0.02, y + size * 0.03), text, font=font,
              fill=(20, 10, 40, 110))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    return tile


def make_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#2dd4bf"/>
      <stop offset="1" stop-color="#7c5cff"/>
    </linearGradient>
  </defs>
  <rect x="8" y="8" width="496" height="496" rx="122" fill="url(#g)"/>
  <rect x="8" y="8" width="496" height="496" rx="122" fill="none"
        stroke="#ffffff" stroke-opacity="0.35" stroke-width="6"/>
  <text x="256" y="338" font-family="DejaVu Sans, sans-serif" font-weight="bold"
        font-size="225" fill="#ffffff" text-anchor="middle">CF</text>
</svg>
"""


def main() -> None:
    root = Path(__file__).resolve().parent
    icons = root / "icons"
    icons.mkdir(parents=True, exist_ok=True)
    for size in SIZES:
        img = make_icon(size)
        out = icons / f"icon-{size}.png"
        img.save(out, "PNG")
        print(f"wrote {out} ({img.size})")
    svg_path = root / "icon.svg"
    svg_path.write_text(make_svg(), encoding="utf-8")
    print(f"wrote {svg_path}")


if __name__ == "__main__":
    main()
