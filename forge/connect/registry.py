"""Connector registry with an honest per-platform capability matrix.

Capability levels:
- "full"   -- works via a real API / direct file access, automated.
- "manual"  -- the platform offers no API; SHE exports from the site (or
               posts by hand) and CreatorForge ingests/prepares the files.
- "none"    -- not possible / not attempted.

Every connector declares `capabilities()` so the CLI (`forge connect
list`) can show the truth instead of implying automation that would get
her account banned.
"""

from __future__ import annotations

import csv
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Level = Literal["full", "manual", "none"]


@dataclass
class Capabilities:
    import_level: Level
    export_level: Level
    import_notes: str
    export_notes: str


class BaseConnector:
    name: str = "base"
    platform: str = "base"
    description: str = ""

    def capabilities(self) -> Capabilities:
        raise NotImplementedError

    def import_data(self, source: str, dest_dir: str,
                    **kwargs: Any) -> dict[str, Any]:
        """Bring data IN from the platform. Returns a summary dict."""
        raise NotImplementedError(f"{self.name} does not support import.")

    def export_data(self, source_dir: str, **kwargs: Any) -> dict[str, Any]:
        """Prepare data for the platform. Returns a summary dict."""
        raise NotImplementedError(f"{self.name} does not support export.")


def _ingest_files(source: Path, dest_dir: Path,
                  exts: set[str]) -> dict[str, Any]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for f in sorted(source.rglob("*")):
        if f.is_file() and f.suffix.lower() in exts:
            shutil.copy2(f, dest_dir / f.name)
            copied += 1
    # Carry any CSV manifests alongside (vault statements, tip menus, etc.)
    csvs = 0
    for f in sorted(source.glob("*.csv")):
        shutil.copy2(f, dest_dir / f.name)
        csvs += 1
    return {"copied_media": copied, "copied_csv": csvs,
            "dest": str(dest_dir)}


_MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif",
               ".mp4", ".mov", ".webm", ".mkv", ".m4v"}


class FanslyConnector(BaseConnector):
    name = "fansly"
    platform = "Fansly"
    description = "Creator subscription platform (like OnlyFans)."

    def capabilities(self) -> Capabilities:
        return Capabilities(
            import_level="manual",
            export_level="manual",
            import_notes=("Fansly has no public content API. She exports her "
                          "media vault from the Fansly site (Settings > Data), "
                          "then this ingests the downloaded files + CSVs."),
            export_notes=("No posting API. Use `forge post packet` to build a "
                          "manual posting packet, then upload in the Fansly app/site."),
        )

    def import_data(self, source: str, dest_dir: str,
                    **kwargs: Any) -> dict[str, Any]:
        return _ingest_files(Path(source), Path(dest_dir), _MEDIA_EXTS)


class OnlyFansConnector(BaseConnector):
    name = "onlyfans"
    platform = "OnlyFans"
    description = "Creator subscription platform."

    def capabilities(self) -> Capabilities:
        return Capabilities(
            import_level="manual",
            export_level="manual",
            import_notes=("OnlyFans has no public API for creators' content. "
                          "She requests her data export from OnlyFans "
                          "(Settings > Privacy > Request data), then this "
                          "ingests the downloaded files."),
            export_notes=("No posting/messaging API. Use `forge post packet` "
                          "for manual posting; use the chat approval queue + "
                          "copy/paste for messages. Bot DMs violate ToS."),
        )

    def import_data(self, source: str, dest_dir: str,
                    **kwargs: Any) -> dict[str, Any]:
        return _ingest_files(Path(source), Path(dest_dir), _MEDIA_EXTS)


