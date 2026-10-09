# Platform capabilities (honest table)

| Platform | What CreatorForge can do | How | What it CANNOT do |
|---|---|---|---|
| Reddit | Post text/image/video via the official API | `forge post reddit` (PRAW). Dry-run by default; needs a Reddit script app | Bypass subreddit rules or rate limits |
| Snapchat | Prepare media + caption + checklist; open share intents | `forge post packet --platform snapchat` (manual assist) | Post via API -- **no public posting API exists**. Automation risks a permanent ban |
| OnlyFans | Content calendar CSV, posting packets, tip menu page | `forge post packet --platform onlyfans`, dashboard | Post or message via API -- **no public API exists**. Bot DMs violate ToS |
| TikTok / Instagram | Posting packets + calendar | `forge post packet` | Official posting APIs are limited/partner-only; not included |
| Discord / Telegram / Zapier | Send via incoming webhook | `forge post/webhook.py`, `platforms.webhook_url` | Anything beyond what the webhook accepts |
| Chat/inbox (any platform) | Draft replies into an approval queue; human approves | `forge chat draft/approve/sent`, dashboard queue | Auto-send is OFF by default. Opt-in per platform with a warning; you are responsible for ToS compliance |
| Spicy chat (flirty/dirty-talk) | Tiered reply templates + rates/tip monetization flows, approval-queued | `forge chat spicy-*`, Spicy mobile tab | **Consent-gated**: needs spicy scope in her identity pack. Explicit tier ships empty -- she writes it. Bot never escalates tiers alone; spicy drafts are never auto-approved |
| Incoming pic triage | Blurred-thumbnail queue, one-tap approve/skip, drafted auto-reply | `forge chat triage-*`, Triage mobile tab | NOT AI vision -- pre-screening assistance only. Optional NSFW classifier adapter interface; none configured by default |
| HeyGen / D-ID live avatar | REAL streaming-avatar sessions via their APIs | `forge live start --provider heygen\|did` | Needs YOUR paid API key. Never simulated. WebRTC client needed to view/drive the stream |
| OBS virtual camera (free) | Looped talking-head clip as a fake webcam w/ green-screen option | `forge live start --provider local-guide`, docs/LIVE.md | Looped clip, not reactive. Can't hold a conversation |
| VoIP (TextNow etc.) | Call checklist + session logging; optional AI-voice intros via her cloned voice | docs/LIVE.md | Manual phone apps -- CreatorForge cannot automate them; automation claims would be lies |
| Tube sites: Pornhub, XVideos, XNXX, xHamster, RedTube, YouPorn | Upload packets: per-site title, description, auto-tags + step-by-step checklist; bulk packets for folders x sites | `forge tube packet` / `forge tube bulk`, `/tube/*` endpoints | **No auto-upload -- none of these sites offer a public upload API** (verified 2026-10-09). She publishes in each site's own dashboard from a verified account; automation tools get accounts banned |

## Tube-site uploads (honest breakdown)

Verified 2026-10-09: none of the major tubes offer a public upload API
for regular creators. Pornhub only accepts uploads from verified Model
Program / content partners; xHamster only from verified members or
producers. "Auto-upload" third-party tools are ban bait.

So `forge tube` doesn't pretend to post for her -- it does the part
that actually eats her time: per-site titles, descriptions, and
auto-tags, plus a checklist for each site's own upload page.

| Site | Upload | Verified account? | Tag limit | Pays via |
|---|---|---|---|---|
| Pornhub | manual dashboard | yes (Model Program) | 20 | ad-revenue share |
| XVideos | manual dashboard | yes | 15 | per-view partner program |
| XNXX | manual dashboard | yes | 15 | per-view partner program |
| xHamster | manual dashboard | yes (members/producers) | 10 | ad-revenue share |
| RedTube | manual dashboard | yes | 20 | partner revenue share |
| YouPorn | manual dashboard | yes | 20 | partner revenue share |

## Chat bot honesty

- The engine **drafts** replies. Nothing sends itself unless you
  explicitly enable `chat.auto_send` for a platform in forge.yaml, and
  even then every draft is logged.
- For platforms with no messaging API (Snapchat, OnlyFans), "sending"
  means YOU copy the approved reply into the app and run
  `forge chat sent <id>` to log it.
- Keyword triggers are dumb pattern matches, not intelligence. Review
  drafts before approving -- especially anything about prices, customs,
  or boundaries.

## Spicy livestream platforms (AFK avatar)

| Platform | What works | CreatorForge does | Won't do / risk |
|---|---|---|---|
| Chaturbate | RTMP ingest via OBS; official Apps & Bots API for tip apps | Session tracking, avatar pipeline, setup guide | AFK avatar = **HIGH ban risk**; expects live performer |
| Stripchat | RTMP ingest via OBS | Session tracking, setup guide | No chat API (manual chat); AFK avatar = **HIGH ban risk** |
| BongaCams | RTMP ingest via OBS | Session tracking, setup guide | No chat API; AFK avatar = **HIGH ban risk** |
| CamSoda | RTMP ingest via OBS | Session tracking, setup guide | No chat API; AFK avatar = **HIGH ban risk** |
| ManyVids (MV Live) | RTMP ingest via OBS | Session tracking, setup guide | No chat API; AFK avatar = **MEDIUM-HIGH risk** |
| MyFreeCams | RTMP ingest via OBS | Session tracking, setup guide | No chat API; AFK avatar = **HIGH ban risk** |
| Fansly Live | RTMP ingest | Session tracking, setup guide | No API; **MEDIUM** (own account, gray area) |
| OnlyFans Live | Via creator dashboard | Session tracking, setup guide | No API; **MEDIUM** (own account, gray area) |

Details + per-platform setup: docs/STREAMING.md. `forge stream go-live`
requires her explicit ToS-risk confirmation; CreatorForge cannot protect
the account.
