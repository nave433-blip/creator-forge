# CreatorForge as an installable app (PWA)

The dashboard (`forge dashboard`) is a Progressive Web App: on Android
you can install it straight from Chrome with no app store and no build
step, and it gets a home-screen icon like a native app.

## Install it

1. On the machine running the dashboard, start it so it's reachable
   from your phone. Localhost won't work from the phone -- bind to your
   LAN IP:
   ```bash
   forge dashboard --host 0.0.0.0 --port 8765
   ```
   > Only do this on a trusted home Wi-Fi network, and set
   > `dashboard.api_token` in forge.yaml first (the app will ask for it).
2. On your Android phone, open Chrome and go to
   `http://<your-computer-IP>:8765`.
3. Tap the ⋮ menu → **Add to Home screen** → **Install**.
4. The Forge icon appears in your app drawer. It opens full-screen
   (standalone) like a native app.

## What the PWA includes

- `forge/dashboard/static/manifest.json` -- name, icons (192/512px),
  theme color, standalone display.
- `forge/dashboard/static/sw.js` -- a minimal service worker that
  caches the app shell (HTML/icons) for fast opens. **API calls are
  never cached**: catalog, chat queue, approvals, and payment links
  always hit the network so you never act on stale data.
- The dashboard HTML shell (`/`) registers the service worker and links
  the manifest, theme color, and touch icons.

## PWA vs. the Expo app

| | PWA (this page) | Expo app (`mobile/`, docs/MOBILE.md) |
|---|---|---|
| Install effort | None -- Add to Home screen | Build an APK with EAS |
| Works offline | App shell only; needs backend for data | Same (thin client) |
| Push notifications | Not implemented | Possible later via Expo push |
| Best for | Quick daily use on her own Wi-Fi | A polished, signed app she can keep |

Both are thin clients: all real work happens in the Python backend.