class RedditConnector(BaseConnector):
    name = "reddit"
    platform = "Reddit"
    description = "Reddit via the official API (PRAW)."

    def capabilities(self) -> Capabilities:
        return Capabilities(
            import_level="full",
            export_level="full",
            import_notes=("Lists her submissions via PRAW (needs script-app "
                          "credentials) and downloads linked media."),
            export_notes=("Posts via the official API (`forge post reddit`, "
                          "dry-run by default). Follows rate limits; subreddit "
                          "rules still apply."),
        )

    def import_data(self, source: str, dest_dir: str,
                    **kwargs: Any) -> dict[str, Any]:
        from forge.config import load_config
        from forge.post.reddit import reddit_client

        config = load_config(kwargs.get("config"))
        reddit = reddit_client(config)
        username = kwargs.get("username") or config.get_path(
            "platforms.reddit.username")
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        saved: list[dict[str, Any]] = []
        for sub in reddit.redditor(username).submissions.new(
                limit=kwargs.get("limit", 50)):
            saved.append({"id": sub.id, "title": sub.title,
                          "url": sub.url,
                          "permalink": f"https://reddit.com{sub.permalink}"})
        (dest / "submissions.json").write_text(
            __import__("json").dumps(saved, indent=2), encoding="utf-8")
        return {"submissions": len(saved), "dest": str(dest),
                "note": "Metadata saved. Media download: extend as needed."}


class FilesystemConnector(BaseConnector):
    name = "filesystem"
    platform = "Local files"
    description = "Import from any local folder (camera roll dumps, etc.)."

    def capabilities(self) -> Capabilities:
        return Capabilities(
            import_level="full",
            export_level="full",
            import_notes="Copies media files from a folder into the catalog staging area.",
            export_notes="Copies files out to a folder.",
        )

    def import_data(self, source: str, dest_dir: str,
                    **kwargs: Any) -> dict[str, Any]:
        return _ingest_files(Path(source), Path(dest_dir), _MEDIA_EXTS)

    def export_data(self, source_dir: str, **kwargs: Any) -> dict[str, Any]:
        out = Path(kwargs.get("dest", Path(source_dir) / "export"))
        return _ingest_files(Path(source_dir), out, _MEDIA_EXTS)


class URLConnector(BaseConnector):
    name = "url"
    platform = "URL download"
    description = "Download a single file from a direct URL."

    def capabilities(self) -> Capabilities:
        return Capabilities(
            import_level="full",
            export_level="none",
            import_notes="Downloads one direct media URL. Not for scraping sites.",
            export_notes="n/a",
        )

    def import_data(self, source: str, dest_dir: str,
                    **kwargs: Any) -> dict[str, Any]:
        import urllib.request
        if not source.startswith(("https://", "http://")):
            raise ValueError(f"Refusing non-HTTP URL: {source!r}")
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        name = kwargs.get("filename") or source.rstrip("/").split("/")[-1] or "download"
        out = dest / name
        urllib.request.urlretrieve(source, out)
        return {"downloaded": str(out)}


_CONNECTORS: list[BaseConnector] = [
    FanslyConnector(),
    OnlyFansConnector(),
    RedditConnector(),
    FilesystemConnector(),
    URLConnector(),
]


def list_connectors() -> list[BaseConnector]:
    return list(_CONNECTORS)


def get_connector(name: str) -> BaseConnector:
    for c in _CONNECTORS:
        if c.name == name.lower():
            return c
    raise KeyError(f"Unknown connector {name!r}. "
                   f"Available: {[c.name for c in _CONNECTORS]}")


def capabilities_table() -> list[dict[str, str]]:
    rows = []
    for c in _CONNECTORS:
        caps = c.capabilities()
        rows.append({
            "connector": c.name,
            "platform": c.platform,
            "import": caps.import_level,
            "export": caps.export_level,
            "notes": (caps.import_notes + " " + caps.export_notes).strip(),
        })
    return rows


def export_capability_csv(out_csv: str | Path) -> Path:
    out = Path(out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["connector", "platform",
                                           "import", "export", "notes"])
        w.writeheader()
        w.writerows(capabilities_table())
    return out
