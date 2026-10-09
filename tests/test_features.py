"""Feature tests: vault, comfort boundary, style profiler, connectors,
trainers registry, voice consent gate, chat conversation modes."""

from __future__ import annotations

import pytest

from forge.chat.engine import Persona, RuleEngine, Trigger
from forge.chat.style import build_style_profile, draft_in_style
from forge.connect.registry import capabilities_table, get_connector
from forge.identity.pack import (
    InvalidConsentError,
    create_identity_pack,
    validate_identity_pack,
)
from forge.persona.trainers import get_trainer, list_trainers
from forge.persona.voice import VoiceConsentError, VoiceNotConfiguredError
from forge.vault.store import Vault, VaultLockedError
from forge.video.scenes import Scene, resolve_scene

STATEMENT = """I, Test Creator, consent to CreatorForge training an AI likeness
and voice model on my own content and generating AI videos of myself for
posting on my own accounts. Signed: Test Creator, 2026-10-09."""


def _pack(**kw):
    kw.setdefault("name", "Test Creator")
    kw.setdefault("signer", "Test Creator")
    kw.setdefault("scope", ("Training a personal AI likeness and voice model "
                            "on my own content and generating AI videos of "
                            "myself for my own accounts."))
    kw.setdefault("statement", STATEMENT)
    pack = create_identity_pack(**kw)
    pack["comfort"] = {"self_filmed": ["lifestyle"],
                       "ai_only": ["fantasy"]}
    return validate_identity_pack(pack)


# -- vault ------------------------------------------------------------------
def test_vault_round_trip(tmp_path):
    v = Vault.init(tmp_path / "vault", "correct horse")
    v.put("photo", b"\x89PNG fake bytes")
    assert v.get("photo") == b"\x89PNG fake bytes"
    v.put_json("settings", {"a": 1})
    assert v.get_json("settings") == {"a": 1}
    assert "photo" in v.list()


def test_vault_wrong_password(tmp_path):
    Vault.init(tmp_path / "vault", "right password")
    v = Vault(tmp_path / "vault")
    v.lock()
    with pytest.raises(VaultLockedError):
        v.unlock("wrong password")


def test_vault_locked_blocks_access(tmp_path):
    Vault.init(tmp_path / "vault", "pw")
    v = Vault(tmp_path / "vault")
    v.lock()
    with pytest.raises(VaultLockedError):
        v.get("anything")
    with pytest.raises(VaultLockedError):
        v.list()


def test_vault_tampered_blob_detected(tmp_path):
    v = Vault.init(tmp_path / "vault", "pw")
    v.put("secret", b"data")
    blob = tmp_path / "vault" / "data" / "secret.enc"
    raw = bytearray(blob.read_bytes())
    raw[-1] ^= 0xFF
    blob.write_bytes(bytes(raw))
    with pytest.raises(Exception):
        v.get("secret")


# -- comfort boundary ---------------------------------------------------------
def test_scene_ai_only():
    d = resolve_scene(Scene(name="s1", categories=["fantasy"]), _pack())
    assert d.mode == "ai"


def test_scene_self_filmed_uses_real():
    items = [{"path": "/x/a.jpg", "tags": ["lifestyle"]},
             {"path": "/x/b.jpg", "tags": ["other"]}]
    d = resolve_scene(Scene(name="s2", categories=["lifestyle"]), _pack(),
                      items)
    assert d.mode == "real"
    assert d.catalog_items == [items[0]]


def test_scene_unknown_category_refused():
    d = resolve_scene(Scene(name="s3", categories=["mystery"]), _pack())
    assert d.mode == "refused"


def test_scene_mixed_boundary_refused():
    d = resolve_scene(Scene(name="s4", categories=["lifestyle", "fantasy"]),
                      _pack())
    assert d.mode == "refused"


def test_scene_no_categories_refused():
    d = resolve_scene(Scene(name="s5"), _pack())
    assert d.mode == "refused"


# -- style profiler ------------------------------------------------------------
TRANSCRIPT = [
    {"sender": "them", "text": "hey", "ts": 1000},
    {"sender": "her", "text": "heyy babe hows it going 💕", "ts": 1060},
    {"sender": "them", "text": "what are prices", "ts": 1100},
    {"sender": "her", "text": "menu is on my page lmk what u want babe 💋",
     "ts": 1180},
    {"sender": "them", "text": "ok cool", "ts": 1200},
    {"sender": "her", "text": "lmk babe 💕", "ts": 1260},
]


def test_style_profile_builds(tmp_path):
    import yaml
    pack_path = tmp_path / "pack.yaml"
    pack_path.write_text(yaml.safe_dump(_pack()), encoding="utf-8")
    profile = build_style_profile(TRANSCRIPT,
                                  identity_pack_path=str(pack_path))
    assert profile.sample_count == 3
    assert profile.emoji_rate == 1.0
    assert profile.top_emojis[0][0] == "💕"
    lex = dict(profile.lexicon)
    assert lex.get("babe", 0) >= 2
    assert lex.get("lmk", 0) >= 2
    assert profile.median_reply_latency_s == 60.0
    assert any("heyy" in o[0] for o in profile.openers)


