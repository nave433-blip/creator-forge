"""Tests for the competitor-gap + spicy-stream integration batch.

Covers: CRM LTV calc, mass-DM packet builder, PPV trigger, welcome-flow
sequencing, compliance checker, stream platform matrix honesty, AFK
session start/stop errors, vault labels + sent log, humanizer, ideas.
"""

from __future__ import annotations

import json

import pytest


# -- CRM ---------------------------------------------------------------------
def test_crm_spend_and_buyer_intent(tmp_path):
    from forge.crm.store import FanCRM
    crm = FanCRM(tmp_path / "crm.db")
    try:
        crm.record_spend("onlyfans", "bigspender", 250.0)
        crm.record_message("onlyfans", "bigspender")
        fan = crm.get_fan("onlyfans", "bigspender")
        assert fan["total_spend"] == 250.0
        assert fan["purchase_count"] == 1
        assert fan["status"] == "active"  # new -> active on first purchase
        score = crm.buyer_intent("onlyfans", "bigspender")
        assert score["score"] >= 55  # high spend + recent purchase
        assert "rules-based" in score["method"]
        assert score["reasons"], "reasons must be shown"
        # unknown fan -> zero, not a crash
        assert crm.buyer_intent("onlyfans", "nobody")["score"] == 0
    finally:
        crm.close()


def test_crm_smart_lists_and_tags(tmp_path):
    from forge.crm.store import FanCRM
    crm = FanCRM(tmp_path / "crm.db")
    try:
        crm.record_spend("onlyfans", "whale1", 300.0)
        crm.upsert_fan(platform="onlyfans", handle="newbie")
        crm.add_tag("onlyfans", "newbie", "online")
        whales = crm.smart_list("whales")
        assert any(f["handle"] == "whale1" for f in whales)
        online = crm.smart_list("online")
        assert [f["handle"] for f in online] == ["newbie"]
        crm.remove_tag("onlyfans", "newbie", "online")
        assert crm.smart_list("online") == []
        with pytest.raises(ValueError):
            crm.smart_list("bogus")
    finally:
        crm.close()


def test_crm_csv_import(tmp_path):
    from forge.crm.store import FanCRM
    csvf = tmp_path / "fans.csv"
    csvf.write_text(
        "platform,handle,tags,notes,total_spend,status\n"
        "fansly,fan_a,whale;vip,good tipper,120.5,active\n"
        "fansly,fan_b,,,,\n")
    crm = FanCRM(tmp_path / "crm.db")
    try:
        assert crm.import_csv(csvf) == 2
        fan = crm.get_fan("fansly", "fan_a")
        assert "whale" in fan["tags"] and "vip" in fan["tags"]
        assert fan["total_spend"] == 120.5
        assert "good tipper" in fan["notes"]
    finally:
        crm.close()


# -- mass DM -------------------------------------------------------------------
def test_massdm_dry_run_and_live(tmp_path):
    from forge.post.massdm import build_mass_dm, personalize
    fans = [
        {"handle": "ann", "platform": "onlyfans", "total_spend": 50},
        {"handle": "bob", "platform": "onlyfans", "total_spend": 0},
    ]
    assert personalize("hey {first}, you spent {spend}!",
                       fans[0]) == "hey ann, you spent 50!"
    manifest = build_mass_dm(
        message_template="hey {first}!", fans=fans, platform="onlyfans",
        out_dir=tmp_path, dry_run=True)
    assert manifest["targets"] == 2
    assert manifest["dry_run"] is True
    assert manifest["packet_dir"] is None
    assert "manual-assist" in manifest["delivery"]
    live = build_mass_dm(
        message_template="hey {first}!", fans=fans, platform="onlyfans",
        out_dir=tmp_path, dry_run=False)
    assert live["packet_dir"] is not None
    packet = __import__("pathlib").Path(live["packet_dir"])
    assert (packet / "ann.txt").read_text() == "hey ann!"
    assert (packet / "CHECKLIST.md").is_file()
    # exclude recently chatted
    excl = build_mass_dm(
        message_template="hi", fans=fans, platform="onlyfans",
        out_dir=tmp_path, recent_handles={"ann"}, dry_run=True)
    assert excl["targets"] == 1 and excl["skipped_recent"] == 1


# -- PPV -------------------------------------------------------------------------
def test_ppv_trigger():
    from forge.chat.ppv import looks_like_buying, ppv_offer_text
    menu = [{"label": "Custom video", "price": "$50"},
            {"label": "Photo set", "price": "$20"}]
    links = {"CashApp": "https://cash.app/$her"}
    assert looks_like_buying("how much for a custom?")
    assert not looks_like_buying("hey how are you")
    offer = ppv_offer_text(fan_message="how much for a custom video?",
                           price_menu=menu, pay_links=links,
                           sender="ann")
    assert offer is not None
    assert "$50" in offer and "cash.app" in offer
    assert ppv_offer_text(fan_message="hey cutie", price_menu=menu,
                          pay_links=links) is None
    assert ppv_offer_text(fan_message="how much?", price_menu=[],
                          pay_links=links) is None


