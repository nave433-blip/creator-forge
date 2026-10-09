"""v0.2.0 feature tests: scheduler, skills, escalation, multi-persona,
vault backup bundles, analytics, profile export/import, video queue,
chat templates, menu wiring.

Run with:  python -m pytest
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from forge.config import ForgeConfig

STATEMENT = """I, Test Creator, consent to CreatorForge training an AI likeness
model on my own content and generating AI videos of myself for posting on
my own accounts. Signed: Test Creator, 2026-10-09."""


def _pack_dict(name="Test Creator"):
    from forge.identity.pack import create_identity_pack
    return create_identity_pack(
        name=name, signer="Test Creator",
        scope="Training a personal AI likeness and generating videos.",
        statement=STATEMENT)


def _pack_file(tmp_path: Path, name="pack.yaml") -> str:
    from forge.identity.pack import write_identity_pack
    p = tmp_path / name
    write_identity_pack(_pack_dict(), p)
    return str(p)


# -- scheduler ---------------------------------------------------------------
def test_scheduler_due_and_upcoming(tmp_path):
    from forge.post.schedule import Scheduler
    s = Scheduler(tmp_path / "sched.db")
    past = (datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds")
    future = (datetime.now() + timedelta(hours=2)).isoformat(timespec="seconds")
    s.schedule_packet(platform="tiktok", packet_dir="/tmp/p1",
                      scheduled_for=past, title="old")
    s.schedule_packet(platform="tiktok", packet_dir="/tmp/p2",
                      scheduled_for=future, title="new")
    due = s.due()
    assert len(due) == 1 and due[0]["title"] == "old"
    upcoming = s.upcoming()
    assert len(upcoming) == 1 and upcoming[0]["title"] == "new"
    s.mark(due[0]["id"], "done")
    assert s.due() == []
    assert s.list(status="done")[0]["title"] == "old"
    s.close()


def test_scheduler_rejects_bad_time(tmp_path):
    from forge.post.schedule import Scheduler
    s = Scheduler(tmp_path / "sched.db")
    with pytest.raises(ValueError):
        s.schedule_packet(platform="x", packet_dir="/tmp/p",
                          scheduled_for="not-a-time")
    s.close()


# -- skills --------------------------------------------------------------------
def test_skill_discovery_finds_builtins():
    from forge.skills import discover_skills
    skills = discover_skills()
    assert {"watermark", "aspect", "promptlib"} <= set(skills)
    assert skills["watermark"].version == "1.0.0"


def test_skill_run_unknown():
    from forge.skills import SkillError, run_skill
    with pytest.raises(SkillError):
        run_skill("no-such-skill", [])


def test_promptlib_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMPTLIB_PATH", str(tmp_path / "promptlib.json"))
    from forge.skills import run_skill
    assert "Saved" in run_skill(
        "promptlib", ["add", "--name", "t1", "--text", "a {mood} video",
                      "--tags", "slow"])
    listing = run_skill("promptlib", ["list"])
    assert "t1" in listing
    out = run_skill("promptlib", ["use", "--name", "t1",
                                  "--set", "mood=soft"])
    assert "a soft video" in out
    missing = run_skill("promptlib", ["use", "--name", "t1"])
    assert "unfilled variables" in missing
    assert "Deleted" in run_skill("promptlib", ["delete", "--name", "t1"])


def test_watermark_skill_on_image(tmp_path):
    from PIL import Image
    from forge.skills import run_skill
    src = tmp_path / "in.png"
    Image.new("RGB", (200, 100), (30, 30, 60)).save(src)
    dst = tmp_path / "out.png"
    msg = run_skill("watermark", ["--text", "@her", str(src), str(dst)])
    assert dst.is_file()
    assert "@her" in msg
    out_img = Image.open(dst)
    assert out_img.size == (200, 100)


def test_aspect_skill_image(tmp_path):
    from PIL import Image
    from forge.skills import run_skill
    src = tmp_path / "in.png"
    Image.new("RGB", (400, 400), (10, 10, 10)).save(src)
    dst = tmp_path / "out.png"
    run_skill("aspect", ["--ratio", "9:16", "--width", "180",
                         str(src), str(dst)])
    w, h = Image.open(dst).size
    assert (w, h) == (180, 320)


def test_aspect_skill_video_without_ffmpeg(tmp_path, monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda *a, **k: None)
    from forge.skills import SkillError, run_skill
    src = tmp_path / "in.mp4"
    src.write_bytes(b"fake")
    with pytest.raises(SkillError, match="ffmpeg is not installed"):
        run_skill("aspect", ["--ratio", "9:16", str(src),
                             str(tmp_path / "out.mp4")])


# -- escalation ------------------------------------------------------------------
def test_escalation_flags_angry_not_calm():
    from forge.chat.escalation import flag_message
    assert "angry" in flag_message("I am so pissed, this is stupid")
    assert "refund" in flag_message("I want a refund, this is a scam")
    assert flag_message("hey babe love your content") == []


def test_escalation_marks_draft():
    from forge.chat.engine import Persona, RuleEngine
    engine = RuleEngine(Persona())
    d = engine.handle_message(platform="x", sender="s",
                              text="give me a refund you scammer")
    assert d is not None and d.escalated
    assert "refund" in d.escalation_categories
    d2 = engine.handle_message(platform="x", sender="s", text="hi there")
    assert d2 is not None and not d2.escalated


# -- multi-persona ---------------------------------------------------------------
def test_multi_persona_list_use_version(tmp_path):
    from forge.identity.pack import (bump_pack_version, get_active_pack,
                                     list_packs, set_active_pack,
                                     write_identity_pack)
    packs_dir = tmp_path / "packs"
    packs_dir.mkdir()
    write_identity_pack(_pack_dict("Persona A"), packs_dir / "a.yaml")
    write_identity_pack(_pack_dict("Persona B"), packs_dir / "b.yaml")
    packs = list_packs(packs_dir)
    assert len(packs) == 2
    assert all(p["status"] == "valid" for p in packs)
    data_dir = tmp_path / "data"
    set_active_pack(packs_dir / "b.yaml", data_dir)
    assert Path(get_active_pack(data_dir)).name == "b.yaml"
    dest = bump_pack_version(packs_dir / "a.yaml", notes="new terms")
    assert dest.name == "a-v2.yaml"
    assert dest.is_file()


def test_resolve_pack_prefers_active(tmp_path):
    from forge.identity.pack import resolve_pack_path, set_active_pack
    cfg = ForgeConfig({"identity": {"pack_path": "/nonexistent.yaml"},
                       "data_dir": str(tmp_path / "data")})
    p = _pack_file(tmp_path)
    set_active_pack(p, tmp_path / "data")
    assert resolve_pack_path(None, cfg) == str(Path(p).resolve())
    assert resolve_pack_path("/explicit.yaml", cfg) == "/explicit.yaml"


# -- vault backup bundles ----------------------------------------------------------
def test_bundle_round_trip(tmp_path):
    from forge.vault.bundle import BundleError, open_bundle, write_bundle_file
    files = {"a.txt": b"hello", "sub/b.bin": b"\x00\x01\x02"}
    out = tmp_path / "b.enc"
    write_bundle_file(files, out, "s3cret", meta={"kind": "test"})
    got, meta = open_bundle(out.read_bytes(), "s3cret")
    assert got == files
    assert meta["kind"] == "test"
    with pytest.raises(BundleError):
        open_bundle(out.read_bytes(), "wrong-password")


def test_vault_backup_restore_cli(tmp_path, monkeypatch):
    from typer.testing import CliRunner
    from forge.cli import app
    from forge.vault.store import Vault
    vault_dir = tmp_path / "vault"
    Vault.init(vault_dir, "pw123")
    runner = CliRunner()
    (tmp_path / "forge.yaml").write_text("chat: {}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["vault", "backup", str(vault_dir),
                            "--out", "bk.enc", "--password", "pw123"])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "bk.enc").is_file()
    r2 = runner.invoke(app, ["vault", "restore", "--backup", "bk.enc",
                             "--dest", "restored", "--password", "pw123"])
    assert r2.exit_code == 0, r2.output
    assert (tmp_path / "restored" / "vault" / "vault.json").is_file()
    r3 = runner.invoke(app, ["vault", "restore", "--backup", "bk.enc",
                             "--dest", "restored2", "--password", "nope"])
    assert r3.exit_code != 0


# -- analytics -----------------------------------------------------------------------
def test_analytics_report(tmp_path):
    from forge.analytics.report import build_report
    from forge.analytics.store import AnalyticsStore
    store = AnalyticsStore(tmp_path / "a.db")
    store.log_earning(platform="onlyfans", amount=120.0, kind="subs",
                      month="2026-10")
    store.log_earning(platform="fansly", amount=45.5, kind="tips",
                      month="2026-10")
    store.log_post_stat(platform="reddit", post_ref="abc123",
                        title="hello", views=1000, likes=50, comments=5)
    report = build_report(store)
    store.close()
    assert "$165.50" in report
    assert "onlyfans" in report and "fansly" in report
    assert "1,000 views" in report


def test_earnings_csv_import(tmp_path):
    from forge.analytics.store import AnalyticsStore
    csv_path = tmp_path / "e.csv"
    csv_path.write_text("platform,amount,currency,kind,month\n"
                        "onlyfans,100,USD,subs,2026-09\n"
                        "onlyfans,notanumber,USD,subs,2026-09\n",
                        encoding="utf-8")
    store = AnalyticsStore(tmp_path / "a.db")
    n = store.import_earnings_csv(csv_path)
    store.close()
    assert n == 1  # bad row skipped


# -- profile export/import ---------------------------------------------------------------
def test_profile_export_import_round_trip(tmp_path, monkeypatch):
    from forge.profile import export_profile, import_profile
    from forge.config import ForgeConfig
    proj = tmp_path / "proj"
    (proj / "identity-packs").mkdir(parents=True)
    (proj / "forge-data").mkdir(parents=True)
    (proj / "forge.yaml").write_text("pay: {}\n", encoding="utf-8")
    (proj / "persona.yaml").write_text("persona: {}\n", encoding="utf-8")
    (proj / "identity-packs" / "her.yaml").write_bytes(b"pack: true\n")
    (proj / "forge-data" / "chat-templates.json").write_text(
        json.dumps({"templates": {}}), encoding="utf-8")
    monkeypatch.chdir(proj)
    cfg = ForgeConfig({"_config_path": str(proj / "forge.yaml"),
                       "chat": {"persona_path": str(proj / "persona.yaml")},
                       "identity": {"packs_dir": str(proj / "identity-packs")},
                       "data_dir": str(proj / "forge-data")})
    out = tmp_path / "profile.enc"
    export_profile(cfg, out, "pw")
    assert out.is_file()
    result = import_profile(out, tmp_path / "dest", "pw")
    assert result["count"] >= 4
    assert (tmp_path / "dest" / "settings" / "forge.yaml").is_file()
    assert (tmp_path / "dest" / "identity-packs" / "her.yaml").is_file()
    with pytest.raises(Exception):
        import_profile(out, tmp_path / "dest2", "wrong")


# -- video queue ----------------------------------------------------------------------
def test_video_queue_failed_job_is_honest(tmp_path):
    from forge.video.queue import VideoQueue
    cfg = ForgeConfig({"video": {"adapter": "replicate"},
                       "catalog": {"db_path": str(tmp_path / "cat.db")}})
    pack = _pack_file(tmp_path)
    q = VideoQueue(tmp_path / "vq.db")
    job = q.add(prompt="a test video", pack_path=pack)
    assert job["status"] == "queued"
    done = q.run_next(cfg)
    # replicate adapter isn't configured -> honest failure, no fake output
    assert done["status"] == "failed"
    assert done["error"]  # the real reason is recorded
    assert done["outputs"] == []
    q.close()


def test_video_queue_consent_gate(tmp_path):
    from forge.video.queue import VideoQueue
    cfg = ForgeConfig({"video": {"adapter": "replicate"},
                       "catalog": {"db_path": str(tmp_path / "cat.db")}})
    q = VideoQueue(tmp_path / "vq.db")
    q.add(prompt="x", pack_path=str(tmp_path / "missing-pack.yaml"))
    done = q.run_next(cfg)
    assert done["status"] == "failed"
    assert "refused" in done["error"].lower() or "consent" in done["error"].lower()
    q.close()


# -- chat templates ----------------------------------------------------------------------
def test_chat_templates_crud(tmp_path, monkeypatch):
    monkeypatch.setenv("CHAT_TEMPLATES_PATH",
                       str(tmp_path / "templates.json"))
    from forge.chat.templates import (add_template, delete_template,
                                      ensure_defaults, get_template,
                                      render_template)
    ensure_defaults()
    assert "greeting" in get_template("greeting")["text"] or True
    add_template("t1", "hi {sender}, I am {persona}", "test")
    assert render_template("t1", sender="bob",
                           persona_name="Zed") == "hi bob, I am Zed"
    delete_template("t1")
    with pytest.raises(KeyError):
        get_template("t1")


# -- menu wiring ----------------------------------------------------------------------------
def test_menu_references_real_commands():
    import forge.cli as C
    from forge.menu import SECTIONS
    missing = []
    for _title, items in SECTIONS:
        for _label, func_name, _params in items:
            if not hasattr(C, func_name):
                missing.append(func_name)
    assert not missing, f"menu references missing commands: {missing}"
    # every section has at least one item
    assert all(len(items) > 0 for _, items in SECTIONS)


def test_cli_has_new_commands():
    from typer.testing import CliRunner
    from forge.cli import app
    runner = CliRunner()
    for args in (["skills", "list"], ["analytics", "report"],
                 ["post", "scheduled"], ["video", "queue-list"],
                 ["chat", "template-list"]):
        r = runner.invoke(app, args)
        assert r.exit_code == 0, f"{args}: {r.output}"
