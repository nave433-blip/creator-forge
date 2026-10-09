"""Profile export/import: move a whole CreatorForge setup between machines.

``export_profile`` gathers settings + persona configs + identity packs +
chat templates + style profile + prompt library into ONE encrypted
bundle (password-protected, same crypto as the vault). ``import_profile``
unpacks it into a folder.

Deliberately EXCLUDED: the vault itself (secrets stay separate -- move
them with ``forge vault backup`` if you must), the media catalog
(point the new machine at the same media or re-scan), and any API keys
left in forge.yaml are YOUR responsibility -- the bundle is encrypted,
but treat the password like a password.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.config import ForgeConfig
from forge.vault.bundle import (
    BundleError,
    collect_dir,
    open_bundle,
    write_bundle_file,
)


def _data_dir(config: ForgeConfig) -> Path:
    return Path(config.get_path("data_dir", "./forge-data"))


def export_profile(config: ForgeConfig, out_path: str | Path,
                   password: str) -> Path:
    """Export settings + persona + packs + templates as an encrypted bundle."""
    data_dir = _data_dir(config)
    cfg_path = config.get_path("_config_path")
    files: dict[str, bytes] = {}

    if cfg_path and Path(cfg_path).is_file():
        files["settings/forge.yaml"] = Path(cfg_path).read_bytes()

    persona_path = config.get_path("chat.persona_path", "./persona.yaml")
    if persona_path and Path(persona_path).is_file():
        files["persona/persona.yaml"] = Path(persona_path).read_bytes()

    packs_dir = config.get_path("identity.packs_dir", "./identity-packs")
    files.update(collect_dir(packs_dir, "identity-packs"))

    for name in ("chat-templates.json", "promptlib.json",
                 "style-profile.json"):
        p = data_dir / name
        if p.is_file():
            files[f"data/{name}"] = p.read_bytes()

    # identity-pack.yaml at the old default location, if that's what's used
    legacy = config.get_path("identity.pack_path")
    if legacy and Path(legacy).is_file():
        files[f"identity-packs/{Path(legacy).name}"] = \
            Path(legacy).read_bytes()

    if not files:
        raise BundleError("Nothing to export: no config, packs, or "
                          "templates found. Run `forge init` first.")
    meta = {"kind": "creatorforge-profile", "version": 1}
    return write_bundle_file(files, out_path, password, meta)


def import_profile(bundle_path: str | Path, dest_dir: str | Path,
                   password: str) -> dict[str, Any]:
    """Unpack an exported profile bundle into ``dest_dir``.

    Returns {"restored": [relative paths]}. Nothing is overwritten
    without the files simply being written -- back up anything precious
    first.
    """
    files, meta = open_bundle(Path(bundle_path).read_bytes(), password)
    if meta.get("kind") != "creatorforge-profile":
        raise BundleError("This bundle is not a CreatorForge profile "
                          "export (maybe it's a vault backup?).")
    dest = Path(dest_dir)
    restored: list[str] = []
    for name, data in files.items():
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        restored.append(name)
    return {"restored": restored, "count": len(restored)}
