# CreatorForge — full capability catalog (v0.3.0)

Plain-English list of everything CreatorForge can do, and the honest
limits of each. If a feature isn't listed here, it doesn't exist.

## Getting around

| Interface | Command | Best for |
|---|---|---|
| Interactive menu | `forge menu` | Beginners -- every command, no flags to memorize |
| Desktop app | `forge gui` | Linux desktop, point-and-click (needs `pip install "creator-forge[gui]"`) |
| Web dashboard | `forge dashboard` | Browser UI at http://127.0.0.1:8765, PWA-installable on Android |
| Android app | `mobile/` (Expo) | Phone thin-client talking to the dashboard backend |
| Terminal | `forge <command>` | Scripting, automation |
| Docker | `docker compose up` | Normal Windows laptop, no Python needed (see `docs/DOCKER.md`) |

## Content catalog

- `forge catalog scan <folder>` -- index photos/videos (sha256 dedupe,
  dimensions, tags, search). Re-scanning never duplicates.
- `forge catalog list [--kind] [--query]` -- browse/search.
- AI-generated outputs are imported back automatically, tagged
  `ai_generated`.

## Identity & consent (the hard gate)

- `forge identity create` -- build a pack from her **signed** consent
  statement (template in `docs/CONSENT.md`).
- `forge identity validate` -- check a pack. Tampered statement =
  invalid, always.
- `forge identity list` / `use` / `new-version` -- **multi-persona**:
  several packs, one active, versioned (v1 -> v2…) as terms change.
- Video, voice-clone, voice-speak, and style-profile **refuse** without
  a valid pack. This is enforced in code, not just docs.

## AI video

- `forge video generate --prompt "..."` -- consent-gated generation
  via Replicate (your API key) or local ComfyUI (your GPU). Unconfigured
  backend = clear error, never fake output.
- `forge video scene --scene scene.yaml` -- the **scene director**:
  resolves each scene against her `comfort` boundary (self-filmed vs
  AI-only categories). Uncategorized = refused, and every decision is
  logged.
- `forge video queue-add` / `queue-run` / `queue-list` -- batch queue;
  each job consent-gated; failures recorded honestly.
- `video.postprocess` in forge.yaml -- run skills over finished clips,
  e.g. watermark + 9:16 resize, before they're cataloged.
- `forge video prep-dataset` / `write-kohya-config` -- build a LoRA
  training dataset + config from her catalog (see `docs/VIDEO.md` for
  real GPU/time expectations).
- `forge persona trainers` -- honest registry of trainer options
  (kohya, diffusers, Replicate, fal.ai, ComfyUI) with docs, costs, GPU
  needs.
- `forge persona voice-clone` / `voice-speak` -- ElevenLabs voice
  cloning, consent-gated (scope must mention voice).

## Posting & scheduling

- `forge post reddit` -- real Reddit API via PRAW. **Dry-run by
  default**; `--live` actually posts. Test in your own subreddit first.
- `forge post packet` -- manual-assist packet (media + caption +
  hashtags + checklist) for Snapchat / OnlyFans / TikTok / Fansly.
  **They have no posting API.** She taps "post" in the app; automation
  risks permanent bans.
- `forge post schedule` / `scheduled` / `due` / `mark-done` -- schedule
  packets, see what's due, mark done. Reminders, not auto-posting.

## Chat helper

- `forge chat draft` -- draft a reply into the approval queue.
- `forge chat queue` / `approve` / `reject` / `sent` -- the human
  workflow. Nothing sends itself.
- `forge chat mode` -- per-conversation: `approve-first` (default),
  `manual` (bot stays silent), `auto` (explicit opt-in, logged, with
  warning).
- `forge chat worker [--once]` -- poll an inbox adapter and draft.
  Adapters are honest about realtime/poll/manual.
- `forge chat template-add/list/use/delete` -- canned replies with
  `{sender}` placeholders.
- **Escalation flags** -- keyword lexicon (anger, refund/chargeback,
  legal, self-harm, platform-risk) highlights drafts needing her eyes.
  Not ML, not sentiment AI -- just keywords, and it says so.
