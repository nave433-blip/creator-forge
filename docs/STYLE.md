# Text style: teaching the bot to sound like her

The chat helper drafts replies. By default they sound like the persona
template. The **style profiler** learns how *she* actually writes from
her own exported chat history, so drafts come out in her voice.

## The honesty rules

1. **Her data only.** The transcript must be chats SHE exported herself
   (from her apps' export features). Never scrape someone else's
   messages, and never feed in conversations she didn't agree to share.
2. **Consent-gated.** Building a profile requires her valid identity
   pack -- same gate as face/voice. No pack, no profile.
3. **Stored encrypted.** Keep the transcript and profile in the vault
   (`forge vault import`), not lying around as plaintext.
4. **She reviews it.** `forge chat style-report` prints a human-readable
   report (top emojis, her words, openers/closers). She edits anything
   that doesn't sound like her before the bot uses it.

## How to export chats

- **Telegram:** open the chat > ⋮ > Export chat history (JSON).
- **WhatsApp:** chat > ⋮ > More > Export chat (email yourself the .txt;
  convert to JSON -- timestamps become `ts`).
- **Discord:** use the "Download chat history" feature or a
  user-authorized export tool.
- **OnlyFans / Fansly / Snapchat DMs:** these apps don't offer clean
  exports. Copy the conversations she wants to teach from into the
  transcript format below by hand, or skip style training for those.

Convert to this JSON shape (a list):

```json
[
  {"sender": "them", "text": "hey how are you", "ts": 1728400000},
  {"sender": "her", "text": "heyy im good wbuu 💕", "ts": 1728400060},
  {"sender": "them", "text": "what are your prices", "ts": 1728400100},
  {"sender": "her", "text": "menu is on my page babe, lmk what u want 💋", "ts": 1728400200}
]
```

`sender` is `"her"` (messages SHE wrote -- the only ones analyzed) or
`"them"`. `ts` is a unix timestamp or null.

## Build and review

```bash
# encrypt the transcript first
forge vault import chats.json --name chats-export

# build the profile (consent-gated), store encrypted in the vault too
forge chat style-build --transcript chats.json --pack identity-pack.yaml \
  --vault ./forge-data/vault --out style-profile.json

# read what it learned -- she reviews/edits this
forge chat style-report --profile style-profile.json
```

## What gets learned

- **Lexicon/slang:** her most common non-stopword tokens ("wbuu",
  "lmk", "babe"...).
- **Emoji habits:** what fraction of her messages use emoji, and which
  ones top the list.
- **Sentence length:** average words per message.
- **Openers/closers:** how she starts ("heyy", "hey babe") and ends
  ("lmk 💋", "ttyl") messages.
- **Response latency:** median seconds between their message and her
  reply (only if timestamps are present).

## How drafts use it

`draft_in_style()` applies the profile *lightly*: her most common
closer if the draft lacks it, her top emoji at roughly her observed
rate. It does not rewrite sentences or invent slang -- the human still
reviews every draft in the approval queue. If the style ever feels off,
re-run `style-report`, edit the JSON, and rebuild.
