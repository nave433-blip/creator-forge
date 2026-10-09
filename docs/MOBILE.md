# CreatorForge Android app (Expo, thin client)

A dark, clean Android app that talks to the CreatorForge FastAPI backend
over your local network. It is a **thin client**: every screen just calls
the backend API. No keys, media, or consent packs live on the phone.

Screens: backend URL + API token setup, Catalog browser, Identity/consent
status, Chat approval queue (approve / reject / mark-sent), Payment links
viewer, Posting packets list.

## Honesty notes

- The app cannot generate videos, train models, or post to Snapchat /
  OnlyFans -- those limits live in the backend (see docs/PLATFORMS.md).
- Chat drafts are approved here, but the reply is still sent by a human
  in the platform's app ("Mark sent" only logs it).
- If the backend has `dashboard.api_token` set, the app must send the
  same token (Setup screen) or every call gets 401.

## Develop

```bash
cd mobile
npm install
npm start            # Expo dev server; open in Expo Go, or:
npm run android      # run on a connected device / emulator
```

Backend must be reachable from the phone:

```bash
# on the backend machine, on trusted home Wi-Fi only:
forge dashboard --host 0.0.0.0 --port 8765
```

Then enter `http://<backend-LAN-IP>:8765` in the app's Setup screen.

## Build an APK with EAS

You need your own Expo account + login. From `mobile/`:

```bash
npm install -g eas-cli
eas login
eas build:configure        # first time only; accepts the eas.json here
eas build -p android --profile preview
```

- `preview` profile builds an **APK** you can install directly
  (`android.buildType: apk`, `distribution: internal`).
- `production` builds an **AAB** for the Play Store.
- `development` builds a dev client.

EAS builds run in Expo's cloud; the APK download link appears in the
terminal and at expo.dev. Install it on the phone (allow "install from
this source" once) -- no Play Store needed for the preview build.

The maintainer does not produce signed APKs: signing keys and the Expo
login belong to you.

## Typecheck / lint

```bash
npm run typecheck   # tsc --noEmit
npx expo lint       # if eslint is configured
```