- **Tip-menu auto-replies** -- `chat.tip_menu_replies: true` answers
  "what's your menu?" from her configured tip menu.
- `forge chat style-build` / `style-report` -- learns how SHE texts
  from her exported chats (consent-gated, encrypted). Produces a
  human-readable report she can review and edit.
- **Custom word bank** (`forge chat lexicon-add/list/remove/import/export`,
  dashboard `/chat/lexicon`, also in `forge menu`) -- her saved dictionary:
  slang, signature phrases, pet names, go-to emoji, openers, closers, plus
  a spicy-only shelf (gated like spicy chat). Custom entries beat the
  learned profile when drafting. `lexicon-adopt` promotes words the style
  profiler found into the bank for her review. Templates can use
  {pet_name} {phrase} {slang} {emoji} {opener} {closer} placeholders.
- Also in the Linux GUI (Word bank screen) and the Android app (Words
  tab): add/remove words from her phone.

## Spicy chat (her request — consent-gated)

- Locked behind consent scope: the identity pack's scope must mention
  spicy/adult chat or every spicy command refuses (full gate in
  `docs/SPICY.md`).
- **Tiered templates** -- playful → teasing → explicit
  (`forge chat spicy-templates list|add|delete`). The explicit tier
  ships empty; she writes every line. Tiers only change when SHE sets
  them (`forge chat spicy-tier`) -- the bot never escalates alone.
- **Spicy drafts** (`forge chat spicy-draft`) go through the same
  approval queue and are never auto-approved, even on auto-send
  platforms.
- **Paid "rates"** -- fan asks for a rating → funny scorecard draft +
  tip upsell with her payment links.
- **Tip-request triggers** -- "how much for a custom?" → reply with
  item, price (from HER menu, never invented), and Cash App link.
- **Findom-lite** -- strictly opt-in (`chat.spicy.findom_enabled`),
  she writes every line herself in forge.yaml; still approval-queued.
- **Pic triage** (`forge chat triage-add/list/approve/skip`) --
  fan-sent pics queued with blurred thumbnails for one-tap approve/skip,
  plus a drafted (never auto-sent) "got your pic" reply. Honest scope:
  pre-screening assistance, not AI vision; an `NSFWClassifier` adapter
  interface lets her plug a real classifier in later.

## Custom video orders

- `forge orders scenes` -- scene templates annotated with comfort
  decisions (what fans may actually order).
- `forge orders create --fan X --scene scene.yaml` -- refused outright
  if the scene hits a comfort boundary (refused categories can't be
  ordered, period).
- Full state machine: `pay` → `render` → `review` → `approve`/`deliver`,
  plus `cancel`/`refund`. Illegal transitions are refused with the
  allowed list.
- `render` enqueues a real consent-gated video job; `review` only
  passes when the job finished; **she sees the finished video before
  anything is delivered**.
- Price menu from `orders.price_menu` (falls back to `pay.tip_menu`).

## Live AI avatar

- `forge live start --provider heygen|did` -- REAL streaming-API
  sessions (her keys; `LiveNotConfiguredError` without them, never
  faked). `forge live stop` / `status`; sessions logged.
- `forge live start --provider local-guide` -- the honest free path:
  talking-head clip + OBS virtual camera (+ green-screen/chroma key).
- `docs/LIVE.md` -- real latency/cost expectations, VoIP honesty
  (TextNow-style apps are manual; call checklist included), optional AI
  voice intros via her cloned voice.

## Payments

- `forge pay links` -- Venmo, Cash App, PayPal.me, BTC/ETH, Throne,
  custom URLs from forge.yaml.
- `forge pay tip-menu` -- standalone shareable tip-menu HTML page.

## Vault & backups

- `forge vault init/unlock/lock/import/export/list` -- AES-256-GCM
  encrypted store; scrypt key; password never stored.
- `forge vault save-settings` / `load-settings` -- forge.yaml encrypted
  in the vault.
