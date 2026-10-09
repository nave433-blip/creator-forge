"""Tests for the custom word bank (forge/chat/lexicon.py)."""

import json

import pytest

from forge.chat.lexicon import (
    CATEGORIES,
    CustomLexicon,
    draft_in_style,
)


def test_add_list_remove_round_trip():
    lex = CustomLexicon()
    assert lex.add("slang", "papi", "what she calls fans") is True
    # dupes rejected (case-insensitive)
    assert lex.add("slang", "PAPI") is False
    items = lex.list("slang")["slang"]
    assert [e.term for e in items] == ["papi"]
    assert lex.remove("slang", "papi") is True
    assert lex.remove("slang", "papi") is False
    assert lex.list("slang")["slang"] == []


def test_unknown_category_rejected():
    lex = CustomLexicon()
    with pytest.raises(ValueError):
        lex.add("nope", "x")
    with pytest.raises(ValueError):
        lex.remove("nope", "x")


def test_search_finds_term_and_note():
    lex = CustomLexicon()
    lex.add("pet_names", "pookie", "top tipper nickname")
    hits = lex.search("tipper")
    assert [(c, e.term) for c, e in hits] == [("pet_names", "pookie")]
    assert lex.search("zzz") == []


def test_render_placeholders():
    lex = CustomLexicon()
    lex.add("pet_names", "baby")
    lex.add("emoji", "\U0001F496")
    out = lex.render("hey {pet_name} {sender}, you up? {emoji}", sender="Mike")
    assert out == "hey baby Mike, you up? \U0001F496"
    # missing placeholders are left as-is, never silently dropped
    assert lex.render("hi {opener}") == "hi {opener}"


def test_spicy_render_gated():
    lex = CustomLexicon()
    lex.add("spicy", "secret-word")
    assert lex.render("{spicy}") == "{spicy}"
    assert lex.render("{spicy}", allow_spicy=True) == "secret-word"


def test_save_load_round_trip(tmp_path):
    lex = CustomLexicon()
    lex.add("closers", "ttyl \U0001F618")
    p = tmp_path / "lex.json"
    lex.save(p)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["entries"]["closers"][0]["term"] == "ttyl \U0001F618"
    back = CustomLexicon.load(p)
    assert back.first("closers") == "ttyl \U0001F618"
    # missing file = empty bank, not an error
    assert CustomLexicon.load(tmp_path / "nope.json").list()["slang"] == []


def test_adopt_from_profile():
    from forge.chat.style import StyleProfile
    prof = StyleProfile(lexicon=[("papi", 12), ("fr", 9), ("the", 3)])
    lex = CustomLexicon()
    added = lex.adopt_from_profile(prof, n=2)
    assert added == ["papi", "fr"]
    # adopting again adds nothing new
    assert lex.adopt_from_profile(prof, n=2) == []


def test_draft_in_style_prefers_word_bank():
    from forge.chat.style import StyleProfile
    prof = StyleProfile(closers=[("later gator", 5)],
                        top_emojis=[("\U0001F60E", 4)], emoji_rate=0.9)
    lex = CustomLexicon()
    lex.add("closers", "mwah \U0001F618")
    out = draft_in_style(prof, "hey there", lexicon=lex)
    assert "mwah \U0001F618" in out
    assert "later gator" not in out  # custom wins over learned


def test_draft_in_style_falls_back_to_profile():
    from forge.chat.style import StyleProfile
    prof = StyleProfile(closers=[("later gator", 5)])
    out = draft_in_style(prof, "hey there")
    assert "later gator" in out


def test_categories_cover_word_bank_needs():
    for needed in ("slang", "phrases", "pet_names", "emoji", "openers",
                   "closers", "spicy"):
        assert needed in CATEGORIES
