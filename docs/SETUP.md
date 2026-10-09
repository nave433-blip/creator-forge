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
```

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
