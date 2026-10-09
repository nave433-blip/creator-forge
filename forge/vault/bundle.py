"""Encrypted bundles: password-protected archives for backups and profiles.

A bundle is: JSON header + AES-256-GCM ciphertext of a tar.gz payload.
The key is derived from a password with the SAME scrypt parameters as
the vault (never stored). Used by:

- ``forge vault backup``  -- vault blobs + settings + databases
- ``forge export-profile`` -- settings + persona + templates + packs
  (NOT the vault itself -- keep secrets and profile separate on purpose)

Restore/import decrypts with the same password and extracts the tar.gz.
"""

from __future__ import annotations

import base64
import io
import json
import secrets
import tarfile
import time
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

_NONCE_LEN = 12
_MAGIC = "creatorforge-bundle-v1"


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=2 ** 15, r=8, p=1)
    return kdf.derive(password.encode("utf-8"))


def make_bundle(files: dict[str, bytes], password: str,
                meta: dict | None = None) -> bytes:
    """Build an encrypted bundle.

    ``files`` maps archive-relative names (e.g. "settings/forge.yaml")
    to bytes. Returns the bundle bytes (header line + ciphertext).
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mtime = int(time.time())
            tf.addfile(info, io.BytesIO(data))
    payload = buf.getvalue()

    salt = secrets.token_bytes(32)
    nonce = secrets.token_bytes(_NONCE_LEN)
    key = _derive_key(password, salt)
    ct = AESGCM(key).encrypt(nonce, payload, None)
    header = {
        "magic": _MAGIC,
        "salt": base64.b64encode(salt).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "created": time.time(),
        "meta": meta or {},
    }
    header_line = json.dumps(header).encode("utf-8")
    return (len(header_line).to_bytes(4, "big") + header_line
            + nonce + ct)


class BundleError(Exception):
    """Bad password or corrupted bundle."""


def open_bundle(bundle: bytes, password: str) -> tuple[dict[str, bytes], dict]:
    """Decrypt a bundle. Returns (files dict, meta dict).

    Raises :class:`BundleError` on wrong password or corruption.
    """
    try:
        hlen = int.from_bytes(bundle[:4], "big")
        header = json.loads(bundle[4:4 + hlen].decode("utf-8"))
        if header.get("magic") != _MAGIC:
            raise BundleError("Not a CreatorForge bundle.")
        salt = base64.b64decode(header["salt"])
        rest = bundle[4 + hlen:]
        nonce, ct = rest[:_NONCE_LEN], rest[_NONCE_LEN:]
        key = _derive_key(password, salt)
        payload = AESGCM(key).decrypt(nonce, ct, None)
    except InvalidTag as e:
        raise BundleError(
            "Wrong password or corrupted bundle.") from e
    except BundleError:
        raise
    except Exception as e:
        raise BundleError(f"Could not read bundle: {e}") from e

    files: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            fh = tf.extractfile(member)
            if fh is not None:
                # guard against path traversal in hostile bundles
                name = member.name.lstrip("/").replace("..", "_")
                files[name] = fh.read()
    return files, header.get("meta", {})


def write_bundle_file(files: dict[str, bytes], out_path: str | Path,
                      password: str, meta: dict | None = None) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(make_bundle(files, password, meta))
    return out


def collect_dir(root: str | Path, prefix: str,
                exclude: set[str] | None = None) -> dict[str, bytes]:
    """Collect all files under ``root`` into {prefix/relpath: bytes}."""
    exclude = exclude or set()
    root = Path(root)
    files: dict[str, bytes] = {}
    if not root.is_dir():
        return files
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name in exclude or p.name.startswith("."):
            continue
        rel = p.relative_to(root).as_posix()
        files[f"{prefix}/{rel}"] = p.read_bytes()
    return files
