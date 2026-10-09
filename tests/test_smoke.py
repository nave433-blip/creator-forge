"""Smoke tests for CreatorForge.

Run with:  python -m pytest   (or: .venv/bin/python -m pytest)

These cover the hard guarantees:
1. The video pipeline REFUSES to run without a valid consent pack.
2. Catalog scan dedupes by sha256.
3. Payment links build correct URLs.
4. Chat drafts stay pending until a human approves; only approved drafts
   can be marked sent.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from forge.catalog.scanner import scan_directory
from forge.catalog.store import CatalogStore
from forge.chat.engine import Persona, RuleEngine, Trigger
from forge.config import ForgeConfig
from forge.identity.pack import (
    InvalidConsentError,
    create_identity_pack,
    validate_identity_pack,
)
from forge.pay.links import build_payment_links
from forge.video.pipeline import ConsentGateError, generate_video

STATEMENT = """I, Test Creator, consent to CreatorForge training an AI likeness
model on my own content and generating AI videos of myself for posting on
my own accounts. Signed: Test Creator, 2026-10-09."""


def _valid_pack():
    return create_identity_pack(
        name="Test Creator",
        signer="Test Creator",
        scope="Training a personal AI likeness on my own content and "
              "generating AI videos of myself for my own accounts.",
        statement=STATEMENT,
    )


# -- identity / consent gate ------------------------------------------------
def test_identity_pack_validates():
    pack = validate_identity_pack(_valid_pack())
    assert pack["consent"]["signer"] == "Test Creator"


def test_identity_gate_rejects_missing_consent():
    with pytest.raises(InvalidConsentError):
        validate_identity_pack({"name": "No Consent Here"})


def test_identity_gate_rejects_tampered_statement():
    pack = _valid_pack()
    pack["consent_statement"] = "I changed the statement after signing."
    with pytest.raises(InvalidConsentError):
        validate_identity_pack(pack)


def test_video_pipeline_refuses_without_consent(tmp_path):
    cfg = ForgeConfig({"video": {"adapter": "replicate"}})
    with pytest.raises(ConsentGateError):
        generate_video(
            config=cfg,
            identity_pack_path=str(tmp_path / "nope.yaml"),
            prompt="a test video",
        )


def test_video_pipeline_refuses_invalid_pack(tmp_path):
    bad = tmp_path / "bad-pack.yaml"
    bad.write_text("name: broken\n", encoding="utf-8")
    cfg = ForgeConfig({"video": {"adapter": "replicate"}})
    with pytest.raises(ConsentGateError):
        generate_video(config=cfg, identity_pack_path=str(bad),
                       prompt="a test video")


def test_video_pipeline_refuses_unconfigured_backend(tmp_path):
    import yaml
    pack_path = tmp_path / "pack.yaml"
    with pack_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(_valid_pack(), fh)
    cfg = ForgeConfig({"video": {"adapter": "replicate"}})  # no token
    from forge.video.adapters import NotConfiguredError
    with pytest.raises(NotConfiguredError):
        generate_video(config=cfg, identity_pack_path=str(pack_path),
                       prompt="a test video")


# -- catalog ----------------------------------------------------------------
def test_catalog_scan_dedupes(tmp_path):
    from PIL import Image
    media = tmp_path / "media"
    media.mkdir()
    img = Image.new("RGB", (64, 64), "red")
    img.save(media / "a.png")
    img.save(media / "b.png")  # identical bytes -> duplicate
    Image.new("RGB", (32, 32), "blue").save(media / "c.jpg")
    (media / "notes.txt").write_text("not media", encoding="utf-8")

    store = CatalogStore(tmp_path / "catalog.db")
    result = scan_directory(media, store, tags=["test"])
    assert result == {"scanned": 3, "added": 2,
                      "skipped_duplicates": 1, "skipped_unsupported": 1}
    assert store.count() == 2
    found = store.search("a.png")
    assert len(found) == 1 and found[0]["tags"] == ["test"]
    assert found[0]["width"] == 64 and found[0]["height"] == 64
    store.close()


# -- payments ---------------------------------------------------------------
def test_payment_links_format():
    links = build_payment_links({"pay": {
        "venmo": "@JaneDoe", "cashapp": "$janedoe",
        "paypal_me": "janedoe", "crypto_btc": "bc1qxyz",
        "custom": {"Throne": "https://throne.com/janedoe"},
    }})
    assert links["Venmo"] == "https://venmo.com/JaneDoe"
    assert links["Cash App"] == "https://cash.app/janedoe"
    assert links["PayPal"] == "https://paypal.me/janedoe"
    assert links["Bitcoin"] == "bitcoin:bc1qxyz"
    assert links["Throne"] == "https://throne.com/janedoe"


def test_payment_links_empty():
    assert build_payment_links({"pay": {}}) == {}
    assert build_payment_links({}) == {}


# -- chat approval flow -----------------------------------------------------
def _engine():
    persona = Persona(name="creator", tone="friendly",
                      boundaries=["meet in person"])
    triggers = [Trigger(name="price", pattern=r"\bprice\b",
                        reply_template="Hi {sender}, menu is on my page!")]
    return RuleEngine(persona, triggers)


def test_chat_draft_pending_by_default():
    engine = _engine()
    draft = engine.handle_message(platform="manual", sender="fan1",
                                  text="what is the price?")
    assert draft.status == "pending"
    assert draft.trigger == "price"
    assert "fan1" in draft.reply


def test_chat_approve_then_sent():
    engine = _engine()
    draft = engine.handle_message(platform="manual", sender="fan1",
                                  text="hello there")
    engine.queue.approve(draft.id)
    assert engine.queue.get(draft.id).status == "approved"
    engine.queue.mark_sent(draft.id)
    assert engine.queue.get(draft.id).status == "sent"


def test_chat_cannot_send_without_approval():
    engine = _engine()
    draft = engine.handle_message(platform="manual", sender="fan1",
                                  text="hello there")
    with pytest.raises(ValueError):
        engine.queue.mark_sent(draft.id)


def test_chat_reject():
    engine = _engine()
    draft = engine.handle_message(platform="manual", sender="fan1",
                                  text="hello there")
    engine.queue.reject(draft.id)
    assert engine.queue.pending() == []


def test_chat_boundary_fallback():
    engine = _engine()
    draft = engine.handle_message(platform="manual", sender="fan1",
                                  text="can we meet in person?")
    assert draft.trigger == "boundary-fallback"


def test_init_scaffolds_example_configs(tmp_path):
    """Regression: `forge init` must copy example configs into the new
    project folder (they ship inside the installed package)."""
    from forge.cli import app
    runner = CliRunner()
    target = tmp_path / "my-project"
    result = runner.invoke(app, ["init", str(target)])
    assert result.exit_code == 0, result.output
    for name in ("forge.yaml", "identity-pack.yaml", "persona.yaml"):
        p = target / name
        assert p.is_file(), f"{name} was not scaffolded by forge init"
        assert p.stat().st_size > 0, f"{name} scaffolded empty"


def test_menu_sections_reference_real_cli_functions():
    """Every menu entry must name a real forge.cli function (no dead items)."""
    import inspect
    import forge.cli as C
    import forge.menu as M
    for title, items in M.SECTIONS:
        for label, func_name, params in items:
            assert hasattr(C, func_name), f"{title} / {label}: {func_name}"
            sig = inspect.signature(getattr(C, func_name))
            for pname, _prompt, _default in params:
                key = pname[:-3] if pname.endswith("...") else pname
                assert key in sig.parameters, \
                    f"{label}: param {key!r} not in {func_name}()"


def test_menu_covers_promo_and_telegram():
    import forge.menu as M
    titles = [t for t, _ in M.SECTIONS]
    assert any("Promo" in t for t in titles)
    assert any("Telegram" in t for t in titles)