# -- flows -------------------------------------------------------------------------
def test_welcome_flow_sequencing(tmp_path):
    from forge.chat.flows import BUILTIN_FLOWS, FlowRunner
    runner = FlowRunner(tmp_path / "flows.db")
    try:
        assert "welcome" in runner.flows and "winback" in runner.flows
        runner.enroll("welcome", "onlyfans", "ann")
        runner.enroll("welcome", "onlyfans", "ann")  # idempotent
        due = runner.due_steps()
        assert len(due) == 1 and due[0]["step_idx"] == 0
        step = runner.current_step(due[0])
        assert "{first}" in step["template"]
        rendered = runner.render(step["template"], "ann smith")
        assert "ann" in rendered and "{first}" not in rendered
        nxt = runner.advance(due[0]["id"])
        assert nxt is not None and nxt["step_idx"] == 1
        # finish the flow
        while runner.advance(due[0]["id"]) is not None:
            pass
        assert runner.due_steps() == []
        runner.enroll("winback", "onlyfans", "bob")
        runner.cancel("winback", "onlyfans", "bob")
        assert runner.pending() == []
        with pytest.raises(ValueError):
            runner.enroll("nope", "onlyfans", "x")
    finally:
        runner.close()


def test_flow_run_due_drafts_into_queue(tmp_path):
    from forge.chat.engine import ApprovalQueue, Persona, RuleEngine
    from forge.chat.flows import FlowRunner, run_due
    runner = FlowRunner(tmp_path / "flows.db")
    engine = RuleEngine(Persona(), [], queue=ApprovalQueue())
    try:
        runner.enroll("nudge", "fansly", "zed")
        drafts = run_due(runner, engine)
        assert len(drafts) == 1
        assert drafts[0].status == "pending"  # never auto-approved
        assert drafts[0].trigger == "flow:nudge"
        assert runner.due_steps() == []  # nudge has one step -> done
    finally:
        runner.close()


# -- compliance ----------------------------------------------------------------------
def test_compliance_checker():
    from forge.chat.compliance import check_draft_text
    cfg = {"banned_terms": ["meet up"],
           "patterns": [r"cashapp\.com"],
           "require_review": ["refund"]}
    findings = check_draft_text("wanna meet up?", cfg)
    assert any(f["category"] == "banned_term" for f in findings)
    findings = check_draft_text("pay me at cashapp.com/x", cfg)
    assert any(f["category"] == "pattern" for f in findings)
    findings = check_draft_text("about that refund", cfg)
    assert any(f["category"] == "require_review" for f in findings)
    assert check_draft_text("hey babe, new drop is live", cfg) == []
    # defaults catch the built-ins even with empty config
    assert check_draft_text("lets meet in person", {}) != []


# -- humanizer -------------------------------------------------------------------------
def test_humanizer_deterministic_and_safe():
    from forge.chat.humanize import humanize, typo_simulate
    a = typo_simulate("hello really there", intensity=0.3)
    b = typo_simulate("hello really there", intensity=0.3)
    assert a == b  # deterministic per text
    assert typo_simulate("hello", intensity=0.0) == "hello"
    assert humanize("Hi!", {}) == "Hi!"  # disabled by default
    out = humanize("Hello! I'm good.", {"enabled": True,
                                        "typo_intensity": 0.2})
    assert isinstance(out, str) and out


# -- ideas -------------------------------------------------------------------------------
def test_ideas_deterministic_and_honest():
    from forge.content.ideas import catalog_tags_for_ideas, generate_ideas
    items = [{"tags": ["red", "night"]}, {"tags": ["red"]}, {"tags": []}]
    tags = catalog_tags_for_ideas(items)
    assert tags[0] == "red"
    a = generate_ideas(catalog_tags=tags, count=5, seed_salt="x")
    b = generate_ideas(catalog_tags=tags, count=5, seed_salt="x")
    assert a == b
    assert all(i["method"].startswith("template remix") for i in a)
    assert len(a) == 5


# -- analytics insights ----------------------------------------------------------------------
def test_ltv_arpu_and_peak_times():
    from forge.analytics.insights import (ltv_arpu, peak_posting_times,
                                          per_post_ranking)
    ltv = ltv_arpu(total_earnings=1000.0, fan_count=10,
                   fan_spends=[5.0] * 9 + [955.0])
    assert ltv["arpu"] == 100.0
    assert ltv["avg_ltv"] == 100.0
    assert ltv["median_fan_spend"] == 5.0
    assert ltv["top_10pct_share"] > 0.9
    assert "only as complete" in ltv["method"]
    posts = [
        {"recorded_at": "2026-10-01T19:00:00", "likes": 100,
         "comments": 10, "earnings": 50.0, "platform": "of",
         "post_ref": "a", "title": "t", "views": 1000},
        {"recorded_at": "2026-10-02T19:00:00", "likes": 10,
         "comments": 1, "earnings": 5.0, "platform": "of",
         "post_ref": "b", "title": "t", "views": 100},
    ]
    peaks = peak_posting_times(posts)
    assert peaks[0]["hour"] == 19
    assert "thin sample" in peaks[0]["note"]
    ranked = per_post_ranking(posts)
    assert ranked[0]["post_ref"] == "a"


