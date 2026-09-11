# Install AEGIS Mobile from Mobile CI (recommended)

The **debug** APK from Mobile CI is the installable build (Android debug certificate).
This matches the builds that successfully install and upload screenshots.

## Steps

1. Open GitHub → **AEGIS_Platform_Server** → **Actions** → **Mobile CI**.
2. Open the latest run with a **green** check on `main`.
3. Scroll to **Artifacts** → download **`AEGIS-Mobile-installable-debug`**.
4. Unzip the artifact on your computer or phone.
5. On the phone: **uninstall** any existing AEGIS / AEGIS debug app first.
6. Install `AEGIS-Mobile-latest-debug.apk` (allow “Install unknown apps”).
7. Settings:
   - Server URL: `https://aegis-api-0z1p.onrender.com`
   - Account ID + API key from the portal
8. Start capture with MT5 chart visible.

## Package id

Debug builds use application id: `com.aegis.mobile.debug`

## Note on website APK

Website `/downloads/aegis-mobile.apk` may lag CI. Prefer the **Mobile CI artifact** for the newest code until release signing is fully wired.
