# Jarvis Tracker (Android)

A minimal standalone Android app whose only job is reliable background GPS
tracking for Jarvis's trip log. It does **not** replace the Jarvis voice
app (`agent-6-jarvis/static/index.html`) — that keeps handling voice, chat,
navigation, and music exactly as before. This app exists because a browser
tab cannot sustain GPS updates through screen-lock or backgrounding (e.g.
Maps/YouTube taking the foreground) for more than a few minutes, and Android
foreground services with background-location access can.

It reimplements the same distance-tracking algorithm the PWA used to run in
JavaScript (Haversine between fixes, a 3-minute gap threshold that discards
jumps instead of guessing, a 20m noise floor, debounced sends) and POSTs the
day's cumulative total to Jarvis's existing `/trip/distance` endpoint.

## Setup

1. Open this folder (`android-tracker/`) directly in **Android Studio** —
   it will offer to generate the Gradle wrapper and sync automatically. (No
   existing Android tooling elsewhere in this repo; Android Studio is the
   easiest path if you don't already have the SDK/emulator/adb set up.)
2. Connect a phone via USB with USB debugging enabled (or use an emulator,
   though a real device is needed to actually test background/locked-screen
   behavior), and hit Run.
3. In the app: enter your Jarvis Cloud Run URL and `JARVIS_PIN`, tap Save.
4. Tap "Grant location + notification permission", then "Allow background
   location" (Android 11+ may only offer "While using the app" in the
   dialog — if so, this opens the app's Settings page so you can pick
   "Allow all the time" manually), then optionally "Ignore battery
   optimizations" (helps on OEMs like Xiaomi/Samsung that aggressively kill
   background services — some of those also need a manual "autostart"
   toggle in their own settings app, which nothing here can automate).
5. Tap "Start tracking". A persistent notification confirms it's running.

## Command-line build (once Android Studio has set up the SDK once)

```bash
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## Why this app writes the GPS field alone

`agent-6-jarvis/static/index.html`'s own client-side distance tracking has
been removed — two independent clients (browser tab and this app) both
overwriting the same day's total via `/trip/distance` would let whichever
posts last silently stomp a more-complete number with a smaller one. This
app is the sole writer of `KM Travelled (GPS)` going forward; the separate
`KM Travelled (Navigated)` field (populated by `navigate_to`'s route
estimate) is untouched by any of this.
