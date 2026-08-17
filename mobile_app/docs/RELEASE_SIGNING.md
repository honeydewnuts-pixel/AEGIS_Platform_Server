# AEGIS Mobile — signed release builds

## What is already wired

- `app/build.gradle.kts` loads signing from:
  - **Local:** `mobile_app/keystore.properties` (see `keystore.properties.example`)
  - **CI:** environment variables (GitHub Actions secrets)
- **Mobile CI** always builds **debug**.
- If release secrets are present, CI also runs **`assembleRelease`** and uploads `aegis-mobile-release`.

Without secrets, release assemble is skipped (debug still works).

---

## One-time: create the keystore (on your PC)

```bash
mkdir -p ~/aegis-secrets
keytool -genkey -v \
  -keystore ~/aegis-secrets/aegis-release.jks \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -alias aegis
```

Back up `aegis-release.jks` offline. Losing it blocks updates under the same app signature.

---

## Local signed release

```bash
cd mobile_app
cp keystore.properties.example keystore.properties
# Edit keystore.properties: storeFile, passwords, alias

./gradlew assembleRelease
# Output: app/build/outputs/apk/release/app-release.apk
```

Copy to portal path if desired:

```bash
cp app/build/outputs/apk/release/app-release.apk ../release/aegis-mobile.apk
```

Then commit **only** the APK under `release/` (if you ship via Render), **never** the keystore.

---

## GitHub Actions secrets (for automated release)

Repo → **Settings → Secrets and variables → Actions** → add:

| Secret | Value |
|--------|--------|
| `AEGIS_KEYSTORE_BASE64` | `base64 -w0 aegis-release.jks` (Linux) or `base64 -i aegis-release.jks` (macOS) |
| `AEGIS_KEYSTORE_PASSWORD` | keystore password |
| `AEGIS_KEY_ALIAS` | e.g. `aegis` |
| `AEGIS_KEY_PASSWORD` | key password |

Then:

1. **Actions → Mobile CI → Run workflow**
2. Download artifact **`aegis-mobile-release`**
3. Optionally replace `release/aegis-mobile.apk` and redeploy Render

---

## Encode keystore for the secret

```bash
base64 -w0 ~/aegis-secrets/aegis-release.jks > keystore.b64
# paste contents of keystore.b64 into AEGIS_KEYSTORE_BASE64
```

---

## Play Store later

Prefer `./gradlew bundleRelease` → upload the **.aab** to Play Console.
Use the same keystore (or Play App Signing upload key) for updates.
