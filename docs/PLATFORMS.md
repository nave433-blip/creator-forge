# Platform capabilities (honest table)

| Platform | What CreatorForge can do | How | What it CANNOT do |
|---|---|---|---|
| Reddit | Post text/image/video via the official API | `forge post reddit` (PRAW). Dry-run by default; needs a Reddit script app | Bypass subreddit rules or rate limits |
| Snapchat | Prepare media + caption + checklist; open share intents | `forge post packet --platform snapchat` (manual assist) | Post via API -- **no public posting API exists**. Automation risks a permanent ban |
| OnlyFans | Content calendar CSV, posting packets, tip menu page | `forge post packet --platform onlyfans`, dashboard | Post or message via API -- **no public API exists**. Bot DMs violate ToS |
| TikTok / Instagram | Posting packets + calendar | `forge post packet` | Official posting APIs are limited/partner-only; not included |
| Discord / Telegram / Zapier | Send via incoming webhook | `forge post/webhook.py`, `platforms.webhook_url` | Anything beyond what the webhook accepts |
| Chat/inbox (any platform) | Draft replies into an approval queue; human approves | `forge chat draft/approve/sent`, dashboard queue | Auto-send is OFF by default. Opt-in per platform with a warning; you are responsible for ToS compliance |

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
