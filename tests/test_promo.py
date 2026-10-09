"""Tests for promo-link (affiliate/shoutout) tracking."""
from __future__ import annotations

import io
import sys

import pytest


@pytest.fixture()
def tracker(tmp_path):
    from forge.promo.tracker import PromoTracker
    t = PromoTracker(tmp_path / "promo.db")
    yield t
    t.close()


def test_tag_url_appends_utm_and_preserves_query():
    from forge.promo.tracker import tag_url
    out = tag_url("https://example.com/page?x=1", campaign="summer",
                  source="gf", medium="shoutout")
    assert "utm_campaign=summer" in out
    assert "utm_source=gf" in out
    assert "utm_medium=shoutout" in out
    assert "x=1" in out  # existing params preserved


def test_tag_url_rejects_bad_url_and_empty_campaign():
    from forge.promo.tracker import tag_url
    with pytest.raises(ValueError):
        tag_url("not a url", campaign="x")
    with pytest.raises(ValueError):
        tag_url("ftp://example.com", campaign="x")
    with pytest.raises(ValueError):
        tag_url("https://example.com", campaign="  ")


def test_create_link_unique_codes(tracker):
    rows = [tracker.create_link("https://example.com/a", "c1")
            for _ in range(20)]
    codes = [r["code"] for r in rows]
    assert len(set(codes)) == 20
    assert all("utm_campaign=c1" in r["full_url"] for r in rows)


def test_get_by_code_case_insensitive(tracker):
    row = tracker.create_link("https://example.com/a", "c1")
    assert tracker.get_by_code(row["code"].lower())["id"] == row["id"]
    with pytest.raises(KeyError):
        tracker.get_by_code("NOPE00")


def test_log_earning_and_report(tracker):
    r1 = tracker.create_link("https://example.com/a", "summer")
    r2 = tracker.create_link("https://example.com/b", "summer")
    r3 = tracker.create_link("https://example.com/c", "winter")
    tracker.log_earning(r1["code"], 50.0, note="shoutout paid off")
    tracker.log_earning(r2["code"], 25.5)
    tracker.log_earning(r3["code"], 10.0)
    report = {r["campaign"]: r for r in tracker.report()}
    assert report["summer"]["earnings"] == pytest.approx(75.5)
    assert report["summer"]["links"] == 2
    assert report["winter"]["earnings"] == pytest.approx(10.0)


def test_log_earning_rejects_bad_amount(tracker):
    row = tracker.create_link("https://example.com/a", "c1")
    with pytest.raises(ValueError):
        tracker.log_earning(row["code"], -5)
    with pytest.raises(ValueError):
        tracker.log_earning(row["code"], "lots")
    with pytest.raises(KeyError):
        tracker.log_earning("NOPE00", 5)


def test_list_links_filter_campaign(tracker):
    tracker.create_link("https://example.com/a", "c1")
    tracker.create_link("https://example.com/b", "c2")
    assert len(tracker.list_links()) == 2
    assert len(tracker.list_links(campaign="c1")) == 1


def test_promo_concurrent_create_no_dup_codes(tmp_path):
    import threading
    from forge.promo.tracker import PromoTracker
    t = PromoTracker(tmp_path / "p.db")
    try:
        n = 8
        barrier = threading.Barrier(n)
        codes: list[str] = []
        lock = threading.Lock()

        def worker():
            barrier.wait()
            for _ in range(10):
                r = t.create_link("https://example.com/a", "cc")
                with lock:
                    codes.append(r["code"])

        threads = [threading.Thread(target=worker) for _ in range(n)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        assert len(codes) == 80
        assert len(set(codes)) == 80
    finally:
        t.close()


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


def _cfg(tmp_path) -> str:
    p = tmp_path / "forge.yaml"
    p.write_text(f"promo:\n  db_path: {tmp_path / 'promo.db'}\n",
                 encoding="utf-8")
    return str(p)


def test_cli_promo_end_to_end(tmp_path):
    cfg = _cfg(tmp_path)
    code, out, err = _run_cli("promo", "link-create", "--url",
                              "https://example.com/menu",
                              "--campaign", "summer", "--source", "gf",
                              "--config", cfg)
    assert code == 0, err
    assert "utm_campaign=summer" in out
    code_line = [l for l in out.splitlines() if l.startswith("Code:")][0]
    code_val = code_line.split(":", 1)[1].strip()

    code, out, err = _run_cli("promo", "link-list", "--config", cfg)
    assert code == 0, err
    assert code_val in out

    code, out, err = _run_cli("promo", "log-earning", "--code", code_val,
                              "--amount", "42.5", "--config", cfg)
    assert code == 0, err

    code, out, err = _run_cli("promo", "report", "--config", cfg)
    assert code == 0, err
    assert "summer" in out and "42.50" in out


def test_cli_promo_bad_url_clean_error(tmp_path):
    cfg = _cfg(tmp_path)
    code, out, err = _run_cli("promo", "link-create", "--url", "notaurl",
                              "--campaign", "x", "--config", cfg)
    assert code != 0
    assert "Traceback" not in out + err
    assert "http" in err.lower()


def test_dashboard_promo_endpoints(tmp_path):
    import forge.dashboard.app as dash_app
    from fastapi.testclient import TestClient
    from forge.config import ForgeConfig
    dash_app.init_state(
        ForgeConfig({"promo": {"db_path": str(tmp_path / "promo.db")}}),
        tmp_path / "dash.db")
    c = TestClient(dash_app.app)
    r = c.get("/promo/report")
    assert r.status_code == 200
    assert r.json() == {"campaigns": []}
    r = c.get("/promo/links")
    assert r.status_code == 200
    assert r.json() == {"links": []}
