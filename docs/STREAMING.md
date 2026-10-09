# Spicy Livestreaming with CreatorForge

How to stream her AI persona to cam platforms, what each platform
allows, and the honest risks. Read the risk notes **before** going live.

## The honest architecture

CreatorForge does **not** stream to platforms itself. The chain is:

```
avatar source -> OBS Studio -> RTMP ingest -> platform
```

- **Avatar source**: a looped AI-persona clip (`forge video generate`),
  a SadTalker lip-sync render (`forge live start --provider sadtalker`),
  or a real-time streaming avatar (HeyGen / D-ID, paid).
- **OBS Studio** (free): takes the avatar output, sends it to the
  platform via RTMP using the stream key from her **verified**
  broadcaster dashboard.
- **CreatorForge** tracks the session (`forge stream go-live` /
  `stop` / `status`), drives the avatar side, and logs everything.

"AFK mode" = the avatar loop plays while she's away. A loop **cannot**
react to chat. Only a real-time streaming provider (HeyGen/D-ID) can
respond live, and even then chat automation only works where the
platform allows it (Chaturbate's official Apps API).

## Platform matrix (verified 2026-10-09; verify again before going live)

| Platform | RTMP ingest | Chat API | Verification | AFK-avatar ToS risk |
|---|---|---|---|---|
| Chaturbate | yes (OBS) | official Apps & Bots API | 18+, ID | **HIGH** — expects live performer; tip bots via official API are fine |
| Stripchat | yes (OBS) | none — manual chat | 18+, ID | **HIGH** — live-performer expectation |
| BongaCams | yes (OBS) | none — manual chat | 18+, ID | **HIGH** |
| CamSoda | yes (OBS) | none — manual chat | 18+, ID | **HIGH** |
| ManyVids (MV Live) | yes (OBS) | none — manual chat | 18+, ID | **MEDIUM-HIGH** |
| MyFreeCams | yes (OBS) | none — manual chat | 18+, ID (female-identifying models) | **HIGH** |
| Fansly Live | yes | none | creator verification | **MEDIUM** — own account, gray area |
| OnlyFans Live | via creator dashboard | none | creator verification | **MEDIUM** — own account, gray area |

**The rule on every cam site**: they verify a real human broadcaster
and expect that human live. Streaming an AI avatar while AFK can get
the account flagged or banned. CreatorForge prints the per-platform
risk at `go-live` and requires her explicit confirmation — it cannot
protect the account for her.

## Setup per platform

1. Get verified as a broadcaster on the platform (ID + age check).
2. Open the broadcaster/streaming dashboard, copy the **RTMP URL**
   and **stream key**. Treat the key like a password.
3. Put them in `forge.yaml`:
   ```yaml
   stream:
     chaturbate_rtmp: "rtmp://..."
     chaturbate_key: "..."   # or STREAM_CHATURBATE_KEY env var
   ```
   (Keys are `stream.<platform>_key` / `stream.<platform>_rtmp` for
   `chaturbate`, `stripchat`, `bongacams`, `camsoda`, `manyvids`,
   `myfreecams`, `fansly-live`, `of-live` — dashes as shown.)
4. In OBS: Settings → Stream → Custom, paste server + key.
5. `forge stream go-live --platform chaturbate --avatar loop
   --avatar-source ./persona-loop.mp4 --i-understand-the-risk`
6. Follow the printed checklist, then Start Streaming in OBS.

## Avatar modes

- `loop` — simplest and most honest: a video file looped in OBS.
  Make it with `forge video generate` from her trained persona.
- `sadtalker` — lip-synced clip from a portrait + voiceover audio.
  Needs a local SadTalker install + NVIDIA GPU (see docs/LIVE.md).
- `heygen` / `did` — real-time streaming avatar (paid APIs, her keys).
  The only mode that can react to chat live.

## Chat during AFK streams

- **Chaturbate**: official Apps & Bots API allows tip-triggered apps
  (tip menus, games). Set those up in the broadcaster dashboard —
  that's the sanctioned path.
- **Everywhere else**: no chat API exists. Chat is manual in the
  site's UI. CreatorForge can draft replies from a copied chat log
  (`forge chat draft`), but it cannot read or post to these chats.

## What CreatorForge will NOT do

- It will not fake a "live" badge or viewer counts.
- It will not circumvent verification or impersonate a different
  verified performer.
- It will not auto-chat on platforms with no chat API and claim it
  did.
