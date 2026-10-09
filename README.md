# CreatorForge

![CreatorForge icon](assets/icons/icon-128.png)

An AI creator-assistant toolkit for an adult content creator: organize
her content catalog, build a consent-gated AI likeness pipeline for
realistic videos of herself, prep posts for every platform, run an
approval-gated chat helper, and share payment links -- all from one
local dashboard, a desktop app, or her phone.

## What it does

- **Catalog** -- scan folders of photos/videos into a deduplicated
  SQLite catalog (sha256 dedupe, dimensions, tags, search).
- **Identity + consent gate** -- her likeness is protected by a signed
  consent record. The video pipeline *refuses to run* without it.
  Multi-persona: keep several packs, switch the active one, version
  them (v1, v2…) as terms change.
- **AI video** -- dataset prep + LoRA training configs from her catalog,
  then generation through real backends you configure (Replicate API or
  your local ComfyUI). Nothing is faked; unconfigured backends raise
  clear errors instead of fake output. Batch queue for running many
  generations; finished clips get watermarked/resized via skills and
  imported back into the catalog tagged `ai_generated`.
- **Posting** -- Reddit posts via the official API (dry-run by default);
  manual-assist posting packets (media + caption + checklist) for
  Snapchat, OnlyFans, TikTok; generic webhooks for the rest.
- **Scheduler** -- schedule packets for future times; `forge post due`
  tells her what's ready to post. Reminders, not auto-posting (those
  platforms have no API -- anyone claiming otherwise is lying).
- **Chat helper** -- keyword triggers draft replies into an approval
  queue. Per-conversation modes (auto / approve-first / manual), a worker
  with pluggable inbox adapters, canned response templates, escalation
  flags that highlight messages needing her eyes, tip-menu auto-replies,
  and a text-style profiler that learns how she writes from her own
  exported chats (consent-gated, encrypted). A human approves every
  reply; auto-send is off unless you explicitly opt a platform in.
- **Spicy chat** -- consent-gated flirty/dirty-talk mode: tiered
  templates (playful → teasing → explicit; tiers only change when SHE
  sets them), paid "rates" flow (funny scorecard + tip upsell), tip
  requests with her real prices, opt-in findom-lite lines she writes
  herself. Spicy drafts are never auto-approved. Incoming pics get
  **triage**: blurred thumbnails with one-tap approve/skip so she
  doesn't have to open everything (pre-screening help, not AI vision).