- `forge vault backup` -- ONE encrypted file with vault blobs +
  settings + databases. `forge vault restore` unpacks it.
  **Without the password the backup is useless -- by design.**

## Connectors

- `forge connect list` -- honest per-platform matrix:
  - Reddit: full import/export via official API (PRAW).
  - Fansly / OnlyFans: **manual** -- she exports from the site, we
    ingest the files. There is no public API; tools claiming otherwise
    get accounts banned.
  - Snapchat / TikTok: manual-assist posting only.
  - Filesystem / URL: full import.
- `forge connect import --platform … --source …`

## Skills (plugins)

Auto-discovered from `forge/skills/builtin/` + `skills.paths`:

- `watermark` -- text watermark on images (Pillow).
- `aspect` -- resize/crop to 9:16, 4:5, 1:1, 16:9 (Pillow for images;
  ffmpeg for video if installed, honest error if not).
- `promptlib` -- save/list/reuse video prompt templates with
  `{variables}`.
- Write your own: drop a `.py` file with a `SKILL` object in a skills
  dir. `forge skills list` / `forge skills run <name>`.

## Analytics

- `forge analytics log-post` -- manual per-post stats (views/likes/
  comments/earnings). OnlyFans/Fansly/Snapchat have no stats API, so
  manual entry (or CSV) is the only honest way.
- `forge analytics log-earning` / `import-earnings` -- money per
  platform/month.
- `forge analytics reddit-stats <id>` -- **live** Reddit stats via the
  official API, saved locally too.
- `forge analytics report` -- plain-English summary: totals, best
  platforms, top posts, and where every number came from.

## Profile portability

- `forge export-profile` -- settings + persona + packs + templates as
  ONE encrypted bundle. The vault is deliberately excluded (move
  secrets separately).
- `forge import-profile` -- unpack on a new machine.

## Tube sites (manual-assist uploads)

- `forge tube sites` -- honest capability matrix (all manual; verified
  accounts required; none offer a public upload API).
- `forge tube metadata --site pornhub` -- preview title/description/tags.
- `forge tube packet --video clip.mp4 --site xvideos` -- one upload
  packet: title.txt, description.txt, tags.txt, checklist.md with the
  site's upload URL and tips.
- `forge tube bulk --dir ./clips --sites pornhub,xvideos,xnxx` --
  packets for a whole folder x many sites + manifest CSV.
- `--template 0-3` picks the title template; the GUI shows all four.
- Metadata engine: title templates (per-site length limits), descriptions
  with her payment links baked in, auto-tags (her custom tags > catalog
  tags > curated taxonomy matched from the scene), per-site tag limits.
  When a site's tag cap cuts tags, you get a warning telling you to put
  the strongest tags first in `--tags`.
- Also in the Linux GUI (Tube screen) and the Android app (Tube tab).

## Public AI providers (Grok / Gemini / Claude)

- `forge ai providers` -- which backends have keys (never leaks keys).
- `forge ai ask|caption|titles|hashtags|ideas|scene-ideas|polish|promo` --
  writing help; everything returned is a **draft** for her review.
- `forge ai reply-assist --incoming "..."` -- two reply options; add
  `--platform` + `--sender` to drop it in the approval queue.
- Needs HER paid API keys (`ai:` in forge.yaml or XAI_API_KEY /
  GEMINI_API_KEY / ANTHROPIC_API_KEY). No key = clear setup error,
  never a fake answer. Full doc: `docs/AI.md`.

## Mobile (Android)

Expo thin client in `mobile/`: Setup, Chat approvals (with escalation
flags), **Triage** (one-tap pic approve/skip), **Spicy** (templates,
drafts, tier control), **Orders** (custom video pipeline),
**Live** (avatar session control), Schedule (due reminders), Canned
replies, Analytics, Catalog, Packets, Pay links, Consent status. Talks
to `forge dashboard` over your network. Build the APK with EAS (needs
your Expo login) -- `docs/MOBILE.md` has the exact commands. The
dashboard also installs as a PWA straight from the browser
(`docs/PWA.md`).

