# CreatorForge

An AI creator-assistant toolkit for an adult content creator: organize
her content catalog, build a consent-gated AI likeness pipeline for
realistic videos of herself, prep posts for every platform, run an
approval-gated chat helper, and share payment links -- all from one
local dashboard.

## What it does

- **Catalog** -- scan folders of photos/videos into a deduplicated
  SQLite catalog (sha256 dedupe, dimensions, tags, search).
- **Identity + consent gate** -- her likeness is protected by a signed
  consent record. The video pipeline *refuses to run* without it.
- **AI video** -- dataset prep + LoRA training configs from her catalog,
  then generation through real backends you configure (Replicate API or
  your local ComfyUI). Nothing is faked; unconfigured backends raise
  clear errors instead of fake output.
- **Posting** -- Reddit posts via the official API (dry-run by default);
  manual-assist posting packets (media + caption + checklist) for
  Snapchat, OnlyFans, TikTok; generic webhooks for the rest.
- **Chat helper** -- keyword triggers draft replies into an approval
  queue. Per-conversation modes (auto / approve-first / manual), a worker
  with pluggable inbox adapters, and a text-style profiler that learns
  how she writes from her own exported chats (consent-gated, encrypted).
  A human approves every reply; auto-send is off unless you explicitly
  opt a platform in.
- **Payments** -- Venmo/Cash App/PayPal/crypto/Throne/custom links plus
  a standalone tip-menu HTML page.
- **Scene director** -- scene templates resolved against her `comfort`
  boundary: self-filmed categories use real footage, AI-only categories
  generate with her persona model, anything uncategorized is refused.
- **Voice persona** -- consent-gated voice cloning via ElevenLabs
  (your key) with notes on the local XTTS alternative.
- **Encrypted vault** -- AES-256-GCM store (scrypt key, password never
  stored) for her content, transcripts, and settings.
- **Connectors** -- honest per-platform capability matrix; manual
  import workflows for Fansly/OnlyFans, full Reddit API where allowed.
- **Dashboard** -- local FastAPI web UI: catalog browser, consent
  status, chat approvals, payment page. Installable as a PWA on Android,
  plus a native Expo thin-client app in `mobile/`.

## What it honestly CAN'T do

- It does **not** include a trained AI model of anyone. Realistic video
  of a real person requires training a LoRA on her content with a GPU
  (see `docs/VIDEO.md` for the real pipeline and costs).
- It can **not** auto-post to Snapchat or OnlyFans -- neither has a
  public posting API. It prepares posting packets; she taps "post".
  Automating those apps risks permanent bans.
- The chat helper **drafts** replies; it doesn't log into her accounts
  or send DMs by itself.
- No money moves through CreatorForge -- payment links are just links.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

forge init my-project && cd my-project
# edit forge.yaml, then:
forge identity create --statement-file signed-consent.txt  # see docs/CONSENT.md
forge catalog scan /path/to/her/content --tags original
forge dashboard   # http://127.0.0.1:8765
```

Docs: `docs/SETUP.md` (install), `docs/CONSENT.md` (consent form),
`docs/VIDEO.md` (train her persona model), `docs/PLATFORMS.md`
(per-platform honesty table), `docs/STYLE.md` (text style profiler),
`docs/MOBILE.md` (Android app), `docs/PWA.md` (install the dashboard as
an app).

## Project layout

```
creator-forge/
  forge/            # the toolkit
    catalog/        # media catalog (sqlite)
    identity/       # consent-gated identity packs
    persona/        # trainer registry, voice cloning
    video/          # adapters, training prep, scene director
    post/           # reddit api, manual packets, webhooks
    chat/           # approval engine, worker, style profiler
    pay/            # payment links + tip menu
    connect/        # platform connector registry
    vault/          # AES-256-GCM encrypted store
    dashboard/      # FastAPI local UI (+ PWA assets)
  mobile/           # Expo React Native Android thin client
  scripts/          # train_lora.sh (GPU training wrapper)
  examples/         # forge.yaml, identity pack, persona, scene templates
  tests/            # smoke + feature tests (pytest)
  docs/             # honest guides
```

## License

MIT. You are responsible for complying with each platform's terms of
service and for labeling AI-generated content where required.
