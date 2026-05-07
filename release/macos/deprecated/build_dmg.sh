#!/usr/bin/env bash
# Run this to compile a new .app file, then immediately bundle it as a 
# dmg. If something isn't working, run the python setup.py py2app step
# independently and then run (from the release/macos folder):
#    dist/Overseer.app/Contents/MacOS/Overseer to see 
#    standard output and do the necessary debugging. 
#    the .dmg alone can be uploaded for mac os users to install the app
#    delete the dist and dmgroot directories 
set -euo pipefail

APP_NAME="Overseer"
DMG_NAME="Overseer"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

rm -rf $ROOT_DIR/release/macos/dmg_pipeline/build $ROOT_DIR/release/macos/dmg_pipeline/dist $ROOT_DIR/release/macos/dmg_pipeline/dmgroot

python setup.py py2app

echo NOT DONE! Done making the .app file. Moving on to package it as a .dmg

mkdir -p $ROOT_DIR/release/macos/dmg_pipeline/dmgroot
cp -R "$ROOT_DIR/release/macos/dmg_pipeline/dist/${APP_NAME}.app" $ROOT_DIR/release/macos/dmg_pipeline/dmgroot/
ln -s /Applications $ROOT_DIR/release/macos/dmg_pipeline/dmgroot/Applications

hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder $ROOT_DIR/release/macos/dmg_pipeline/dmgroot \
  -ov -format UDZO \
  "$ROOT_DIR/release/macos/dmg_pipeline/${DMG_NAME}.dmg"

echo "Built release/macos/dmg_pipeline/${DMG_NAME}.dmg"
