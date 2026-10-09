# Setup

## Requirements

- Python 3.10+
- pip

## Install

```bash
cd creator-forge
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## First run

```bash
# 1. Scaffold a project folder (copies example configs)
forge init my-project
cd my-project

# 2. Edit forge.yaml -- payment handles, Reddit creds, video backend

# 3. Create the consent pack (see docs/CONSENT.md for the form)
forge identity create --statement-file signed-consent.txt

# 4. Scan her existing content into the catalog
forge catalog scan /path/to/her/photos --tags "original"

# 5. Start the dashboard
forge dashboard
# open http://127.0.0.1:8765

# ...or the interactive menu (no flags to memorize)
forge menu
```

## Desktop app (Linux, optional)

```bash
pip install -e ".[gui]"   # adds PySide6
forge gui
```

The GUI is iOS-glass styled and covers every area: catalog, identity,
video, persona, chat approvals, posting, schedule, pay, vault,
connectors, analytics, skills, settings. Without PySide6, `forge gui`
just prints the install hint -- nothing else breaks.

### Add it to your app launcher

```bash
# 1. Copy the .desktop file
cp assets/creator-forge.desktop ~/.local/share/applications/

# 2. Install the icon (pick one; 256px is a good default)
mkdir -p ~/.local/share/icons
cp assets/icons/icon-256.png ~/.local/share/icons/creatorforge.png
#    ^ the .desktop file's Icon=creatorforge resolves to this name

# 3. Make sure `forge` is on your PATH (e.g. pipx or the venv's bin),
#    then refresh the launcher
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
```

The `.desktop` file runs `forge gui`, so `forge` must be importable
from a normal login shell. If you installed with `pip install -e` into
a venv, either put that venv's bin dir on PATH or install with
`pipx install -e .` instead.

## Restore from a backup

`forge vault backup` writes one encrypted file. To restore on the same
or a new machine:

```bash
forge vault restore --backup forge-backup.enc --dest ./forge-restore
# then copy into place:
cp -r ./forge-restore/vault/*    /path/to/your/vault/
cp ./forge-restore/data/*.db     ./forge-data/
cp ./forge-restore/data/*.json   ./forge-data/
cp ./forge-restore/settings/forge.yaml ./forge.yaml   # review first!
forge vault unlock   # confirm the password works
forge identity validate
```

Moving to a new machine without the vault? Use the lighter
`forge export-profile` / `forge import-profile` pair instead (settings
+ persona + packs + templates, no secrets).

## Configuration

`forge.yaml` is read from (in order): `--config` flag, `FORGE_CONFIG`
env var, `./forge.yaml`, `~/.config/creator-forge/forge.yaml`.

Any value can be overridden with env vars: `FORGE_<SECTION>_<KEY>`,
e.g. `FORGE_REDDIT_CLIENT_ID=...`, `FORGE_VIDEO_REPLICATE_TOKEN=...`.
Prefer env vars (or a secrets manager) for tokens -- never commit real
keys to git.

## Keys you may need (all optional; each feature degrades honestly)

| Feature | What you need | Where it goes |
|---|---|---|
| Video via Replicate | `REPLICATE_API_TOKEN` + a model version | `video.replicate_token`, `video.replicate_model_version` |
| Video via ComfyUI | Local ComfyUI at :8188 + workflow JSON loading your LoRA | `video.comfy_workflow` |
| Reddit posting | Reddit script app credentials | `platforms.reddit.*` |
| Webhook posting | An incoming webhook URL (Discord, Zapier...) | `platforms.webhook_url` |

Snapchat, OnlyFans, TikTok: no keys exist because there is no public
API -- use `forge post packet` (manual assist). See docs/PLATFORMS.md.