- **Custom video orders** -- fans order from her price menu; comfort
  boundaries enforced (refused categories can't be ordered); orders flow
  pending_payment → queued → rendering → awaiting_review → delivered,
  and she reviews the finished video before anything is delivered.
- **Live AI avatar** -- real HeyGen/D-ID streaming sessions (her paid
  API keys; never faked) or the free path: talking-head clip + OBS
  virtual camera with green-screen option. Honest VoIP notes (manual
  phone apps, call checklist, optional AI-voice intros).
- **Payments** -- Venmo/Cash App/PayPal/crypto/Throne/custom links plus
  a standalone tip-menu HTML page.
- **Scene director** -- scene templates resolved against her `comfort`
  boundary: self-filmed categories use real footage, AI-only categories
  generate with her persona model, anything uncategorized is refused.
- **Voice persona** -- consent-gated voice cloning via ElevenLabs
  (your key) with notes on the local XTTS alternative.
- **Encrypted vault** -- AES-256-GCM store (scrypt key, password never
  stored) for her content, transcripts, and settings. Encrypted backups
  and full profile export/import for moving machines.
- **Connectors** -- honest per-platform capability matrix; manual
  import workflows for Fansly/OnlyFans, full Reddit API where allowed.
- **Skills** -- auto-discovered plugins (`watermark`, `aspect`,
  `promptlib` built in; drop in your own `.py` file to add more).
- **Analytics** -- log earnings and post stats (manual or CSV import),
  live Reddit stats via the official API, plain-English reports,
  **LTV/ARPU** from recorded earnings + CRM fan count, and **peak
  posting-time** insights from her own data.
- **Fan CRM** -- per-platform fan profiles: tags, timestamped notes,
  lifetime spend, statuses, smart lists (whales/new/active/expired/
  quiet/online), and a rules-based buyer-intent score (heuristic, shown
  with its reasons -- not ML).
- **Mass DMs** -- compose once, personalize per fan, get per-platform
  send packets. Reddit via API where configured; OnlyFans/Fansly/
  Snapchat are always manual-assist (no messaging API exists).
- **PPV upsell triggers** -- buying-intent keywords draft an offer from
  her price menu + payment links into the approval queue.
- **Message flows** -- welcome / win-back / online-nudge sequences;
  due steps draft for approval, never auto-send.
- **Humanizer** -- typo simulation, tone fixes, emoji sprinkle, and an
  optional LibreTranslate-compatible endpoint (basic MT, not pro
  quality). **Compliance checker** -- her own wordlists flag risky
  drafts before approval.
- **Content ideas** -- template remixes of her own catalog tags
  (honestly labeled, not generative AI).
- **Vault labels + no-resend guard** -- encrypted searchable labels;
  a sent-log stops PPV being sent (or charged) twice.
- **Spicy livestream (AFK)** -- honest per-platform matrix (Chaturbate,
  Stripchat, BongaCams, CamSoda, ManyVids, MyFreeCams, Fansly Live,
  OnlyFans Live): RTMP ingest via OBS, chat-API reality, verification
  requirements, and per-platform ToS risk. `forge stream go-live` runs
  her avatar pipeline (loop / SadTalker lip-sync / HeyGen / D-ID) and
  tracks the session; she confirms the risk explicitly. Most cam sites
  expect a live verified performer -- AFK avatar streaming can get the
  account banned. Full guide: docs/STREAMING.md.
- **Interfaces** -- `forge menu` (interactive TUI), `forge dashboard`
  (local FastAPI web UI, PWA-installable on Android), `forge gui`
  (Linux desktop app, iOS-glass style), and a native Expo thin-client
  Android app in `mobile/`.

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
forge menu            # friendly interactive menu -- start here
# or step by step:
forge identity create --statement-file signed-consent.txt  # see docs/CONSENT.md
forge catalog scan /path/to/her/content --tags original
forge dashboard   # http://127.0.0.1:8765
forge gui         # desktop app (needs: pip install "creator-forge[gui]")
```

Docs: `docs/SETUP.md` (install), `docs/FEATURES.md` (full capability
catalog), `docs/CONSENT.md` (consent form), `docs/VIDEO.md` (train her
persona model), `docs/PLATFORMS.md` (per-platform honesty table),
`docs/STYLE.md` (text style profiler), `docs/MOBILE.md` (Android app),
`docs/PWA.md` (install the dashboard as an app).

## Project layout

```
creator-forge/
  forge/            # the toolkit
    catalog/        # media catalog (sqlite)
    identity/       # consent-gated identity packs (multi-persona)
    persona/        # trainer registry, voice cloning
    video/          # adapters, training prep, scene director, batch queue
    post/           # reddit api, manual packets, webhooks, scheduler
    chat/           # approval engine, worker, style profiler, templates
    pay/            # payment links + tip menu
    connect/        # platform connector registry
    vault/          # AES-256-GCM encrypted store + backup bundles
    skills/         # auto-discovered plugins (watermark, aspect, promptlib)
    analytics/      # earnings + post stats, plain-English reports
    gui/            # PySide6 desktop app (optional)
    dashboard/      # FastAPI local UI (+ PWA assets)
  mobile/           # Expo React Native Android thin client
  assets/           # app icon (CF monogram) + Linux .desktop launcher
  scripts/          # train_lora.sh (GPU training wrapper)
  examples/         # forge.yaml, identity pack, persona, scene templates
  tests/            # smoke + feature tests (pytest)
  docs/             # honest guides
```

## License

MIT. You are responsible for complying with each platform's terms of
service and for labeling AI-generated content where required.
