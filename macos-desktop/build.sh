#!/usr/bin/env bash
# Build + sign AEGIS Capture DMG on macOS (requires Xcode / Swift toolchain).
#
# BUG FIXES vs. the original build.sh:
#   1. The compiled app is now actually codesigned with
#      AegisCapture.entitlements applied. Previously the entitlements
#      file existed in the repo but was never referenced anywhere, so
#      the app-sandbox/screen-capture entitlements never took effect,
#      and the resulting .app/.dmg was unsigned — Gatekeeper rejects
#      unsigned, downloaded apps on any Mac other than the one that
#      built it.
#   2. VERSION is now a parameter (env var), not hardcoded, so CI can
#      pass the release tag through to both the DMG filename and the
#      bundle's CFBundleVersion / CFBundleShortVersionString.
#   3. Optional notarization + stapling, gated on Apple credentials
#      being present in the environment. Local/dev builds without
#      those credentials still work (ad-hoc signed), they just won't
#      pass Gatekeeper on other machines until notarized.
#
# Required env vars for a fully signed + notarized release build:
#   DEVELOPER_ID_APPLICATION   - "Developer ID Application: Your Name (TEAMID)"
#                                 (identity must already be in the login/build keychain)
#   APPLE_TEAM_ID              - your Apple Developer Team ID
#   APPLE_ID                   - Apple ID used for notarization (App Store Connect API
#                                 key auth is also supported — see notarytool docs if
#                                 you prefer that over Apple ID + app-specific password)
#   APPLE_APP_SPECIFIC_PASSWORD - app-specific password for the above Apple ID
#
# If DEVELOPER_ID_APPLICATION is not set, the script ad-hoc signs
# instead (fine for local testing, NOT fine for distribution).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

APP_NAME="AEGIS_Capture"
VERSION="${VERSION:-1.0.0}"
BUILD_NUMBER="${BUILD_NUMBER:-1}"

BUILD_DIR="$ROOT/build"
APP_DIR="$BUILD_DIR/$APP_NAME.app"
CONTENTS="$APP_DIR/Contents"
MACOS="$CONTENTS/MacOS"
RES="$CONTENTS/Resources"

rm -rf "$BUILD_DIR"
mkdir -p "$MACOS" "$RES"

echo "==> Compiling Swift sources…"
swiftc -O \
  -framework SwiftUI -framework AppKit -framework Foundation -framework ScreenCaptureKit -framework CoreMedia \
  AegisCaptureApp.swift ContentView.swift config.swift CaptureService.swift TradeBridge.swift \
  -o "$MACOS/$APP_NAME"
chmod +x "$MACOS/$APP_NAME"

echo "==> Writing Info.plist…"
cp Info.plist "$CONTENTS/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$CONTENTS/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion $BUILD_NUMBER" "$CONTENTS/Info.plist"

echo "==> Copying resources…"
# Guides/EA files are optional at the packaging level — copy whichever
# exist rather than silently no-op'ing all of them, so a genuinely
# missing guide image is still visible (empty Resources dir) rather
# than masked entirely by `|| true` on every line.
copied_any_guide=false
for candidate in "Resources/mt5_color_match_guide.jpg" "guides/mt5_color_match_guide.jpg"; do
  if [ -f "$candidate" ]; then
    cp "$candidate" "$RES/"
    copied_any_guide=true
    break
  fi
done
if [ "$copied_any_guide" = false ]; then
  echo "WARNING: mt5_color_match_guide.jpg not found in Resources/ or guides/ — Color Guide button will show a missing-image message at runtime."
fi
if [ -f "mq5/AEGIS_Executor.mq5" ]; then
  cp "mq5/AEGIS_Executor.mq5" "$RES/"
else
  echo "WARNING: mq5/AEGIS_Executor.mq5 not found — it will not be bundled."
fi

echo "==> Code signing…"
if [ -n "${DEVELOPER_ID_APPLICATION:-}" ]; then
  codesign --force --deep --options runtime \
    --entitlements "$ROOT/AegisCapture.entitlements" \
    --sign "$DEVELOPER_ID_APPLICATION" \
    "$APP_DIR"
  echo "    Signed with: $DEVELOPER_ID_APPLICATION (hardened runtime, entitlements applied)"
else
  codesign --force --deep --options runtime \
    --entitlements "$ROOT/AegisCapture.entitlements" \
    --sign - \
    "$APP_DIR"
  echo "    WARNING: no DEVELOPER_ID_APPLICATION set — ad-hoc signed only."
  echo "    This build will NOT pass Gatekeeper on any Mac other than this one."
fi

codesign --verify --deep --strict --verbose=2 "$APP_DIR"

DMG_NAME="AEGIS_Capture_v${VERSION}.dmg"
rm -f "$ROOT/$DMG_NAME"
hdiutil create -volname "AEGIS Capture" -srcfolder "$APP_DIR" -ov -format UDZO "$ROOT/$DMG_NAME"
echo "==> Built $ROOT/$DMG_NAME"

if [ -n "${DEVELOPER_ID_APPLICATION:-}" ] && [ -n "${APPLE_ID:-}" ] && [ -n "${APPLE_TEAM_ID:-}" ] && [ -n "${APPLE_APP_SPECIFIC_PASSWORD:-}" ]; then
  echo "==> Notarizing…"
  xcrun notarytool submit "$ROOT/$DMG_NAME" \
    --apple-id "$APPLE_ID" \
    --team-id "$APPLE_TEAM_ID" \
    --password "$APPLE_APP_SPECIFIC_PASSWORD" \
    --wait
  echo "==> Stapling…"
  xcrun stapler staple "$ROOT/$DMG_NAME"
  echo "    Notarized and stapled."
else
  echo "    Skipping notarization (Apple credentials not fully set) — DMG is signed but not notarized."
  echo "    Gatekeeper will still show a warning on first launch until notarized."
fi

ls -lh "$ROOT/$DMG_NAME"
