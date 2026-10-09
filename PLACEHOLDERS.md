# PLACEHOLDERS.md — steps that need a human, and what the code does meanwhile

Standing rule (Evan, 2026-10-09): whenever the app needs manual work from
him or from her — API keys, logins, paid memberships, installs on their
machines, decisions only they can make — the code must **not** stall
waiting. Every such step gets a clearly-marked placeholder below, and the
code either degrades gracefully (clean error naming the exact fix) or
ships a working replacement. Everything stays green and shippable around
the placeholders.

Sourcing rule (Evan, 2026-10-09): when a new capability is needed, prefer
borrowing an established open-source tool over building from scratch.
Permissive licenses (MIT / Apache-2.0 / BSD) are preferred. If the best
option is GPL/LGPL, it is **not** vendored silently — it is flagged below
for his call. License files and notices are always kept intact.

Privacy: no real names appear in this repo, including here.

---

## Active placeholders

### 1. AI provider keys (Grok / Gemini / Claude) — HER
- **She does:** paste a key into `forge.yaml` under `ai:` (see
  `forge/examples/forge.yaml`) or set `XAI_API_KEY` / `GEMINI_API_KEY` /
  `ANTHROPIC_API_KEY`.
- **Until then:** `forge ai ...` prints a clean one-line setup error that
  names the key and points at the free fallback. Nothing fakes AI output.
- **Working replacement (shipped):** `forge ai caption|titles|hashtags|`
  `ideas|scene-ideas|polish|promo|reply-assist --local` — honest
  template-based drafts assembled from her word bank, labeled
  `local template draft (not AI-generated)` (`forge/ai/local.py`).
- **OSS upgrade path (not built — needs his install):** local LLM via
  [Ollama](https://ollama.com) (MIT license) as a future `--provider
  ollama` backend. Requires him to install Ollama and pull a model
  (~4–8 GB) on the machine running `forge`. Flagged, not stalled on.

### 2. Video generation backend (Replicate / fal.ai / local ComfyUI) — HER (+ HIM for local GPU)
- **They do:** add a Replicate or fal.ai key, *or* install ComfyUI
  locally with a GPU (see `docs/VIDEO.md` for real GPU/time expectations).
- **Until then:** `forge video generate` raises a clean
  `NotConfiguredError`. No fake output, ever.
- **No working replacement possible:** realistic video of a real person
  needs a trained LoRA + GPU or a paid API. Faking it would violate the
  honesty constraint.

### 3. ElevenLabs voice key — HER
- **She does:** add her ElevenLabs key (`voice:` in forge.yaml).
- **Until then:** `forge persona voice-clone` / `voice-speak` refuse with
  a clean `VoiceNotConfiguredError`. Consent gate stays mandatory
  regardless.

### 4. Live avatar providers (HeyGen / D-ID) — HER
- **She does:** add provider keys (`live:` in forge.yaml).
- **Until then:** `forge live start --provider local-guide` works today —
  the honest free path (talking-head clip + OBS virtual camera, with
  green-screen/chroma-key notes). `docs/LIVE.md` lists real
  latency/cost expectations.
- **OSS note:** [SadTalker](https://github.com/OpenTalker/SadTalker)
  (MIT) is stubbed as a local lip-sync adapter; it needs him to clone
  the repo + download checkpoints and set `live.sadtalker_dir`.

### 5. Reddit API credentials — HER
- **She does:** create a Reddit app (script type) and add id/secret.
- **Until then:** `forge post reddit` runs in dry-run mode only and says
  so. No posting without credentials, ever.

### 6. Expo login + EAS build (Android APK) — HIM
- **He does:** `eas login` on his machine, then the exact commands in
  `docs/MOBILE.md`.
- **Until then:** the dashboard installs as a PWA straight from the
  browser (`docs/PWA.md`) — same features, no app store.

### 7. Apple Developer membership — HIM
- **He does:** enroll ($99/yr) if iOS distribution is ever wanted.
- **Until then:** Android APK path is unaffected; iOS stays on Expo Go /
  TestFlight-via-EAS only after enrollment. Nothing in the repo pretends
  otherwise.

### 8. Dashboard API token — OPTIONAL (him or her)
- **They do:** set `dashboard.api_token` in forge.yaml (or
  `FORGE_DASHBOARD_API_TOKEN`).
- **Until then:** dashboard is open on localhost only (binds
  127.0.0.1). Docs warn not to expose it publicly without a token.

### 9. LibreTranslate endpoint (translator) — OPTIONAL
- **They do:** self-host LibreTranslate (AGPL — see note below) or point
  `chat.translator_endpoint` at a public instance.
- **Until then:** `translate()` raises clean `TranslationNotConfigured`.
- **License flag for his call:** LibreTranslate is **AGPL-3.0**.
  Self-hosting it as a separate service is fine; bundling it into this
  repo is not done. If he wants it vendored/integrated, that's his
  explicit call.

### 10. OnlyFans / Fansly / Snapchat / TikTok access — NOBODY (by design)
- **Not a placeholder to resolve:** these platforms offer no public
  posting/messaging API. Tools claiming full automation use unofficial
  access that gets accounts banned. CreatorForge stays manual-assist +
  approval-gated here permanently. Documented in `docs/PLATFORMS.md`.

### 11. Telegram bot token — HER
- **She does:** message @BotFather on Telegram, create a bot, paste the
  token into `forge.yaml` under `telegram:` (or `TELEGRAM_BOT_TOKEN`).
  Add the bot as admin to her channel (or use a numeric chat id).
- **Until then:** `forge telegram ...` prints a clean one-line setup
  error pointing at @BotFather.
- **Honest scope:** the Bot API sends announcements/media drops. It does
  not do Telegram Stars payouts or read fan DMs.

---

## Sourcing log (OSS borrowed or evaluated)

| Capability | Decision | License | Notes |
|---|---|---|---|
| Web framework (dashboard) | Borrowed: FastAPI + Starlette | MIT / BSD | Already in use |
| CLI | Borrowed: Typer | MIT | Already in use |
| Encryption | Borrowed: `cryptography` (AES-GCM, scrypt) | Apache-2.0 / BSD | Already in use |
| Images | Borrowed: Pillow | HPND (permissive) | Already in use |
| Reddit API | Borrowed: PRAW | BSD-2 | Already in use |
| Local AI drafts | Built from scratch (`forge/ai/local.py`) | — | Zero-dependency template engine was the right call; no OSS micro-lib needed. Ollama (MIT) noted above as the future upgrade path. |
| Translator backend | Not vendored | AGPL-3.0 (LibreTranslate) | Flagged in §9 for his call per the GPL rule |
| Promo-link tracking | Built from scratch (`forge/promo/tracker.py`) | — | Evaluated OSS: none worth borrowing — UTM tagging is `urllib.parse`, storage is sqlite; a micro-dependency would add risk for ~150 lines. |
| Telegram bot adapter | Built thin on httpx (`forge/telegram/bot.py`) | httpx: BSD | Evaluated the established OSS lib python-telegram-bot — it is **LGPL-3.0**. For this narrow send-only surface the thin adapter avoids the license question and keeps deps light. Revisit with his explicit call if a full conversational bot is ever wanted. |

## License hygiene
- `pyproject.toml` pins third-party deps; their licenses ship with them.
- Nothing GPL/LGPL is vendored into this repo. If that ever changes, it
  goes in the table above first, with his explicit approval.