def test_style_profile_refuses_without_consent():
    with pytest.raises(InvalidConsentError):
        build_style_profile(TRANSCRIPT, identity_pack_path=None)


def test_draft_in_style_applies_closer_and_emoji(tmp_path):
    import yaml
    pack_path = tmp_path / "pack.yaml"
    pack_path.write_text(yaml.safe_dump(_pack()), encoding="utf-8")
    profile = build_style_profile(TRANSCRIPT,
                                  identity_pack_path=str(pack_path))
    out = draft_in_style(profile, "Thanks for asking")
    assert "💕" in out  # her top emoji at 100% rate


# -- connectors -----------------------------------------------------------------
def test_capability_matrix_honest():
    table = {r["connector"]: r for r in capabilities_table()}
    assert table["fansly"]["import"] == "manual"
    assert table["fansly"]["export"] == "manual"
    assert table["onlyfans"]["import"] == "manual"
    assert table["reddit"]["import"] == "full"
    assert table["reddit"]["export"] == "full"
    assert table["filesystem"]["import"] == "full"
    get_connector("fansly").capabilities()
    with pytest.raises(KeyError):
        get_connector("nonexistent")


def test_fansly_manual_import_ingests_files(tmp_path):
    from PIL import Image
    src = tmp_path / "export"
    src.mkdir()
    Image.new("RGB", (16, 16), "red").save(src / "pic.png")
    (src / "vault.csv").write_text("a,b\n", encoding="utf-8")
    summary = get_connector("fansly").import_data(str(src),
                                                 str(tmp_path / "dest"))
    assert summary["copied_media"] == 1
    assert summary["copied_csv"] == 1


# -- trainers ---------------------------------------------------------------------
def test_trainers_registry():
    trainers = list_trainers()
    assert len(trainers) == 5
    kinds = {t.kind for t in trainers}
    assert kinds == {"local-gpu", "paid-api"}
    kohya = get_trainer("kohya_sd LoRA")
    assert "VRAM" in kohya.gpu_notes
    assert kohya.config_generator is not None
    with pytest.raises(KeyError):
        get_trainer("magic instant ai")


def test_diffusers_command_builds():
    from forge.persona.trainers import diffusers_lora_command
    cmd = diffusers_lora_command(train_data_dir="d", output_dir="o",
                                 pretrained_model="base")
    assert "train_text_to_image_lora_sdxl.py" in cmd
    assert "--rank=16" in cmd


# -- voice consent gate --------------------------------------------------------------
def test_voice_clone_refuses_without_key():
    from forge.persona.voice import ElevenLabsVoice
    import os
    os.environ.pop("ELEVENLABS_API_KEY", None)
    with pytest.raises(VoiceNotConfiguredError):
        ElevenLabsVoice(api_key=None, config_key=None)


def test_voice_speak_refuses_without_consent(tmp_path):
    from forge.persona.voice import ElevenLabsVoice, _require_voice_consent
    with pytest.raises(VoiceConsentError):
        _require_voice_consent(str(tmp_path / "missing.yaml"))
    # key accepted structurally, but consent checked first in speak()
    v = ElevenLabsVoice(api_key="fake-key")
    with pytest.raises(VoiceConsentError):
        v.speak(text="hi", voice_id="x", out_path=str(tmp_path / "o.mp3"),
                identity_pack_path=str(tmp_path / "missing.yaml"))


# -- chat conversation modes ----------------------------------------------------------
def _engine():
    return RuleEngine(Persona(name="c"),
                      [Trigger(name="t", pattern="hi",
                               reply_template="hello {sender}")])


def test_chat_manual_mode_drafts_nothing():
    e = _engine()
    e.set_conversation_mode("manual", "fan1", "manual")
    assert e.handle_message(platform="manual", sender="fan1",
                            text="hi there") is None
    assert len(e.seen) == 1
    assert e.queue.pending() == []


def test_chat_auto_mode_approves():
    e = _engine()
    e.set_conversation_mode("manual", "fan1", "auto")
    d = e.handle_message(platform="manual", sender="fan1", text="hi there")
    assert d is not None and d.status == "approved"


def test_chat_default_is_approve_first():
    e = _engine()
    d = e.handle_message(platform="manual", sender="fan1", text="hi there")
    assert d is not None and d.status == "pending"


def test_chat_bad_mode_rejected():
    e = _engine()
    with pytest.raises(ValueError):
        e.set_conversation_mode("p", "s", "yolo")


def test_chat_modes_persist(tmp_path):
    e = _engine()
    e.set_conversation_mode("p", "s", "manual")
    p = tmp_path / "modes.json"
    e.save_modes(p)
    e2 = _engine()
    e2.load_modes(p)
    assert e2.get_conversation_mode("p", "s") == "manual"


def test_chat_queue_persists(tmp_path):
    e = _engine()
    d = e.handle_message(platform="p", sender="s", text="hi")
    p = tmp_path / "queue.json"
    e.queue.save(p)
    e2 = _engine()
    e2.queue.load(p)
    assert e2.queue.get(d.id).reply == d.reply
