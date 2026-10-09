# Live AI avatar — video calls & streams

What "live AI avatar" honestly means here, and the three ways to do it.

## Option 1: HeyGen / D-ID streaming (real-time, paid)

`forge live start --provider heygen` (or `did`) calls the provider's
**real streaming API** to open a live avatar session:

- **HeyGen** — needs `live.heygen_api_key` (+ `live.heygen_avatar_id`,
  optional `live.heygen_voice_id`) in forge.yaml. Paid plan required.
  `POST /v1/streaming.new` opens the session; you drive it with a WebRTC
  client using the returned SDP/access token.
- **D-ID** — needs `live.did_api_key` (+ `live.did_source_image`: a URL
  of her persona image). Paid plan required. `POST /talks/streams`
  opens a WebRTC stream from the source image.

Without a key, the adapters raise `LiveNotConfiguredError` — they never
fake a session. `forge live status` / `forge live stop` manage the one
active session (state in `./forge-data/live-session.json`); every
start/stop is logged to `live-calls.jsonl` for her records.

Realistic expectations: 1–3s latency is normal for streaming avatars;
you pay per minute/stream; lip-sync quality varies by provider. Test
with the provider's own web demo before spending money.

## Option 2: Local guide — talking-head clip + OBS (free)

`forge live start --provider local-guide` prints this instead of
starting anything:

1. Make or pick a **talking-head clip** of her AI persona
   (`forge video generate` with her trained persona, or a HeyGen/D-ID
   one-off render).
2. Install **OBS Studio** (free) and enable the Virtual Camera.
3. Add the clip as a Media Source, set to loop. For the "green screen"
   effect: use OBS's background removal filter, or a real green screen
   + Chroma Key filter, then put any background behind it.
4. In your VoIP app / streaming software, select **OBS Virtual Camera**
   as the camera.

Voice: run her cloned voice (`forge persona voice-speak`) through a
virtual audio cable, or just talk yourself while the avatar loops.

Honest limits: this is a **looped clip, not a reactive avatar**. Zero
latency, zero cost — but it can't respond to chat or hold a real
conversation. For reactive, you need Option 1.

## VoIP calls — honest notes

Apps like TextNow give you a second number for calls/texts, but they
are **manual phone apps** — CreatorForge does not (and cannot) automate
them, and claiming otherwise would get accounts banned. What's real:

- **Call checklist** (`forge live` logs the session; you run the app):
  1. Start your avatar (Option 1 or 2).
  2. Open your VoIP app, select OBS Virtual Camera if video.
  3. Optional: route her cloned ElevenLabs voice for intros/outros.
  4. `forge live stop` when done — the call is logged.
- **AI voice on calls**: pre-generate lines with
  `forge persona voice-speak --text "..."` (consent-gated) and play
  them through a virtual audio cable. This is manual playback, not a
  live voice-changer — anyone selling you "real-time AI voice calls
  with no latency" is overselling.
- Keep a boundary script handy (rates, what's on/off-menu, payment
  before custom). The spicy chat templates double as phone scripts.

## Commands

- `forge live start --provider heygen|did|local-guide [--api-key ...]`
- `forge live stop`
- `forge live status`
- Dashboard: `/live` (status, start, stop). Mobile: Live tab.

## Config (forge.yaml)

```yaml
live:
  heygen_api_key: ""      # x-api-key from heygen.com
  heygen_avatar_id: ""    # your avatar id
  heygen_voice_id: ""     # optional; defaults to avatar voice
  did_api_key: ""         # "key:secret" from d-id.com
  did_source_image: ""    # public URL of her persona image
```