## What it honestly can't do

- No trained AI model ships with it. Realistic video of a real person
  needs a LoRA trained on her content with a GPU (or paid API).
- No auto-posting to Snapchat / OnlyFans / Fansly / TikTok (no APIs).
- The chat helper drafts; it doesn't log into her accounts or send DMs.
- No money moves through CreatorForge; payment links are just links.
- Stats for platforms without APIs are only as fresh as your manual
  entries.
- The live avatar is a real provider session (paid) or a looped OBS
  clip -- never a fake "AI video call" with zero latency.
- Triage blurs and queues; it does not understand images.

## Fan CRM (new)

Fan profiles per platform: tags, timestamped notes, lifetime spend,
purchase/message counts, statuses (new/active/expired/vip). Smart lists:
whales, new, active, expired, quiet (30d+ silent), online (she tags).
Buyer-intent is a **rules-based** 0–100 score with its reasons shown —
a heuristic, not a prediction model. Fan records come from what she
enters (`forge crm ...`) or imports from CSV exports she downloads from
each site — the app cannot see inside the platforms. Per-fan reply/spend
stats for her own review (`forge crm stats`).

## Mass DMs (new)

`forge post massdm` composes once, personalizes per fan
({handle}/{first}/{spend}), and builds per-platform send packets. Reddit
can send via the real API where configured; OnlyFans/Fansly/Snapchat
are **always manual-assist** (copy/paste checklist) — no messaging API
exists and automating risks her account. Dry-run by default; optional
scheduler reminder (never auto-sends).

## PPV upsell triggers (new)

`forge chat ppv` watches for buying intent ("how much", "ppv", ...) and
drafts an offer from her price menu + payment links into the approval
queue. Never auto-sends.

## Message flows (new)

Welcome, win-back, and online-nudge sequences (`forge chat flows`).
Enroll a fan; due steps are drafted into the approval queue — nothing
auto-sends, ever. Same rule as the rest of chat: auto mode is an
explicit per-conversation opt-in.

## Humanizer + translator (new)

Draft post-processing: typo simulation (configurable intensity),
lowercase/tone fixes, emoji sprinkle from her style, plus an optional
LibreTranslate-compatible endpoint for basic machine translation
(honestly labeled — not professional quality). She still approves every
draft.

## Compliance checker (new)

Her own wordlists (`chat.compliance` in forge.yaml): banned terms,
regex patterns (e.g. off-platform links), must-review topics. Flags
drafts before approval in CLI, dashboard, and mobile. A dumb wordlist
matcher — it catches what she tells it to catch.

## Content ideas (new)

`forge content ideas`: template remixes of her own catalog tags +
caption templates + hashtag sets. Honestly labeled as remix, not
generative AI.

## LTV / ARPU + peak posting times (new)

`forge analytics ltv`: lifetime value and average revenue per user from
recorded earnings ÷ CRM fan count, with median spend and top-10%
concentration. `forge analytics peak-times`: best weekday/hour slots
from her recorded post stats (says so when the sample is thin). All
figures reflect only what she logged.

## Vault labels + no-resend guard (new)

Encrypted, searchable labels on vault blobs; plus a sent-log so PPV
content is never sent (or charged) twice to the same fan
(`forge vault check-sent`).

## Spicy livestream — AFK avatar (new)

`forge stream`: honest per-platform matrix (Chaturbate, Stripchat,
BongaCams, CamSoda, ManyVids, MyFreeCams, Fansly Live, OnlyFans Live)
with RTMP ingest notes, chat-API reality, verification requirements,
and per-platform ToS risk. `go-live` runs her avatar pipeline (loop /
SadTalker lip-sync / HeyGen / D-ID) and tracks the session; OBS does
the actual RTMP ingest with her stream key. She must explicitly confirm
the ToS risk — most cam sites expect a live verified performer and
AFK-avatar streaming can get the account banned. Full guide:
docs/STREAMING.md.
