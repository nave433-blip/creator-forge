"""Tube upload packets: everything she needs to post, in one folder.

For each video x each site, builds:
    packets/tube/<site>/<video-name>/
        title.txt          -- copy-paste title
        description.txt    -- copy-paste description + links + hashtags
        tags.txt           -- comma-separated tags, site limit respected
        checklist.md       -- where to upload + site tips + verification note

Bulk mode does this for a whole folder of videos across many sites and
writes a manifest CSV so she can track what's posted where.
"""

from __future__ import annotations

import csv
from pathlib import Path

from forge.tube.metadata import generate_metadata
from forge.tube.sites import TubeSite, get_site, list_sites


def build_packet(video_path: str, site: TubeSite, out_dir: str | Path,
                 scene: dict | None = None, name: str = "",
                 catalog_tags: list[str] | None = None,
                 custom_tags: list[str] | None = None,
                 links: dict | None = None,
                 extra_description: str = "",
                 template_idx: int = 0) -> Path:
    """Build one upload packet. Returns the packet directory."""
    meta = generate_metadata(site, scene, name, catalog_tags, custom_tags,
                             links, extra_description, template_idx)
    stem = Path(video_path).stem
    dest = Path(out_dir) / "tube" / site.key / stem
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "title.txt").write_text(meta.title, encoding="utf-8")
    (dest / "description.txt").write_text(meta.description, encoding="utf-8")
    (dest / "tags.txt").write_text(", ".join(meta.tags), encoding="utf-8")
    tips = "\n".join(f"- {n}" for n in site.notes) or "- (no special notes)"
    (dest / "checklist.md").write_text(
        f"# Upload checklist: {site.name}\n\n"
        f"Video file: `{video_path}`\n\n"
        f"1. Make sure you're logged into your VERIFIED {site.name} account.\n"
        f"2. Open the upload page: {site.upload_url}\n"
        f"3. Upload the video file above.\n"
        f"4. Paste the title from `title.txt`.\n"
        f"5. Paste the description from `description.txt`.\n"
        f"6. Add the tags from `tags.txt` (max {site.max_tags} on {site.name}).\n"
        f"7. Double-check everything, then publish.\n\n"
        f"## {site.name} tips\n{tips}\n\n"
        f"## Monetization\n{site.monetization or 'See the site partner pages.'}\n",
        encoding="utf-8")
    return dest


def build_bulk(video_paths: list[str], site_keys: list[str],
               out_dir: str | Path, scene: dict | None = None,
               name: str = "", catalog_tags: list[str] | None = None,
               custom_tags: list[str] | None = None,
               links: dict | None = None,
               extra_description: str = "") -> Path:
    """Packets for many videos x many sites + a manifest CSV."""
    sites = [get_site(k) for k in site_keys]
    rows: list[dict] = []
    for i, vp in enumerate(video_paths):
        for site in sites:
            dest = build_packet(
                vp, site, out_dir, scene=scene, name=name,
                catalog_tags=catalog_tags, custom_tags=custom_tags,
                links=links, extra_description=extra_description,
                template_idx=i % 4)
            rows.append({"video": vp, "site": site.name,
                         "packet": str(dest), "status": "ready"})
    manifest = Path(out_dir) / "tube" / "manifest.csv"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["video", "site", "packet", "status"])
        w.writeheader()
        w.writerows(rows)
    return manifest


def site_keys() -> list[str]:
    return [s.key for s in list_sites()]
