#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  build_dmg.sh — wrap the macOS PyInstaller output into FundTrail.app + a
#  drag-to-Applications .dmg (the standard Mac install pattern).
#
#  RUN ORDER (on a Mac):
#       ./build_exe.sh      # produces dist/FundTrail  (Mach-O binary)
#       ./build_dmg.sh      # produces dist/FundTrail.app and dist/FundTrail.dmg
#
#  Tools used (all ship with macOS): sips, iconutil, hdiutil, osascript.
#  No third-party tooling (create-dmg) required.
#
#  GATEKEEPER CAVEAT: this produces an UNSIGNED app. On first launch end users
#  will see "FundTrail can't be opened because Apple cannot check it for
#  malicious software." Right-click → Open (once), or sign + notarize with an
#  Apple Developer ID. See docs/INSTALLERS.md → "macOS code-signing".
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"

APP_NAME="FundTrail"
BUNDLE_ID="in.gov.tn.cybercrime.fundtrail"
APP_VERSION="3.0"
BIN="dist/${APP_NAME}"
APP="dist/${APP_NAME}.app"
DMG="dist/${APP_NAME}.dmg"
ICON_SRC="main/static/logo.png"

[[ -f "$BIN" ]] || { echo "ERROR: $BIN not found. Run ./build_exe.sh first." >&2; exit 1; }

echo "[1/5] Generating FundTrail.icns from ${ICON_SRC}..."
# Icon is cosmetic: never let a bad/odd source image abort packaging. `-s format
# png` forces true PNG bytes (the source may be JPEG-encoded with a .png suffix,
# which iconutil rejects).
make_icns() {
  local iconset; iconset="$(mktemp -d)/FundTrail.iconset"; mkdir -p "$iconset"
  local s
  for s in 16 32 64 128 256 512; do
    sips -s format png -z $s $s             "$ICON_SRC" --out "$iconset/icon_${s}x${s}.png"    >/dev/null 2>&1
    sips -s format png -z $((s*2)) $((s*2)) "$ICON_SRC" --out "$iconset/icon_${s}x${s}@2x.png" >/dev/null 2>&1
  done
  iconutil -c icns "$iconset" -o "dist/FundTrail.icns" >/dev/null 2>&1
}
if [[ -f "$ICON_SRC" ]] && make_icns && [[ -f "dist/FundTrail.icns" ]]; then
  echo "  icon: dist/FundTrail.icns"
else
  rm -f "dist/FundTrail.icns"
  echo "  WARNING: could not build icon from ${ICON_SRC}; continuing without a custom icon."
fi

echo "[2/5] Assembling ${APP}..."
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/${APP_NAME}"
chmod +x "$APP/Contents/MacOS/${APP_NAME}"
[[ -f "dist/FundTrail.icns" ]] && cp "dist/FundTrail.icns" "$APP/Contents/Resources/FundTrail.icns"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>${APP_NAME}</string>
  <key>CFBundleDisplayName</key><string>${APP_NAME}</string>
  <key>CFBundleIdentifier</key><string>${BUNDLE_ID}</string>
  <key>CFBundleVersion</key><string>${APP_VERSION}</string>
  <key>CFBundleShortVersionString</key><string>${APP_VERSION}</string>
  <key>CFBundleExecutable</key><string>${APP_NAME}</string>
  <key>CFBundleIconFile</key><string>FundTrail.icns</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

echo "[3/5] Staging .dmg layout (FundTrail.app + Applications alias)..."
STAGE="$(mktemp -d)/dmgroot"; mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

echo "[4/5] Building read/write image and arranging icons..."
TMP_DMG="$(mktemp -d)/rw.dmg"
hdiutil create -srcfolder "$STAGE" -volname "$APP_NAME" -fs HFS+ \
  -format UDRW -ov "$TMP_DMG" >/dev/null
MOUNT_DIR="/Volumes/${APP_NAME}"
hdiutil attach "$TMP_DMG" -mountpoint "$MOUNT_DIR" -nobrowse >/dev/null
# Best-effort Finder layout: side-by-side "drag onto Applications" view.
osascript <<OSA || true
tell application "Finder"
  tell disk "${APP_NAME}"
    open
    set theViewOptions to icon view options of container window
    set arrangement of theViewOptions to not arranged
    set icon size of theViewOptions to 128
    set bounds of container window to {200, 150, 760, 520}
    set position of item "${APP_NAME}.app" of container window to {150, 200}
    set position of item "Applications" of container window to {420, 200}
    update without registering applications
    delay 1
    close
  end tell
end tell
OSA
sync
hdiutil detach "$MOUNT_DIR" >/dev/null

echo "[5/5] Converting to compressed read-only ${DMG}..."
rm -f "$DMG"
hdiutil convert "$TMP_DMG" -format UDZO -imagekey zlib-level=9 -o "$DMG" >/dev/null

echo "============================================================"
echo "  Done:"
echo "    App bundle : $APP"
echo "    Installer  : $DMG   (drag FundTrail.app onto Applications)"
echo "  Data persists in ~/.local/share/FundTrail (untouched by install/move)."
echo "  UNSIGNED — see docs/INSTALLERS.md for the Gatekeeper / notarization note."
echo "============================================================"
