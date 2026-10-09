# Spicy chat mode — how it works, and its honest limits

Spicy mode is the flirty/dirty-talk side of the chat helper, built from
the creator's own requests: AI-drafted flirty replies, paid "rates",
tip upsells, and pic triage so she doesn't have to stare at everything
fans send.

## The consent gate (non-negotiable)

Spicy mode is locked behind the identity pack's consent **scope**. The
scope text must contain one of: `spicy`, `adult chat`, `explicit`,
`dirty talk`, `sexting`, `findom`. Without it, every spicy command
refuses with an error telling her exactly what to do (sign a new
statement covering it, then `forge identity create` again).

This is enforced in code (`forge/chat/spicy.py::require_spicy_consent`),
not just docs. The gate covers: spicy drafts, spicy templates, the
rates flow, and findom lines.

## Tiers: playful → teasing → explicit

- Each conversation has a "heat" tier. It starts at `playful` (or
  `chat.spicy.default_tier` in forge.yaml).
- **Only she changes the tier** (`forge chat spicy-tier` or the Spicy
  screen in the app). The bot never escalates on its own, no matter what
  the fan writes.
- Templates live in `./forge-data/chat-spicy-templates.json` and are
  fully editable. The **explicit tier ships empty** — placeholder text
  she must replace with her own words. CreatorForge ships no explicit
  copy, ever.

## Drafts, not sends

Spicy drafts go through the **same approval queue** as everything else.
The spicy engine never auto-approves — even on platforms where she
opted into auto-send for normal chat, spicy drafts stay pending. She
reads every line before it goes out.

## Monetization flows

**Paid "rates"** — when a fan asks for a rating, the bot drafts a
playful scorecard (confidence / lighting / creativity, clearly a bit,
not a real judgment) plus a tip upsell pointing at her payment links.
`forge chat spicy-draft --platform X --sender Y --text "rate me"`.

**Tip requests** — "how much for a custom?" drafts a reply naming the
item, price, and her Cash App (from `pay` config). Prices come from her
tip menu / orders price menu — the bot never invents prices.

**Findom-lite (strictly opt-in)** — off by default. She writes every
line herself under `chat.spicy.findom_lines` in forge.yaml and sets
`chat.spicy.findom_enabled: true`. Nothing ships pre-written. Every
findom reply still goes through the approval queue.

## Incoming pic triage — honest scope

`forge chat triage-add --platform X --sender Y --media pic.jpg`:

1. Stores the pic with a **heavily blurred thumbnail** (Pillow
   Gaussian blur + pixelation; falls back to a gray placeholder if the
   file can't be read).
2. Queues it for her one-tap **approve / skip** — in the dashboard,
   the mobile Triage tab, or `forge chat triage-approve/skip`.
3. Drafts a "got your pic babe" auto-reply into the approval queue
   (never auto-sent; text configurable at `chat.triage.auto_reply`).

What it is: **pre-screening assistance**. What it is not: AI vision that
understands content. An `NSFWClassifier` adapter interface
(`forge/chat/triage.py`) exists so a real classifier can be plugged in
later via `register_classifier()` — with none configured (the default),
every item is manual review and the UI says so.

## Style matching

Spicy drafts use her text-style profile when one exists (built with
`forge chat style-build`, consent-gated): the engine mirrors her emoji
habits lightly. It never rewrites her template words — it's a garnish,
not a ghostwriter.

## Commands

- `forge chat spicy-templates list|add|delete --tier playful|teasing|explicit`
- `forge chat spicy-tier --platform X --sender Y --tier teasing`
- `forge chat spicy-draft --platform X --sender Y --text "..."`
- `forge chat triage-add/list/approve/skip`
- Dashboard: Triage + Spicy sections; mobile: Triage + Spicy tabs.
