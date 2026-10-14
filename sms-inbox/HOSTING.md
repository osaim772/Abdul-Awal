# Free hosting option

For the selected free workflow, use `cloudflare/README.md`. Cloudflare Workers + D1 have bounded free tiers. The following paid Render option is optional and is not required.

# iPhone inbox hosting

Hosting has not been created or paid for. This is a prepared deployment configuration, not a live service.

One option is Render with a persistent disk. `render.yaml` requests a **paid Starter service and disk**; review the provider's current price before approving deployment. Free ephemeral storage is unsuitable for retaining SMS, device keys and sessions across deployments.

1. Upload this entire project (not just the APK) to a new **private** GitHub repository. Keep `data/`, environment files and Android build outputs excluded.
2. Create or sign into a Render account. Create a Blueprint from that repository, review the plan and disk costs, and enter a unique `SMS_ADMIN_PASSWORD` of at least 16 characters through Render's secure environment settings. Do not send the password in chat.
3. Render supplies `RENDER_EXTERNAL_URL`, which this server uses as its HTTPS origin. If using a custom domain, set `SMS_PUBLIC_ORIGIN` to that exact HTTPS origin. HTTPS termination is managed by Render. The configured bind address is for the provider's internal routing; the local default remains loopback.
4. Confirm the HTTPS inbox loads and that private messages cannot be read without login. Create a device key after signing in.
5. Install the Android APK on a phone you own, enable the requested SMS permission, and enter the Render HTTPS origin plus that phone's device key. Send a test SMS. Verify its text and timestamp in the iPhone inbox.
6. Open the HTTPS inbox in iPhone Safari, tap Share, then Add to Home Screen. The portrait logo will be used as its icon.

The Render blueprint has not been deployed or validated on Render. The Android APK has built successfully, but delivery has not been validated on a physical phone. If testing fails, preserve the original SMS and do not depend on forwarding for access to an account. Consult README for Android OTP restrictions and privacy/storage limitations.