# -- stream platforms --------------------------------------------------------------------------
def test_stream_platform_matrix_honest():
    from forge.stream.platforms import get_platform, list_platforms
    plats = list_platforms()
    assert len(plats) == 8
    keys = {p["key"] for p in plats}
    assert {"chaturbate", "stripchat", "bongacams", "camsoda",
            "manyvids", "myfreecams", "fansly-live", "of-live"} <= keys
    for p in plats:
        # every entry must carry the honest fields
        for field in ("tos_risk", "chat_api", "verification",
                      "rtmp_notes", "payout_notes"):
            assert p[field], f"{p['key']} missing {field}"
        assert "ban" in p["tos_risk"].lower() or \
            "gray area" in p["tos_risk"].lower()
    cb = get_platform("chaturbate")
    assert cb["chat_api"] == "apps"
    with pytest.raises(ValueError):
        get_platform("notasite")


def test_stream_session_requires_config_and_risk(tmp_path):
    from forge.stream.session import (StreamNotConfiguredError,
                                      StreamSessionManager)

    class Cfg:
        def get_path(self, _k, default=None):
            return default

    mgr = StreamSessionManager(tmp_path)
    # no stream key configured -> honest error, not a fake session
    with pytest.raises(StreamNotConfiguredError):
        mgr.go_live(platform="chaturbate", config=Cfg(), avatar="loop",
                    avatar_source="x.mp4", acknowledged_risk=True)
    # risk not acknowledged -> refused even with config
    class Cfg2:
        def get_path(self, k, default=None):
            if k == "stream.chaturbate_rtmp":
                return "rtmp://example/live"
            if k == "stream.chaturbate_key":
                return "secret"
            return default

    with pytest.raises(StreamNotConfiguredError) as ei:
        mgr.go_live(platform="chaturbate", config=Cfg2(), avatar="loop",
                    avatar_source="x.mp4", acknowledged_risk=False)
    assert "ToS RISK" in str(ei.value)
    # unknown avatar mode
    with pytest.raises((ValueError, StreamNotConfiguredError)):
        mgr.go_live(platform="chaturbate", config=Cfg2(),
                    avatar="hologram", avatar_source="x.mp4",
                    acknowledged_risk=True)
    assert mgr.status() == {"active": False}
    assert mgr.stop()["stopped"] is False


# -- vault labels + sent log ---------------------------------------------------------------------
def test_vault_labels_and_sent_log(tmp_path):
    from forge.vault.store import Vault
    v = Vault.init(tmp_path / "vault", "correct horse")
    try:
        v.put("clip1", b"data")
        assert v.set_labels("clip1", ["ppv", "new"]) == ["new", "ppv"]
        assert v.get_labels("clip1") == ["new", "ppv"]
        assert v.blobs_by_label("ppv") == ["clip1"]
        assert v.search("new")[0]["blob"] == "clip1"
        assert not v.already_sent("clip1", "ann")
        v.log_sent("clip1", "ann")
        assert v.already_sent("clip1", "ann")
        assert v.sent_to("clip1") == ["ann"]
        assert not v.already_sent("clip1", "bob")
    finally:
        v.lock()


# -- sadtalker adapter honesty -----------------------------------------------------------------------
def test_sadtalker_requires_setup():
    from forge.live.adapters import (LiveNotConfiguredError, get_adapter)

    class Cfg:
        def get_path(self, _k, default=None):
            return default

    with pytest.raises(LiveNotConfiguredError) as ei:
        get_adapter("sadtalker", Cfg())
    assert "SadTalker" in str(ei.value)
    with pytest.raises(ValueError):
        get_adapter("notaprovider", Cfg())


# -- privacy: no real names in repo docs/code --------------------------------------------------------------
def test_no_real_person_names_in_repo():
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    skip = {"node_modules", ".venv", ".git", "__pycache__",
            ".pytest_cache", "forge-data"}
    # The checked surname is assembled so this test file itself doesn't
    # contain the literal string.
    surname = "blanken" + "baker"
    hits = []
    for p in root.rglob("*"):
        if p.resolve() == pathlib.Path(__file__).resolve():
            continue  # this test file (contains the split string only)
        if not p.is_file() or any(s in p.parts for s in skip):
            continue
        if p.suffix in {".png", ".jpg", ".jpeg", ".webp", ".mp3",
                        ".enc", ".db", ".zip"}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="strict")
        except Exception:
            continue
        if surname in text.lower():
            hits.append(str(p))
    assert not hits, f"real name leaked into repo: {hits}"
