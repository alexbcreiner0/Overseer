#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
MACOS_DIR="$ROOT/release/macos"
PAYLOAD_DIR="$MACOS_DIR/pkg_pipeline/payload"
SCRIPTS_DIR="$MACOS_DIR/pkg_pipeline/scripts"
DIST_DIR="$MACOS_DIR/pkg_pipeline/dist"
COMPONENT_PLIST="$MACOS_DIR/pkg_pipeline/component.plist"

APP_IDENTITY="Developer ID Application: Alex Creiner (YJG3692G9D)"
PKG_IDENTITY="Developer ID Installer: Alex Creiner (YJG3692G9D)"
NOTARY_PROFILE="AC_PROFILE"

UNSIGNED_PKG="$DIST_DIR/Overseer-unsigned.pkg"
SIGNED_PKG="$DIST_DIR/Overseer.pkg"

APP_SUPPORT_DST="$PAYLOAD_DIR/Library/Application Support/Overseer"
APP_BUNDLE_DST="$PAYLOAD_DIR/Applications/Overseer.app"

rm -rf "$PAYLOAD_DIR" "$DIST_DIR/Overseer.pkg"
mkdir -p "$APP_SUPPORT_DST" "$PAYLOAD_DIR/Applications" "$DIST_DIR"

# Copy project files
cp "$ROOT/pyproject.toml" "$APP_SUPPORT_DST/"
cp "$ROOT/README.md" "$APP_SUPPORT_DST/" || true
cp -R "$ROOT/src" "$APP_SUPPORT_DST/"

# Wrapper app should already exist in packaging/macos/app-template, or build it here:
mkdir -p "$APP_BUNDLE_DST/Contents/MacOS"
mkdir -p "$APP_BUNDLE_DST/Contents/Resources"

cp "$MACOS_DIR/pkg_pipeline/app-template/Info.plist" "$APP_BUNDLE_DST/Contents/Info.plist"
cp "$MACOS_DIR/pkg_pipeline/app-template/Overseer" "$APP_BUNDLE_DST/Contents/MacOS/Overseer"
chmod +x "$APP_BUNDLE_DST/Contents/MacOS/Overseer"
cp "$ROOT/src/overseer/assets/icon.icns" "$APP_BUNDLE_DST/Contents/Resources/AppIcon.icns"

codesign --force --timestamp --options runtime --sign "$APP_IDENTITY" "$APP_BUNDLE_DST"
codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE_DST"
spctl --assess --type execute --verbose=4 "$APP_BUNDLE_DST" || true

pkgbuild --analyze --root "$PAYLOAD_DIR" "$COMPONENT_PLIST"
/usr/libexec/PlistBuddy -c "Set :0:BundleIsRelocatable false" "$COMPONENT_PLIST"

pkgbuild \
  --root "$PAYLOAD_DIR" \
  --scripts "$SCRIPTS_DIR" \
  --identifier "edu.overseer.installer" \
  --component-plist "$COMPONENT_PLIST" \
  --version "1.0.0" \
  "$UNSIGNED_PKG"

productsign --sign "$PKG_IDENTITY" "$UNSIGNED_PKG" "$SIGNED_PKG"
pkgutil --check-signature "$SIGNED_PKG"

xcrun notarytool submit "$SIGNED_PKG" --keychain-profile "$NOTARY_PROFILE" --wait

xcrun stapler staple "$SIGNED_PKG"
xcrun stapler validate "$SIGNED_PKG"

echo "Built, signed, notarized and stapled!"
echo "  $SIGNED_PKG"
