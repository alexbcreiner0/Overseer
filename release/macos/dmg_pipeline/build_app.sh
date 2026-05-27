#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${1:-}"
DMG_NAME="${1:-}"
# BUNDLE_ID="com.alexcreiner.crossdualdynamicroprelease"
# IDENTITY="Developer ID Application: Alex Creiner (YJG3692G9D)"

if [[ -z "$APP_NAME" ]]; then
  echo "Usage: ./build_app.sh APP_NAME"
  exit 1
fi

cd "$(dirname "$0")"
rm -rf build dist dmgroot "${DMG_NAME}.dmg"

# Optional signing/notarization-related flags (move inside the pyinstaller command below if using:
#   --osx-bundle-identifier "$BUNDLE_ID"
#   --codesign-identity "$IDENTITY"
#   --osx-entitlements-file ./entitlements.plist

pyinstaller \
  -n "$APP_NAME" \
  --clean \
  --noconfirm \
  --windowed \
  --onedir \
  --icon ../../../src/overseer/assets/icon.icns \
  --additional-hooks-dir=. \
  --collect-data overseer \
  --collect-data scienceplots \
  --add-data "../../../src/overseer/defaults/models:overseer/defaults/models" \
  --collect-all mesa \
  --hidden-import overseer.tools.log_formatter \
  --paths ../../../src \
  ./main.py

# ditto -c -k --keepParent "dist/${APP_NAME}.app" "dist/${APP_NAME}.zip" # zip the app
#codesign --verify --deep --strict --verbose=2 "dist/${APP_NAME}.app" # verify

mkdir -p dmgroot
cp -R "dist/${APP_NAME}.app" dmgroot/
ln -s /Applications "dmgroot/Applications"

hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder dmgroot \
  -ov -format UDZO \
  "${DMG_NAME}.dmg"

#xcrun notarytool submit "${DMG_NAME}.dmg" --keychain-profile "AC_PROFILE" --wait
#xcrun notarytool history --keychain-profile "AC_PROFILE"
#xcrun stapler staple "${DMG_NAME}.dmg"
#xcrun stapler validate "${DMG_NAME}.dmg"

echo "Done."
