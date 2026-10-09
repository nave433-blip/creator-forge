"""Tests for tube-site uploads (forge/tube/): registry honesty + metadata."""

import pytest

from forge.tube.metadata import (
    build_description,
    build_title,
    generate_metadata,
    suggest_tags,
)
from forge.tube.packets import build_bulk, build_packet
from forge.tube.sites import SITES, get_site


def test_all_sites_are_manual_assist():
    # Honesty invariant: no fake auto-upload, ever.
    assert len(SITES) >= 6
    for s in SITES:
        assert s.upload_mode == "manual", s.key
        assert s.needs_verification is True, s.key


def test_get_site_unknown():
    with pytest.raises(KeyError):
        get_site("nope")


def test_suggest_tags_priority_and_limits():
    tags = suggest_tags(
        scene={"vibe": "sensual lingerie tease", "setting": "bedroom"},
        catalog_tags=["red-lingerie"],
        custom_tags=["my-brand"],
        max_tags=5)
    assert tags[0] == "my-brand"          # custom first
    assert "red-lingerie" in tags          # catalog kept
    assert "lingerie" in tags              # taxonomy matched from scene
    assert len(tags) <= 5
    assert len(set(tags)) == len(tags)     # deduped


def test_title_respects_site_limit():
    site = get_site("xhamster")
    title = build_title(
        {"vibe": "a" * 200, "outfit": "lingerie", "setting": "bedroom"},
        limit=site.title_limit)
    assert len(title) <= site.title_limit
    assert title  # never empty


def test_description_includes_links_and_hashtags():
    desc = build_description(
        {"vibe": "playful tease"},
        links={"CashApp": "https://cash.app/$her"},
        hashtags=["amateur", "tease"])
    assert "https://cash.app/$her" in desc
    assert "#amateur" in desc


def test_generate_metadata_matches_site_limits():
    site = get_site("pornhub")
    meta = generate_metadata(site, {"vibe": "sensual", "setting": "shower"},
                             name="Bella", custom_tags=["solo"])
    assert len(meta.title) <= site.title_limit
    assert len(meta.tags) <= site.max_tags
    assert "solo" in meta.tags


def test_packet_files_created(tmp_path):
    site = get_site("xvideos")
    dest = build_packet("/vids/clip1.mp4", site, tmp_path,
                        scene={"vibe": "playful", "setting": "bedroom"},
                        name="Bella", links={"Tip": "https://x.test/tip"})
    for f in ("title.txt", "description.txt", "tags.txt", "checklist.md"):
        assert (dest / f).is_file(), f
    checklist = (dest / "checklist.md").read_text()
    assert site.upload_url in checklist
    assert "VERIFIED" in checklist


def test_bulk_manifest(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"x")
    (tmp_path / "b.mp4").write_bytes(b"x")
    manifest = build_bulk([str(tmp_path / "a.mp4"), str(tmp_path / "b.mp4")],
                          ["pornhub", "xhamster"], tmp_path / "out")
    assert manifest.is_file()
    rows = manifest.read_text().strip().splitlines()
    assert len(rows) == 1 + 2 * 2  # header + videos x sites
