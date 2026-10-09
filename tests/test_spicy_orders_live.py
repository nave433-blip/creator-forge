"""Feature tests: spicy chat consent gate + monetization flows,
custom video order state machine, live avatar adapters.

Run with:  python -m pytest
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from forge.identity.pack import (
    create_identity_pack,
    validate_identity_pack,
    write_identity_pack,
)

STATEMENT = """I, Test Creator, consent to CreatorForge training an AI likeness
model on my own content, generating AI videos of myself, and running
flirty/spicy chat with fans on my own accounts, including spicy chat.
Signed: Test Creator, 2026-10-09."""

PLAIN_STATEMENT = """I, Test Creator, consent to CreatorForge generating AI
videos of myself for posting on my own accounts.
Signed: Test Creator, 2026-10-09."""


def _pack(tmp_path: Path, spicy: bool = True) -> Path:
    scope = ("Training a personal AI likeness and generating videos"
             + (" including spicy chat with fans." if spicy else "."))
    pack = create_identity_pack(
        name="Test Creator", signer="Test Creator",
        scope=scope, statement=STATEMENT if spicy else PLAIN_STATEMENT)
    pack["comfort"] = {"self_filmed": ["lifestyle"],
                       "ai_only": ["fantasy"]}
    validate_identity_pack(pack)
    p = tmp_path / ("pack-spicy.yaml" if spicy else "pack-plain.yaml")
    return write_identity_pack(pack, p)


def _scene(tmp_path: Path, name: str, categories: list[str]) -> Path:
    p = tmp_path / f"{name}.yaml"
    p.write_text(yaml.safe_dump({
        "name": name, "setting": "studio", "outfit": "dress",
        "camera_angle": "medium shot", "action": "waves hello",
        "categories": categories,
    }), encoding="utf-8")
    return p


# -- spicy consent gate --------------------------------------------------------

def test_spicy_gate_refuses_without_scope(tmp_path):
    from forge.chat.spicy import SpicyConsentError, require_spicy_consent
    pack_path = _pack(tmp_path, spicy=False)
    with pytest.raises(SpicyConsentError, match="Spicy mode is locked"):
        require_spicy_consent(pack_path)


def test_spicy_gate_allows_with_scope(tmp_path):
    from forge.chat.spicy import consent_allows_spicy, require_spicy_consent
    from forge.identity.pack import load_identity_pack
    pack_path = _pack(tmp_path, spicy=True)
    pack = require_spicy_consent(pack_path)
    assert consent_allows_spicy(load_identity_pack(pack_path))
    assert pack["name"] == "Test Creator"


def test_spicy_engine_needs_pack_file(tmp_path):
    from forge.chat.spicy import SpicyConsentError, SpicyEngine
    with pytest.raises(SpicyConsentError):
        SpicyEngine.from_pack(tmp_path / "nope.yaml")


# -- spicy monetization flows ---------------------------------------------------

def test_rates_flow_produces_scorecard_and_upsell(tmp_path):
    from forge.chat.spicy import (SpicyEngine, build_rate_scorecard,
                                  rates_upsell)
    from forge.chat.engine import ApprovalQueue
    scorecard = build_rate_scorecard("bob")
    assert "bob" in scorecard and "8/10" in scorecard
    upsell = rates_upsell({"Cash App": "https://cash.app/$testcreator"})
    assert "cash.app/$testcreator" in upsell

    engine = SpicyEngine.from_pack(_pack(tmp_path), queue=ApprovalQueue())
    draft = engine.draft(platform="onlyfans", sender="bob",
                         text="hey can you rate me?",
                         links={"Cash App": "https://cash.app/$testcreator"})
    assert draft.trigger == "spicy:rates"
    assert draft.status == "pending"  # never auto-approved
    assert "cash.app/$testcreator" in draft.reply


def test_tip_request_uses_her_prices(tmp_path):
    from forge.chat.spicy import SpicyEngine, tip_request_reply
    from forge.chat.engine import ApprovalQueue
    reply = tip_request_reply("custom video", "$50",
                              {"Cash App": "https://cash.app/$testcreator"})
    assert "$50" in reply and "cash.app/$testcreator" in reply

    engine = SpicyEngine.from_pack(_pack(tmp_path), queue=ApprovalQueue())
    draft = engine.draft(platform="onlyfans", sender="amy",
                         text="how much for a custom?",
                         links={"Cash App": "https://cash.app/$x"},
                         menu=[{"label": "custom video", "price": "$75"}])
    assert draft.trigger == "spicy:tip-request"
    assert "$75" in draft.reply  # her menu price, not invented


def test_spicy_tier_never_self_escalates(tmp_path):
    from forge.chat.spicy import SpicyEngine
    from forge.chat.engine import ApprovalQueue
    engine = SpicyEngine.from_pack(_pack(tmp_path), queue=ApprovalQueue())
    assert engine.get_tier("onlyfans", "bob") == "playful"
    # even an explicit-leaning message doesn't move the tier
    engine.draft(platform="onlyfans", sender="bob",
                 text="hey sexy talk dirty to me", links={})
    assert engine.get_tier("onlyfans", "bob") == "playful"
    engine.set_tier("onlyfans", "bob", "teasing")
    assert engine.get_tier("onlyfans", "bob") == "teasing"
    with pytest.raises(ValueError):
        engine.set_tier("onlyfans", "bob", "nuclear")


def test_findom_off_by_default(tmp_path):
    from forge.chat.spicy import SpicyEngine, findom_enabled
    from forge.chat.engine import ApprovalQueue
    from forge.config import ForgeConfig
    cfg = ForgeConfig({})
    assert findom_enabled(cfg) is False
    engine = SpicyEngine.from_pack(_pack(tmp_path), queue=ApprovalQueue(),
                                   config=cfg)
    draft = engine.draft(platform="onlyfans", sender="sam",
                         text="shame me loser", links={})
    assert draft.trigger != "spicy:findom"  # ignored while disabled


# -- order state machine ---------------------------------------------------------

def test_order_create_and_full_lifecycle(tmp_path):
    from forge.orders.flow import (create_order, deliver_order, mark_paid,
                                   review_order)
    from forge.orders.store import OrderStore
    from forge.video.queue import VideoQueue

    pack_path = _pack(tmp_path)
    scene = _scene(tmp_path, "cozy-fantasy", ["fantasy"])  # ai_only
    store = OrderStore(tmp_path / "orders.db")
    try:
        order = create_order(store, fan_handle="fan1", scene_path=scene,
                             pack_path=pack_path, price_label="custom",
                             price="$50")
        assert order.status == "pending_payment"

        order = mark_paid(store, order.id)
        assert order.status == "queued"

        # illegal: can't deliver before rendering/review
        from forge.orders.flow import OrderRefusedError, deliver_order
        with pytest.raises(OrderRefusedError):
            deliver_order(store, order.id)

        # rendering -> awaiting_review needs a finished video job
        queue = VideoQueue(tmp_path / "vq.db")
        try:
            from forge.orders.flow import render_order
            order = render_order(store, queue, _FakeConfig(tmp_path),
                                 order.id, pack_path)
            assert order.status == "rendering"
            assert order.video_job_id is not None
            # job isn't done (no backend) -> review refuses honestly
            with pytest.raises(OrderRefusedError, match="not done yet"):
                review_order(store, queue, order.id)
        finally:
            queue.close()
    finally:
        store.close()


def test_order_refused_category_rejected(tmp_path):
    from forge.orders.flow import OrderRefusedError, create_order
    from forge.orders.store import OrderStore
    pack_path = _pack(tmp_path)
    scene = _scene(tmp_path, "mystery", ["totally-unknown-category"])
    store = OrderStore(tmp_path / "orders2.db")
    try:
        with pytest.raises(OrderRefusedError, match="not orderable"):
            create_order(store, fan_handle="fan2", scene_path=scene,
                         pack_path=pack_path)
    finally:
        store.close()


def test_order_cancel_refund(tmp_path):
    from forge.orders.flow import (OrderRefusedError, cancel_order,
                                   create_order, refund_order)
    from forge.orders.store import OrderStore
    pack_path = _pack(tmp_path)
    scene = _scene(tmp_path, "cozy-fantasy", ["fantasy"])
    store = OrderStore(tmp_path / "orders3.db")
    try:
        order = create_order(store, fan_handle="fan3", scene_path=scene,
                             pack_path=pack_path)
        order = cancel_order(store, order.id, reason="fan changed mind")
        assert order.status == "cancelled"
        order = refund_order(store, order.id)
        assert order.status == "refunded"
        with pytest.raises(OrderRefusedError):
            refund_order(store, order.id)  # already refunded
    finally:
        store.close()


class _FakeConfig(dict):
    def __init__(self, tmp_path: Path):
        super().__init__({})
        self._tmp = tmp_path

    def get_path(self, dotted: str, default=None):
        if dotted == "video.postprocess":
            return []
        if dotted == "catalog.db_path":
            return str(self._tmp / "catalog.db")
        return default


# -- live adapters -----------------------------------------------------------------

def test_live_adapters_need_keys():
    from forge.live.adapters import (DIDAdapter, HeyGenAdapter,
                                     LiveNotConfiguredError, get_adapter)
    from forge.config import ForgeConfig
    with pytest.raises(LiveNotConfiguredError, match="heygen_api_key"):
        HeyGenAdapter()
    with pytest.raises(LiveNotConfiguredError, match="did_api_key"):
        DIDAdapter()
    with pytest.raises(LiveNotConfiguredError):
        get_adapter("heygen", ForgeConfig({}))
    with pytest.raises(ValueError, match="Unknown live provider"):
        get_adapter("bogus", ForgeConfig({}))


def test_live_session_manager_no_active(tmp_path):
    from forge.live.session import LiveSessionManager, local_guide_text
    mgr = LiveSessionManager(tmp_path)
    assert mgr.current() is None
    assert mgr.status() == {"active": False}
    assert mgr.stop(None)["stopped"] is False
    guide = local_guide_text()
    assert "OBS" in guide and "Virtual Camera" in guide


def test_live_start_refuses_second_session(tmp_path):
    from forge.live.session import LiveSessionManager
    from forge.config import ForgeConfig
    mgr = LiveSessionManager(tmp_path)
    # fake an active session file (no provider call needed)
    mgr._save({"provider": "heygen", "info": {}})
    with pytest.raises(RuntimeError, match="already active"):
        mgr.start("heygen", ForgeConfig({}))
    mgr._save(None)


# -- triage --------------------------------------------------------------------------

def test_triage_blur_and_approve_skip(tmp_path):
    from forge.chat.triage import (NullNSFWClassifier, TriageQueue,
                                   get_classifier, make_blurred_thumbnail)
    try:
        from PIL import Image
        img = Image.new("RGB", (64, 64), (200, 30, 30))
        src = tmp_path / "fan-pic.jpg"
        img.save(src)
    except ImportError:
        pytest.skip("Pillow not installed")
    thumb = make_blurred_thumbnail(src, tmp_path / "thumb.jpg")
    assert thumb.is_file() and thumb.stat().st_size > 0

    q = TriageQueue(tmp_path / "triage.db",
                    thumbs_dir=tmp_path / "thumbs",
                    classifier=get_classifier("none"))
    try:
        item = q.add(platform="onlyfans", sender="fan9",
                     media_path=str(src))
        assert item.status == "pending"
        assert isinstance(get_classifier("none"), NullNSFWClassifier)
        assert item.nsfw_label == "unknown"  # honest: no classifier
        assert q.approve(item.id).status == "approved"
        item2 = q.add(platform="onlyfans", sender="fan9",
                      media_path=str(src))
        assert q.skip(item2.id).status == "skipped"
        assert len(q.list(status="pending")) == 0
    finally:
        q.close()
