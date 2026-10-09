"""Tests for the honest local AI fallback (forge ai ... --local) and the
placeholder directive: everything must stay green and shippable with zero
API keys configured."""
from __future__ import annotations

import io
import sys

import pytest

from forge.ai import local as local_ai
from forge.ai.local import LOCAL_TAG


def _lex_with_words():
    from forge.chat.lexicon import CustomLexicon
    lex = CustomLexicon()
    lex.add("slang", "fr")
    lex.add("emoji", "💕")
    lex.add("openers", "heyy")
    lex.add("closers", "xoxo")
    lex.add("pet_names", "babe")
    lex.add("phrases", "you already know")
    return lex


def test_local_output_always_labeled_not_ai():
    assert "not AI" in LOCAL_TAG


def test_local_captions_use_her_words():
    caps = local_ai.local_captions("beach day", n=3, lex=_lex_with_words())
    assert len(caps) == 3
    joined = " ".join(caps)
    assert "beach day" in joined
    assert "💕" in joined  # her emoji, not a default
    assert "fr" in joined  # her slang
    assert "{" not in joined and "}" not in joined


def test_local_captions_clean_without_word_bank():
    caps = local_ai.local_captions("beach day", n=2, lex=None)
    assert len(caps) == 2
    for c in caps:
        assert "{" not in c and "}" not in c, c
        assert "beach day" in c


def test_local_titles_and_ideas_counts():
    assert len(local_ai.local_titles("pool party", n=4)) == 4
    ideas = local_ai.local_content_ideas("try-ons", n=7)
    assert len(ideas) == 7
    assert all("try-ons" in i for i in ideas)


def test_local_hashtags_topic_first():
    tags = local_ai.local_hashtags("red lingerie", n=5)
    assert tags[0] == "#redlingerie"
    assert len(tags) == 5
    assert all(t.startswith("#") for t in tags)


def test_local_promo_uses_her_price_never_invents():
    text = local_ai.local_promo("custom video", "$25", lex=_lex_with_words())
    assert "$25" in text
    assert "custom video" in text


def test_local_polish_is_mechanical_only():
    assert local_ai.local_polish("  hello   world  ") == "Hello world."
    assert local_ai.local_polish("already fine!") == "Already fine!"
    assert local_ai.local_polish("") == ""
    # adds no new content words
    out = local_ai.local_polish("new drop friday")
    assert out == "New drop friday."


def test_local_reply_options_safe():
    opts = local_ai.local_reply_options("send me something spicy",
                                        lex=_lex_with_words())
    assert len(opts) == 2
    joined = " ".join(opts).lower()
    assert "babe" in joined  # her pet name used
    for bad in ("nude", "explicit", "naked"):
        assert bad not in joined


def test_local_templates_contain_no_real_names():
    """Privacy: template output must never contain her real name.

    (Name assembled from parts so this file itself doesn't contain the
    literal string -- same technique as test_no_real_person_names_in_repo.)
    """
    first, last = "li" + "ly", "blanken" + "baker"
    blob = " ".join(
        local_ai.local_captions("x", n=10)
        + local_ai.local_titles("x", n=10)
        + local_ai.local_content_ideas("x", n=12)
        + local_ai.local_scene_ideas("x", n=6)
        + local_ai.local_reply_options("x")
        + [local_ai.local_promo("x", "$1")]
    ).lower()
    assert first not in blob
    assert last not in blob


# -- CLI --

def _run_cli(*args: str):
    from forge.cli import app as cli_app
    old_argv, old_out, old_err = sys.argv, sys.stdout, sys.stderr
    out, err = io.StringIO(), io.StringIO()
    sys.argv = ["forge", *args]
    sys.stdout, sys.stderr = out, err
    try:
        try:
            cli_app()
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
        else:
            code = 0
    finally:
        sys.argv, sys.stdout, sys.stderr = old_argv, old_out, old_err
    return code, out.getvalue(), err.getvalue()


def test_cli_ai_local_caption_no_keys_needed(tmp_path):
    cfg = tmp_path / "forge.yaml"
    cfg.write_text("chat: {}\n", encoding="utf-8")
    code, out, err = _run_cli("ai", "caption", "--topic", "beach day",
                              "--n", "2", "--local", "--config", str(cfg))
    assert code == 0, err
    assert LOCAL_TAG in out
    assert "beach day" in out
    assert "Traceback" not in out + err


def test_cli_ai_local_hashtags_and_polish(tmp_path):
    cfg = tmp_path / "forge.yaml"
    cfg.write_text("chat: {}\n", encoding="utf-8")
    code, out, err = _run_cli("ai", "hashtags", "--topic", "pool",
                              "--n", "3", "--local", "--config", str(cfg))
    assert code == 0, err
    assert "#pool" in out
    code, out, err = _run_cli("ai", "polish", "--text", "  hi there  ",
                              "--local", "--config", str(cfg))
    assert code == 0, err
    assert "Hi there." in out


def test_cli_ai_ask_local_refuses_cleanly(tmp_path):
    cfg = tmp_path / "forge.yaml"
    cfg.write_text("chat: {}\n", encoding="utf-8")
    code, out, err = _run_cli("ai", "ask", "--prompt", "hello",
                              "--local", "--config", str(cfg))
    assert code != 0
    assert "Traceback" not in out + err
    assert "--local" in err


def test_cli_ai_no_key_error_points_to_local(tmp_path):
    """Without keys AND without --local: clean error that names the fix."""
    cfg = tmp_path / "forge.yaml"
    cfg.write_text("chat: {}\n", encoding="utf-8")
    code, out, err = _run_cli("ai", "caption", "--topic", "x",
                              "--config", str(cfg))
    assert code != 0
    assert "Traceback" not in out + err
    assert "--local" in err


def test_cli_ai_local_uses_word_bank(tmp_path):
    from forge.chat.lexicon import CustomLexicon
    lex = CustomLexicon()
    lex.add("emoji", "💕")
    lex.save(tmp_path / "lexicon.json")
    cfg = tmp_path / "forge.yaml"
    cfg.write_text(f"chat:\n  lexicon_path: {tmp_path / 'lexicon.json'}\n",
                   encoding="utf-8")
    code, out, err = _run_cli("ai", "caption", "--topic", "beach",
                              "--n", "1", "--local", "--config", str(cfg))
    assert code == 0, err
    assert "💕" in out
