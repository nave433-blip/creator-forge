"""Skill: watermark -- stamp a text watermark onto an image.

Usage: forge skills run watermark --text "@herhandle" in.png out.png
       [--position bottom-right] [--opacity 0.5] [--size 36]

Positions: top-left, top-right, bottom-left, bottom-right, center.
Images only (Pillow). For video, burn the watermark in with ffmpeg
yourself -- this skill will not pretend it can do video.
"""

from __future__ import annotations

import argparse

from forge.skills import Skill, SkillError


def _parse(args: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="watermark")
    p.add_argument("--text", required=True, help="Watermark text.")
    p.add_argument("--position", default="bottom-right",
                   choices=["top-left", "top-right", "bottom-left",
                            "bottom-right", "center"])
    p.add_argument("--opacity", type=float, default=0.55)
    p.add_argument("--size", type=int, default=36, help="Font size (px).")
    p.add_argument("input", help="Input image path.")
    p.add_argument("output", help="Output image path.")
    return p.parse_args(args)


def run(args: list[str]) -> str:
    from pathlib import Path

    from PIL import Image, ImageDraw, ImageFont

    ns = _parse(args)
    src = Path(ns.input)
    if not src.is_file():
        raise SkillError(f"Input not found: {src}")

    img = Image.open(src).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", ns.size)
    except OSError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), ns.text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    margin = max(12, ns.size // 2)
    positions = {
        "top-left": (margin, margin),
        "top-right": (img.width - tw - margin, margin),
        "bottom-left": (margin, img.height - th - margin),
        "bottom-right": (img.width - tw - margin, img.height - th - margin),
        "center": ((img.width - tw) // 2, (img.height - th) // 2),
    }
    x, y = positions[ns.position]
    alpha = max(0, min(255, int(255 * ns.opacity)))
    # shadow for readability, then the text
    draw.text((x + 2, y + 2), ns.text, font=font, fill=(0, 0, 0, alpha))
    draw.text((x, y), ns.text, font=font, fill=(255, 255, 255, alpha))

    out = Image.alpha_composite(img, overlay).convert("RGB")
    out_path = Path(ns.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path)
    return f"Watermarked {src.name} -> {out_path} ({ns.position}, '{ns.text}')"


SKILL = Skill(
    name="watermark",
    version="1.0.0",
    description="Stamp a text watermark onto an image (Pillow).",
    usage="forge skills run watermark --text HANDLE in.png out.png [--position bottom-right]",
    run=run,
)
