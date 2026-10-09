"""Stress + adversarial tests for CreatorForge.

Covers: malformed CLI input through the real ForgeTyper wrapper (production
error path, not CliRunner), concurrent dashboard requests from threads,
corrupt/empty/bomb catalog images, vault wrong-password/truncated/corrupt
cases, approval-queue races, and scheduler overlap + garbage times.

Threading note: the dashboard serves from worker threads, so the queue,
Scheduler, and CatalogStore are expected to be thread-safe.
"""
from __future__ import annotations

import io
import json
import os
import struct
import sys
import threading
import zlib
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def run_cli(*args: str):
    """Invoke the CLI through the real ForgeTyper.__call__ wrapper.

    This is the production path (``forge ...`` console script), where domain
    errors become clean one-line messages. Returns (exit_code, stdout, stderr).
    """
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


def assert_clean_failure(code: int, stdout: str, stderr: str):
    assert code != 0, "expected a failure exit code"
    assert "Traceback" not in stdout + stderr, "traceback leaked to user"


def make_config(tmp_path: Path, **overrides) -> str:
    """Write a minimal forge.yaml in tmp and return its path."""
    import yaml
    cfg = {
        "catalog": {"db_path": str(tmp_path / "catalog.db")},
        "post": {
            "packets_dir": str(tmp_path / "packets"),
            "schedule_db": str(tmp_path / "schedule.db"),
        },
    }
    cfg.update(overrides)
    p = tmp_path / "forge.yaml"
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# 1. malformed CLI input (production wrapper path)
# ---------------------------------------------------------------------------

