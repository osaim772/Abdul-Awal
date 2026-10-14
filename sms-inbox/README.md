# Personal SMS inbox — prototype

Separate project: this does not change the existing OSAIM website. Only connect Android phones you own, with explicit consent on each phone. No phone-number lookup is used: the installed sender receives new SMS on that Android phone and uploads them to your private inbox. The iPhone opens the inbox in Safari and can add it to its Home Screen.

## Current status

Python server and browser inbox are functionally tested with synthetic SMS. The Android debug APK has been compiled successfully and its APK signature verified. Android lint completed successfully with remaining translation warnings (no errors). It has **not** been tested on a physical device. There is no public deployment or verified delivery of actual OTPs yet. Do not use this prototype as the sole way to access important codes.

## Free hosting option

The tested Cloudflare Workers + D1 version is in `cloudflare/`. Its API works with the existing Android APK. See `cloudflare/README.md` for free-plan limits and account setup. Local Worker/D1 tests and a deploy dry-run passed; the Cloudflare account is not authenticated here and nothing has been deployed. This version avoids the paid Render plan.

## Server

Requires Python 3.12+. No Python packages required. Set these privately in your deployment environment; do not commit their values:

- `SMS_ADMIN_PASSWORD`: unique, at least 16 characters, for the inbox owner.
- `SMS_PUBLIC_ORIGIN`: exact HTTPS origin, for example `https://inbox.example.com`.
- Optional `SMS_DATA_DIR`: private persistent directory; defaults to `data/`.
- Optional `SMS_PORT`: defaults to 8080.

From this directory run `python3 server.py`. It binds only to `127.0.0.1`. Place it behind an HTTPS reverse proxy forwarding to that loopback port. The server requires a real TLS certificate; cleartext Android connections are disabled. This repository does not provision hosting, a domain, or the reverse proxy. Keep the service running through your hosting provider's process manager. Never expose it through plain HTTP. Do not log request bodies or Authorization headers in the proxy. SQLite contains SMS in plaintext at rest: protect the host, directory and disk; this is **not end-to-end encryption**.

Verify the public inbox opens over HTTPS, unauthenticated `/api/inbox` returns 401, and login works before connecting a phone. Retain this existing checkout; no Git worktree is needed. `python3 -m unittest test_server.py -v` validates authenticated ingestion, duplicate protection, access revocation, CSRF checks and session logout.

## Android sender

Use Android Studio with JDK 17, Android SDK 35 and Gradle 8.11.1. Open `android/`, sync, and build the debug APK (`gradle :app:assembleDebug` when that Gradle version is installed). A Gradle wrapper is not provided. A separately downloadable debug APK is available as `Osaim-SMS-debug.apk`; it is for initial testing, not a production store release. Manifest targets Android 15 and supports Android 8+.

1. Log into the HTTPS inbox on iPhone. Create a device key and label under “Android ফোন যুক্ত করুন”. The key is displayed once and is only valid for uploading, not reading the inbox.
2. Install the Android sender on the SIM phone. Enter the HTTPS origin and its device key. Confirm ownership and forwarding consent, then grant Receive SMS permission.
3. Send a real test SMS to that SIM. Keep the Android phone online; refresh the sender status and iPhone inbox. Verify sender, full multipart text and timestamp.
4. Test offline arrival and reconnection, a phone reboot, permission denial and device revocation. Test separately on every intended handset and Android version before relying on it.

Android restricts SMS permission and OTP access on some versions/devices. Sideloading may require allowing a restricted permission, and Google Play restricts SMS-permission apps; store approval is not established. Newer Android protections may hide OTPs from ordinary apps. Manufacturer battery management and JobScheduler can delay delivery. Some banks may not deliver usable codes this way. Real OTP forwarding is unverified, not guaranteed. iMessage, WhatsApp and app-generated authentication codes are outside this SMS receiver.

The prototype labels messages by **phone**, not SIM slot or verified phone number. A dual-SIM phone forwards incoming SMS under one phone label. It does not import older SMS. The sender stores pending SMS in its app-private database, retries network failures, and deletes expired queued messages after seven days during upload processing. Stop disables forwarding, removes the local key and deletes queued SMS. Revoke in the inbox invalidates a phone's key and deletes its server messages. Messages expire from the server after seven days during ingestion/inbox requests; backups must have their own retention controls.

The inbox shows the most recent 200 messages, refreshes every 15 seconds while visible, and expires login after an hour. No push notifications or offline SMS caching are implemented. It has no ads or third-party scripts. Credentials and messages are not printed by the server.

## Before deployment

Test the built Android APK, verify real-device SMS/OTP access, select private HTTPS hosting, configure secrets securely, and review host/disk security. This is a starting implementation, not a deployed or production-audited service.
