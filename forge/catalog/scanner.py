"""Content catalog: scan a folder of media into a deduplicated SQLite catalog.

Each file gets a row with its sha256 hash (dedupes re-uploads/copies),
mime type, image dimensions (via Pillow), and free-form tags. Video
duration is a placeholder (``None``) unless ffprobe/ffmpeg is available on
the PATH, in which case we try to read it.
"""

from __future__ import annotations

import hashlib
import mimetypes
import shutil
import subprocess
from pathlib import Path

from PIL import Image

from forge.catalog.store import CatalogStore

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi"}


def sha256_of(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def image_dimensions(path: Path) -> tuple[int, int] | tuple[None, None]:
    try:
        with Image.open(path) as im:
            return im.width, im.height
    except Exception:
        return None, None


def video_duration(path: Path) -> float | None:
    """Best-effort duration in seconds via ffprobe; None if unavailable."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=15,
        )
        return float(out.stdout.strip()) if out.stdout.strip() else None
    except Exception:
        return None


def scan_one_file(
    path: str | Path,
    store: CatalogStore,
    *,
    tags: list[str] | None = None,
    notes: str = "",
) -> int | None:
    """Insert a single media file into ``store`` (dedupes by hash).

    Returns the new item id, or ``None`` if the file is a duplicate or
    an unsupported type.
    """
    path = Path(path)
    if not path.is_file():
        return None
    suffix = path.suffix.lower()
    kind: str | None = None
    if suffix in IMAGE_EXTS:
        kind = "image"
    elif suffix in VIDEO_EXTS:
        kind = "video"
    if kind is None:
        return None
    digest = sha256_of(path)
    if store.find_by_hash(digest):
        return None
    mime, _ = mimetypes.guess_type(path.name)
    width = height = None
    duration = None
    if kind == "image":
        width, height = image_dimensions(path)
    else:
        duration = video_duration(path)
    return store.add_item(
        path=str(path.resolve()),
        sha256=digest,
        kind=kind,
        mime=mime or "application/octet-stream",
        width=width,
        height=height,
        duration=duration,
        tags=tags or [],
        notes=notes,
    )


def scan_directory(
    root: str | Path,
    store: CatalogStore,
    *,
    tags: list[str] | None = None,
    recursive: bool = True,
) -> dict[str, int]:
    """Scan ``root`` for media and insert rows into ``store``.

    Returns ``{"scanned": N, "added": M, "skipped_duplicates": K,
    "skipped_unsupported": J}``.
    """
    root = Path(root)
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")
    pattern = "**/*" if recursive else "*"
    scanned = added = dups = unsupported = 0
    for path in sorted(root.glob(pattern)):
        if not path.is_file() or path.name.startswith("."):
            continue
        suffix = path.suffix.lower()
        kind: str | None = None
        if suffix in IMAGE_EXTS:
            kind = "image"
        elif suffix in VIDEO_EXTS:
            kind = "video"
        if kind is None:
            unsupported += 1
            continue
        scanned += 1
        digest = sha256_of(path)
        if store.find_by_hash(digest):
            dups += 1
            continue
        mime, _ = mimetypes.guess_type(path.name)
        width = height = None
        duration = None
        if kind == "image":
            width, height = image_dimensions(path)
        else:
            duration = video_duration(path)
        store.add_item(
            path=str(path.resolve()),
            sha256=digest,
            kind=kind,
            mime=mime or "application/octet-stream",
            width=width,
            height=height,
            duration=duration,
            tags=tags or [],
        )
        added += 1
    return {
        "scanned": scanned,
        "added": added,
        "skipped_duplicates": dups,
        "skipped_unsupported": unsupported,
    }
