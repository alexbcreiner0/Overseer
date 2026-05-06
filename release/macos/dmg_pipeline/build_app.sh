#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${1:-}"
DMG_NAME="${1:-}"
BUNDLE_ID="com.alexcreiner.crossdualdynamicroprelease" # change to whatever is appropriate
IDENTITY="Developer ID Application: Alex Creiner (YJG3692G9D)"

if [[ -z "$APP_NAME" ]]; then
  echo "Usage: ./build_app.sh APP_NAME"
  exit 1
fi

cd "$(dirname "$0")"
rm -rf build dist dmgroot "${DMG_NAME}.dmg"

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
  --collect-all mesa \
  --hidden-import overseer.tools.log_formatter \
  --paths ../../../src \
  --osx-bundle-identifier "$BUNDLE_ID" \
  --codesign-identity "$IDENTITY" \
  --osx-entitlements-file ./entitlements.plist \
  ./main.py

# ditto -c -k --keepParent "dist/${APP_NAME}.app" "dist/${APP_NAME}.zip" # zip the app
codesign --verify --deep --strict --verbose=2 "dist/${APP_NAME}.app" # verify

mkdir -p dmgroot
cp -R "dist/${APP_NAME}.app" dmgroot/
ln -s /Applications "dmgroot/Applications"

hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder dmgroot \
  -ov -format UDZO \
  "${DMG_NAME}.dmg"

# codesign --verify --verbose=2 "${DMG_NAME}.dmg"
# codesign --force --timestamp --sign "$IDENTITY" "${DMG_NAME}.dmg" # sign

xcrun notarytool submit "${DMG_NAME}.dmg" --keychain-profile "AC_PROFILE" --wait

# echo "Done. DMG file created, signed and submitted for notarization."
# echo "Poll for progress using the command:"
# echo '  xcrun notarytool history --keychain-profile "AC_PROFILE"'
xcrun notarytool history --keychain-profile "AC_PROFILE"

# echo "After approval, copy and paste the following commands to complete the process: "
# echo "  xcrun stapler staple \"${DMG_NAME}.dmg\""
# echo "  xcrun stapler validate \"${DMG_NAME}.dmg\""
# xcrun stapler validate "dist/${APP_NAME}.app"
# rm "dist/{$APP_NAME}.zip"
# spctl --assess --type execute --verbose=4 "dist/${APP_NAME}.app"
# ditto -c -k --keepParent "dist/${APP_NAME}.app" "${APP_NAME}.zip"
xcrun stapler staple "${DMG_NAME}.dmg"
xcrun stapler validate "${DMG_NAME}.dmg"

echo "Done."