def test_cli_garbage_yaml_config_is_clean_error(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("just a string: [unclosed\n", encoding="utf-8")
    code, out, err = run_cli("catalog", "list", "--config", str(bad))
    assert_clean_failure(code, out, err)
    assert "Bad YAML" in err


def test_cli_non_mapping_yaml_config_is_clean_error(tmp_path):
    bad = tmp_path / "str.yaml"
    bad.write_text("just a plain string\n", encoding="utf-8")
    code, out, err = run_cli("catalog", "list", "--config", str(bad))
    assert_clean_failure(code, out, err)
    assert "mapping" in err


def test_cli_garbage_schedule_time_is_clean_error(tmp_path):
    cfg = make_config(tmp_path)
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
    code, out, err = run_cli(
        "post", "schedule", "--config", cfg,
        "--platform", "tiktok", "--media", str(media),
        "--caption", "hi", "--when", "not-a-time",
    )
    assert_clean_failure(code, out, err)
    assert "Bad time" in err or "ISO-8601" in err


def test_cli_schedule_missing_media_is_clean_error(tmp_path):
    cfg = make_config(tmp_path)
    code, out, err = run_cli(
        "post", "schedule", "--config", cfg,
        "--platform", "tiktok", "--media", str(tmp_path / "nope.mp4"),
        "--caption", "hi", "--when", "2026-10-10T19:00",
    )
    assert_clean_failure(code, out, err)
    assert "not found" in err.lower()


def test_cli_scan_missing_dir_is_clean_error(tmp_path):
    cfg = make_config(tmp_path)
    code, out, err = run_cli("catalog", "scan", "/definitely/not/here",
                             "--config", cfg)
    assert_clean_failure(code, out, err)


def test_cli_unknown_command_is_clean_error():
    code, out, err = run_cli("frobnicate")
    assert_clean_failure(code, out, err)


def test_cli_missing_required_arg_is_clean_error():
    code, out, err = run_cli("chat", "approve")  # draft id required
    assert_clean_failure(code, out, err)


def test_cli_weird_unicode_and_empty_args(tmp_path):
    cfg = make_config(tmp_path)
    for args in (
        ["catalog", "list", "--config", cfg, "--query", "💕\x00weird"],
        ["chat", "queue", "--config", cfg],
    ):
        code, out, err = run_cli(*args)
        assert "Traceback" not in out + err, args


# ---------------------------------------------------------------------------
# 2. vault adversarial cases
# ---------------------------------------------------------------------------

def _unlocked_vault(tmp_path: Path, password: str = "correct-horse"):
    from forge.vault.store import Vault
    return Vault.init(str(tmp_path / "vault"), password)


def test_vault_wrong_password_unlock(tmp_path):
    from forge.vault.store import Vault, VaultLockedError
    v = _unlocked_vault(tmp_path)
    v.lock()
    with pytest.raises(VaultLockedError):
        v.unlock("wrong-horse")
    # correct password still works afterwards
    v.unlock("correct-horse")
    v.put("ok", b"1")
    assert v.get("ok") == b"1"


def test_vault_truncated_blob_raises_vault_error(tmp_path):
    from forge.vault.store import Vault, VaultError
    v = _unlocked_vault(tmp_path)
    v.put("t", b"hello")
    enc = next((tmp_path / "vault" / "data").glob("*.enc"))
    enc.write_bytes(enc.read_bytes()[:5])  # shorter than the 12-byte nonce
    with pytest.raises(VaultError):
        v.get("t")


def test_vault_corrupt_session_missing_key(tmp_path):
    from forge.vault.store import Vault, VaultLockedError
    v = _unlocked_vault(tmp_path)
    (tmp_path / "vault" / ".session").write_text(
        json.dumps({"expires": 9999999999}), encoding="utf-8")
    with pytest.raises(VaultLockedError):
        v.put("x", b"data")


def test_vault_corrupt_session_bad_hex(tmp_path):
    from forge.vault.store import Vault, VaultLockedError
    v = _unlocked_vault(tmp_path)
    (tmp_path / "vault" / ".session").write_text(
        json.dumps({"key": "zzzz-not-hex", "expires": 9999999999}),
        encoding="utf-8")
    with pytest.raises(VaultLockedError):
        v.get("nope")


def test_vault_bundle_wrong_password_and_truncation(tmp_path):
    from forge.vault.bundle import make_bundle, open_bundle, BundleError
    blob = make_bundle({"a.txt": b"secret"}, "pw123")
    files, _ = open_bundle(blob, "pw123")
    assert files["a.txt"] == b"secret"
    with pytest.raises(BundleError):
        open_bundle(blob, "wrong")
    with pytest.raises(BundleError):
        open_bundle(blob[:10], "pw123")
    with pytest.raises(BundleError):
        open_bundle(b"total garbage", "pw123")


# ---------------------------------------------------------------------------
# 3. catalog adversarial images
# ---------------------------------------------------------------------------

def _png_with_ihdr(width: int, height: int) -> bytes:
    def chunk(ctype: bytes, data: bytes) -> bytes:
        c = ctype + data
        return struct.pack(">I", len(data)) + c + struct.pack(
            ">I", zlib.crc32(c) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IEND", b""))


def test_catalog_corrupt_and_empty_images_survive(tmp_path):
    from forge.catalog.scanner import scan_one_file, image_dimensions
    from forge.catalog.store import CatalogStore
    store = CatalogStore(tmp_path / "c.db")
    try:
        corrupt = tmp_path / "corrupt.jpg"
        corrupt.write_bytes(os.urandom(2048))
        assert image_dimensions(corrupt) == (None, None)
        assert scan_one_file(corrupt, store) is not None  # still cataloged

        empty = tmp_path / "empty.png"
        empty.write_bytes(b"")
        assert image_dimensions(empty) == (None, None)
        assert scan_one_file(empty, store) is not None

        texty = tmp_path / "text.webp"
        texty.write_text("this is not an image" * 100, encoding="utf-8")
        assert scan_one_file(texty, store) is not None
    finally:
        store.close()


def test_catalog_decompression_bomb_header_no_oom(tmp_path):
    """A PNG claiming gigapixel dimensions must not allocate or crash."""
    from forge.catalog.scanner import scan_one_file, image_dimensions
    from forge.catalog.store import CatalogStore
    store = CatalogStore(tmp_path / "c.db")
    try:
        bomb = tmp_path / "bomb.png"
        bomb.write_bytes(_png_with_ihdr(100000, 100000))
        dims = image_dimensions(bomb)  # must return, not explode
        assert dims == (None, None) or dims == (100000, 100000)
        assert scan_one_file(bomb, store) is not None
    finally:
        store.close()


# ---------------------------------------------------------------------------
# 4. approval queue races (direct + through the dashboard)
# ---------------------------------------------------------------------------

def _draft_kwargs(i: int = 0) -> dict:
    return {"platform": "fansly", "sender": f"user{i}",
            "incoming": "hey", "reply": "hello!", "trigger": "greeting"}


def test_approval_queue_concurrent_add_unique_ids():
    from forge.chat.engine import ApprovalQueue
    q = ApprovalQueue()
    n_threads, per_thread = 8, 25
    barrier = threading.Barrier(n_threads)

    def worker(k):
        barrier.wait()
        for i in range(per_thread):
            q.add(**_draft_kwargs(k * per_thread + i))

    threads = [threading.Thread(target=worker, args=(k,))
               for k in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ids = [d.id for d in q.all()]
    assert len(ids) == n_threads * per_thread
    assert len(set(ids)) == len(ids), "duplicate draft ids under concurrency"


def test_approval_queue_approve_reject_race_single_winner():
    """Racing approve vs reject: exactly one decision wins, no exceptions leak."""
    from forge.chat.engine import ApprovalQueue
    q = ApprovalQueue()
    n = 16
    barrier = threading.Barrier(n)
    outcomes: list[str] = []
    lock = threading.Lock()

    def worker(k):
        barrier.wait()
        try:
            if k % 2:
                q.approve(1)
                res = "approved"
            else:
                q.reject(1)
                res = "rejected"
        except (ValueError, KeyError):
            res = "lost"
        with lock:
            outcomes.append(res)

    q.add(**_draft_kwargs())
    threads = [threading.Thread(target=worker, args=(k,)) for k in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert outcomes.count("approved") + outcomes.count("rejected") == 1
    assert q.get(1).status in ("approved", "rejected")


def _dash_client(tmp_path: Path):
    """Fresh dashboard app state + a TestClient (one per thread)."""
    import forge.dashboard.app as dash_app
    from fastapi.testclient import TestClient
    from forge.config import ForgeConfig
    dash_app.init_state(ForgeConfig({}), tmp_path / "dash.db")
    return TestClient(dash_app.app), dash_app


def test_dashboard_concurrent_approve_single_winner(tmp_path):
    client, dash_app = _dash_client(tmp_path)
    q = dash_app._state["engine"].queue
    q.add(**_draft_kwargs())
    n = 12
    barrier = threading.Barrier(n)
    codes: list[int] = []
    lock = threading.Lock()

    def worker():
        from fastapi.testclient import TestClient
        import forge.dashboard.app as da
        c = TestClient(da.app)
        barrier.wait()
        r = c.post("/chat/approve/1")
        with lock:
            codes.append(r.status_code)

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert codes.count(200) == 1, f"expected exactly one winner, got {codes}"
    assert codes.count(400) == n - 1
    assert q.get(1).status == "approved"


def test_dashboard_concurrent_catalog_reads_no_500(tmp_path):
    from forge.catalog.scanner import scan_one_file
    client, dash_app = _dash_client(tmp_path)
    store = dash_app._state["store"]
    img = tmp_path / "a.jpg"
    img.write_bytes(os.urandom(512))
    stop = threading.Event()
    errors: list[BaseException] = []

    def reader():
        from fastapi.testclient import TestClient
        import forge.dashboard.app as da
        c = TestClient(da.app)
        while not stop.is_set():
            try:
                r = c.get("/catalog")
                assert r.status_code == 200
            except BaseException as e:  # noqa: BLE001
                errors.append(e)
                stop.set()

    def writer():
        for i in range(30):
            p = tmp_path / f"w{i}.jpg"
            p.write_bytes(os.urandom(256))
            scan_one_file(p, store)

    rt = threading.Thread(target=reader)
    wt = threading.Thread(target=writer)
    rt.start()
    wt.start()
    wt.join()
    stop.set()
    rt.join()
    assert not errors, f"dashboard errors under concurrent catalog writes: {errors[:2]}"


def test_dashboard_bad_draft_id_handled(tmp_path):
    client, _ = _dash_client(tmp_path)
    r = client.post("/chat/approve/424242")  # nonexistent
    assert r.status_code == 400
    r = client.post("/chat/approve/notanint")  # not an int
    assert r.status_code == 422
    r = client.post("/chat/sent/424242")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# 5. scheduler: garbage times + overlapping jobs
# ---------------------------------------------------------------------------

def test_scheduler_rejects_garbage_times(tmp_path):
    from forge.post.schedule import Scheduler
    s = Scheduler(tmp_path / "s.db")
    try:
        for bad in ("garbage", "", "2026-13-99", "tomorrow-ish", "10/10/2026"):
            with pytest.raises(ValueError):
                s.schedule_packet(platform="x", packet_dir="/tmp",
                                  scheduled_for=bad)
    finally:
        s.close()


def test_scheduler_concurrent_schedule_and_due(tmp_path):
    from forge.post.schedule import Scheduler
    s = Scheduler(tmp_path / "s.db")
    n_threads, per_thread = 8, 25
    barrier = threading.Barrier(n_threads + 2)
    errors: list[BaseException] = []

    def worker(k):
        try:
            barrier.wait()
            for i in range(per_thread):
                s.schedule_packet(
                    platform="tiktok", packet_dir=f"/tmp/p{k}-{i}",
                    scheduled_for="2026-10-10T19:00:00",
                    title=f"job {k}-{i}")
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    def reader():
        try:
            barrier.wait()
            for _ in range(50):
                s.due()
                s.list()
                s.upcoming()
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    threads = ([threading.Thread(target=worker, args=(k,))
                for k in range(n_threads)]
               + [threading.Thread(target=reader) for _ in range(2)])
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    try:
        assert not errors, f"scheduler errors under concurrency: {errors[:2]}"
        assert s.count() if hasattr(s, "count") else len(s.list()) == \
            n_threads * per_thread
    finally:
        s.close()


def test_scheduler_overlapping_mark_and_delete(tmp_path):
    """Concurrent mark/delete on the same post: consistent, no leaked errors."""
    from forge.post.schedule import Scheduler
    s = Scheduler(tmp_path / "s.db")
    try:
        row = s.schedule_packet(platform="x", packet_dir="/tmp",
                                scheduled_for="2026-10-10T19:00:00")
        pid = row["id"]
        n = 10
        barrier = threading.Barrier(n)
        marked: list[str] = []

        def marker():
            barrier.wait()
            r = s.mark(pid, "done")
            marked.append(r["status"])

        threads = [threading.Thread(target=marker) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert marked == ["done"] * n
        assert s.get(pid)["status"] == "done"

        # delete race: exactly one wins, the rest get KeyError
        barrier2 = threading.Barrier(n)
        wins = 0
        lock = threading.Lock()

        def deleter():
            nonlocal wins
            barrier2.wait()
            try:
                s.delete(pid)
                with lock:
                    wins += 1
            except KeyError:
                pass

        threads = [threading.Thread(target=deleter) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert wins == 1
    finally:
        s.close()
