# Free-plan iPhone inbox

This is an alternative to the paid Render/Python deployment. The existing Android APK works with the same API. iPhone uses Safari, optionally Add to Home Screen; there is no native iOS application.

Uses Cloudflare Workers, static assets and D1. These have free tiers with usage/storage limits; they are not unlimited or guaranteed to remain free. Keep the account on the Free plan, do not enable paid upgrades, and review current limits in your dashboard. Exceeding a free-tier limit can interrupt delivery. No hosting account or deployment has been created by this project.

## Publish using your own account

Requires Node.js 22+ and a computer. From `cloudflare/`:

1. `npm ci` to install the pinned tools.
2. `npx wrangler login` opens Cloudflare's own browser login/authorization flow. Do not share your password or API tokens in chat.
3. `npx wrangler d1 create osaim-private-sms`. Copy the returned `database_id` into `wrangler.jsonc`, replacing `REPLACE_WITH_YOUR_D1_DATABASE_ID`.
4. `npx wrangler d1 migrations apply osaim-private-sms --remote` creates the inbox tables in your own D1 database. For this new database, accept the confirmation to apply the migration.
5. `npx wrangler secret put SMS_ADMIN_PASSWORD`. Enter a unique password of at least 16 characters in that secure prompt. Do not commit it. It is the inbox owner login, distinct from your Cloudflare password.
6. `npx wrangler deploy` publishes the Worker and web assets. Cloudflare prints its HTTPS `workers.dev` URL; no paid domain is required.
7. On iPhone, open that exact URL in Safari, sign in and create a device key. Enter that URL and key in the Android sender on each phone. Send a new test SMS and verify it on iPhone, then Share → Add to Home Screen.

If the secret prompt requires the Worker to exist first, deploy once, add the secret, then test again. Without the secret, login intentionally returns 503 and messages are not readable. Workers uploads include only `worker.mjs` and `../web`, not the private SQLite data or Android keys.

## Checks and limits

`npm test` runs the Worker in Cloudflare's local workerd runtime with a real local D1 database and synthetic SMS. It does not log passwords or OTPs. `npm run check:deploy` bundles without publishing. Successful local checks are not evidence of remote deployment or delivery from an Android handset.

SMS are stored in your Cloudflare D1 database, not end-to-end encrypted. Use a strong private password. The scheduled job deletes messages older than seven days, and inbox reads also prune them. D1's platform recovery/backups may retain deleted historical data according to Cloudflare's policies. Devices use upload-only bearer keys; revoke deletes that phone's inbox messages. Login expires after an hour. Browser writes require same-origin requests. There are no ads, analytics or third-party scripts. Android OTP and battery restrictions still apply; see the main README. Phone labels do not distinguish SIM slots in dual-SIM phones.
