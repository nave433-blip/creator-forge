"""QA regression tests: clean errors, flows hardening, tube flags, skills."""
import pytest
from typer.testing import CliRunner

from forge.cli import app as cli_app

runner = CliRunner()


def test_cli_errors_are_clean_no_traceback():
    """User-facing errors print one line, never a traceback."""
    cases = [
        ["identity", "validate", "/definitely/not/here.yaml"],
        ["chat", "approve", "424242"],
        ["chat", "mode", "--platform", "t", "--sender", "s", "--mode", "bogus"],
        ["tube", "metadata", "--site", "nope"],
        ["video", "generate", "--prompt", "x"],  # no pack configured
    ]
    for args in cases:
        r = runner.invoke(cli_app, args)
        assert r.exit_code != 0, args
        assert "Traceback" not in r.output, f"{args} leaked a traceback"


def test_cli_help_still_works_after_wrapper():
    r = runner.invoke(cli_app, ["tube", "metadata", "--help"])
    assert r.exit_code == 0
    assert "--template" in r.output


def test_flows_render_empty_handle():
    from forge.chat.flows import FlowRunner
    fr = FlowRunner(":memory:")
    out = fr.render("hey {first}, it's {handle}!", "")
    assert "there" in out


def test_flows_enroll_rejects_empty():
    from forge.chat.flows import FlowRunner
    fr = FlowRunner(":memory:")
    with pytest.raises(ValueError):
        fr.enroll("welcome", "", "bob")
    with pytest.raises(ValueError):
        fr.enroll("welcome", "onlyfans", "  ")


def test_flows_run_due_survives_stale_run():
    """A run pointing past the end of its flow is closed, not crashed."""
    from forge.chat.flows import FlowRunner, run_due

    class FakeQueue:
        def __init__(self):
            self.drafts = []

        def add(self, **kw):
            d = dict(kw, id=len(self.drafts) + 1)
            self.drafts.append(d)
            return type("D", (), d)()

    class FakeEngine:
        def __init__(self):
            self.queue = FakeQueue()

    fr = FlowRunner(":memory:")
    fr._conn.execute(
        "INSERT INTO flow_runs (flow, platform, handle, step_idx,"
        " enrolled_at, due_at, status) VALUES (?,?,?,?,?,?,?)",
        ("welcome", "t", "s", 99, "2020-01-01", "2020-01-01", "active"))
    fr._conn.commit()
    drafts = run_due(fr, FakeEngine())  # must not raise
    assert drafts == []
    row = fr._conn.execute(
        "SELECT status FROM flow_runs WHERE handle='s'").fetchone()
    assert row["status"] == "cancelled"


def test_tube_tags_truncated_flag():
    from forge.tube.metadata import generate_metadata
    from forge.tube.sites import get_site
    site = get_site("xhamster")  # max 10 tags
    meta = generate_metadata(
        site, {"vibe": "sensual lingerie pov webcam solo tease"},
        custom_tags=[f"tag{i}" for i in range(15)])
    assert meta.tags_truncated is True
    assert len(meta.tags) == 10
    assert "tag0" in meta.tags  # custom tags keep priority


def test_tube_tags_not_truncated_flag():
    from forge.tube.metadata import generate_metadata
    from forge.tube.sites import get_site
    meta = generate_metadata(get_site("pornhub"), custom_tags=["a", "b"])
    assert meta.tags_truncated is False


def test_skill_argparse_error_becomes_skill_error():
    from forge.skills import SkillError, run_skill
    with pytest.raises(SkillError):
        run_skill("watermark", ["--not-a-real-flag", "x"])


def test_menu_template_param_coerces_to_int():
    from forge.menu import _coerce, _INT_PARAMS
    assert "template" in _INT_PARAMS
    assert _coerce("template", "2") == 2
