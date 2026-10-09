"""Skill: aspect -- resize/crop media to a platform aspect ratio.

Usage: forge skills run aspect --ratio 9:16 in.png out.png
       [--fit cover]   # cover = crop to fill | contain = letterbox

Presets:
  9:16  -- TikTok / Reels / Shorts / Snapchat (vertical)
  4:5   -- Instagram portrait feed
  1:1   -- square feed posts
  16:9  -- YouTube / landscape

Images are handled with Pillow. Video needs ffmpeg on PATH; if it is
missing the skill says so plainly instead of faking it.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from forge.skills import Skill, SkillError

PRESETS = {
    "9:16": (9, 16),
    "4:5": (4, 5),
    "1:1": (1, 1),
    "16:9": (16, 9),
}

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv"}


def _parse(args: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="aspect")
    p.add_argument("--ratio", required=True, choices=sorted(PRESETS),
                   help="Target aspect ratio preset.")
    p.add_argument("--fit", default="cover", choices=["cover", "contain"],
                   help="cover=crop to fill (default); contain=letterbox.")
    p.add_argument("--width", type=int, default=1080,
                   help="Output width in px (height derived).")
    p.add_argument("input", help="Input media path.")
    p.add_argument("output", help="Output media path.")
    return p.parse_args(args)


def _resize_image(src: Path, dst: Path, ratio: str, fit: str,
                  width: int) -> str:
    from PIL import Image, ImageOps

    rw, rh = PRESETS[ratio]
    height = round(width * rh / rw)
    img = Image.open(src).convert("RGB")
    if fit == "cover":
        out = ImageOps.fit(img, (width, height), Image.LANCZOS)
    else:
        out = ImageOps.contain(img, (width, height), Image.LANCZOS)
        canvas = Image.new("RGB", (width, height), (0, 0, 0))
        canvas.paste(out, ((width - out.width) // 2,
                           (height - out.height) // 2))
        out = canvas
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst)
    return f"{src.name} -> {dst} at {ratio} ({width}x{height}, fit={fit})"


def _resize_video(src: Path, dst: Path, ratio: str, width: int) -> str:
    if not shutil.which("ffmpeg"):
        raise SkillError(
            "ffmpeg is not installed, so video resizing is unavailable. "
            "Install ffmpeg (https://ffmpeg.org) and retry, or use this "
            "skill on images only.")
    rw, rh = PRESETS[ratio]
    height = round(width * rh / rw)
    # scale to fill then center-crop to the exact ratio
    vf = (f"scale={width}:{height}:force_original_aspect_ratio=increase,"
          f"crop={width}:{height}")
    cmd = ["ffmpeg", "-y", "-i", str(src), "-vf", vf,
           "-c:a", "copy", str(dst)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SkillError(f"ffmpeg failed: {proc.stderr[-500:]}")
    return f"{src.name} -> {dst} at {ratio} ({width}x{height}) via ffmpeg"


def run(args: list[str]) -> str:
    ns = _parse(args)
    src = Path(ns.input)
    if not src.is_file():
        raise SkillError(f"Input not found: {src}")
    dst = Path(ns.output)
    ext = src.suffix.lower()
    if ext in IMAGE_EXTS:
        return _resize_image(src, dst, ns.ratio, ns.fit, ns.width)
    if ext in VIDEO_EXTS:
        return _resize_video(src, dst, ns.ratio, ns.width)
    raise SkillError(
        f"Unsupported file type {ext!r}. Supported images: "
        f"{sorted(IMAGE_EXTS)}; videos: {sorted(VIDEO_EXTS)}.")


SKILL = Skill(
    name="aspect",
    version="1.0.0",
    description="Resize/crop media to platform aspect ratios (9:16, 1:1, 16:9, 4:5).",
    usage="forge skills run aspect --ratio 9:16 in.png out.png",
    run=run,
)
