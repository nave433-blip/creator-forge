"""AES-256-GCM encrypted local vault.

- Key derived from a password with scrypt (never stored; the password is
  never written to disk).
- Each blob is stored as ``<name>.enc`` = 12-byte nonce + AES-GCM
  ciphertext. Names are sanitized to a safe alphabet.
- ``unlock()`` verifies the password against a stored verifier and writes
  a session file (0600, expires after ``session_minutes``). Honest
  tradeoff: while unlocked, the derived key sits in a root-only-readable
  file on the same machine -- convenient, not hardware-security-module
  grade. ``lock()`` deletes it.

Layout::

    <vault>/
      vault.json        # salt, scrypt params, verifier, version
      data/<name>.enc   # encrypted blobs
      .session          # present only while unlocked
"""

from __future__ import annotations

import base64
import json
import os
import re
import secrets
import time
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

VAULT_VERSION = 1
_NONCE_LEN = 12
_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$")


class VaultError(Exception):
    """Generic vault failure."""


class VaultLockedError(VaultError):
    """Raised when an operation needs an unlocked vault."""


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=n, r=r, p=p)
    return kdf.derive(password.encode("utf-8"))


class Vault:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.meta_path = self.path / "vault.json"
        self.data_dir = self.path / "data"
        self.session_path = self.path / ".session"
        if not self.meta_path.is_file():
            raise VaultError(
                f"No vault at {self.path}. Run `forge vault init` first.")
        self.meta = json.loads(self.meta_path.read_text(encoding="utf-8"))

    # -- setup -----------------------------------------------------------
    @classmethod
    def init(cls, path: str | Path, password: str,
             session_minutes: int = 30) -> "Vault":
        p = Path(path)
        if (p / "vault.json").exists():
            raise VaultError(f"Vault already exists at {p}.")
        p.mkdir(parents=True, exist_ok=True)
        (p / "data").mkdir(exist_ok=True)
        salt = secrets.token_bytes(32)
        n, r, pp = 2 ** 15, 8, 1
        key = _scrypt(password, salt, n, r, pp)
        vnonce = secrets.token_bytes(_NONCE_LEN)
        verifier = vnonce + AESGCM(key).encrypt(
            vnonce, b"creatorforge-vault", None)
        meta = {
            "version": VAULT_VERSION,
            "salt": base64.b64encode(salt).decode(),
            "scrypt": {"n": n, "r": r, "p": pp},
            "verifier": base64.b64encode(verifier).decode(),
            "session_minutes": session_minutes,
            "created": time.time(),
        }
        (p / "vault.json").write_text(json.dumps(meta, indent=2),
                                      encoding="utf-8")
        vault = cls(p)
        vault._write_session(key, session_minutes)
        return vault

    # -- sessions ----------------------------------------------------------
    def _derive(self, password: str) -> bytes:
        salt = base64.b64decode(self.meta["salt"])
        sc = self.meta["scrypt"]
        return _scrypt(password, salt, sc["n"], sc["r"], sc["p"])

    def _write_session(self, key: bytes, minutes: int | None = None) -> None:
        minutes = minutes if minutes is not None else self.meta.get(
            "session_minutes", 30)
        payload = {"key": key.hex(), "expires": time.time() + minutes * 60}
        self.session_path.write_text(json.dumps(payload), encoding="utf-8")
        os.chmod(self.session_path, 0o600)

    def unlock(self, password: str) -> None:
        key = self._derive(password)
        verifier = base64.b64decode(self.meta["verifier"])
        nonce, ct = verifier[:_NONCE_LEN], verifier[_NONCE_LEN:]
        try:
            if AESGCM(key).decrypt(nonce, ct, None) != b"creatorforge-vault":
                raise VaultLockedError("Wrong password.")
        except InvalidTag as e:
            raise VaultLockedError("Wrong password.") from e
        self._write_session(key)

    def lock(self) -> None:
        try:
            self.session_path.unlink()
        except FileNotFoundError:
            pass

    def _key(self) -> bytes:
        try:
            payload = json.loads(self.session_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise VaultLockedError(
                "Vault is locked. Run `forge vault unlock` first.") from e
        if payload.get("expires", 0) < time.time():
            self.lock()
            raise VaultLockedError("Vault session expired. Unlock again.")
        return bytes.fromhex(payload["key"])

    # -- blobs ---------------------------------------------------------------
    def _blob_path(self, name: str) -> Path:
        if not _NAME_RE.match(name):
            raise VaultError(
                f"Bad blob name {name!r}: use letters, digits, . _ -")
        return self.data_dir / (name + ".enc")

    def put(self, name: str, data: bytes) -> None:
        key = self._key()
        nonce = secrets.token_bytes(_NONCE_LEN)
        ct = AESGCM(key).encrypt(nonce, data, None)
        self._blob_path(name).write_bytes(nonce + ct)

    def get(self, name: str) -> bytes:
        key = self._key()
        raw = self._blob_path(name).read_bytes()
        nonce, ct = raw[:_NONCE_LEN], raw[_NONCE_LEN:]
        try:
            return AESGCM(key).decrypt(nonce, ct, None)
        except InvalidTag as e:
            raise VaultError(f"Blob {name!r} failed integrity check.") from e

    def list(self) -> list[str]:
        self._key()  # ensure unlocked
        return sorted(p.name[:-4] for p in self.data_dir.glob("*.enc"))

    def delete(self, name: str) -> None:
        self._key()
        self._blob_path(name).unlink(missing_ok=True)

    # -- settings (encrypted JSON) -------------------------------------------
    def put_json(self, name: str, obj: object) -> None:
        self.put(name, json.dumps(obj, indent=2).encode("utf-8"))

    def get_json(self, name: str) -> object:
        return json.loads(self.get(name).decode("utf-8"))

    # -- labels (encrypted blob metadata) ----------------------------------
    # Labels live in the encrypted "_labels" blob: {blob_name: [labels]}.
    # Nothing about the labels is visible without the vault password.

    def _load_labels(self) -> dict[str, list[str]]:
        try:
            data = self.get_json("_labels")
            return {k: list(v) for k, v in data.items()} \
                if isinstance(data, dict) else {}
        except Exception:
            return {}

    def set_labels(self, blob: str, labels: list[str]) -> list[str]:
        """Replace the label set for a blob. Returns the new labels."""
        all_labels = self._load_labels()
        clean = sorted({str(l).strip() for l in labels if str(l).strip()})
        all_labels[blob] = clean
        self.put_json("_labels", all_labels)
        return clean

    def get_labels(self, blob: str) -> list[str]:
        return self._load_labels().get(blob, [])

    def blobs_by_label(self, label: str) -> list[str]:
        labels = self._load_labels()
        return sorted(b for b, ls in labels.items() if label in ls)

    def search(self, query: str) -> list[dict[str, str | list[str]]]:
        """Search blob names + labels (case-insensitive)."""
        q = query.lower()
        out = []
        for blob in self.list():
            labels = self.get_labels(blob)
            if q in blob.lower() or any(q in l.lower() for l in labels):
                out.append({"blob": blob, "labels": labels})
        return out

    # -- sent log (no-resend guard) ----------------------------------------
    # "_sent" blob: {blob_name: [fan handles it already went to]}.
    # Check before re-sending PPV so nobody gets (or is charged for)
    # the same content twice.

    def _load_sent(self) -> dict[str, list[str]]:
        try:
            data = self.get_json("_sent")
            return {k: list(v) for k, v in data.items()} \
                if isinstance(data, dict) else {}
        except Exception:
            return {}

    def log_sent(self, blob: str, fan: str) -> list[str]:
        """Record that a blob was sent to a fan. Returns the fan list."""
        sent = self._load_sent()
        fans = sent.get(blob, [])
        if fan not in fans:
            fans.append(fan)
        sent[blob] = fans
        self.put_json("_sent", sent)
        return fans

    def sent_to(self, blob: str) -> list[str]:
        return self._load_sent().get(blob, [])

    def already_sent(self, blob: str, fan: str) -> bool:
        """True if this fan already got this blob -- don't resend."""
        return fan in self.sent_to(blob)
