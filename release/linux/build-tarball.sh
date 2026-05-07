#!/usr/bin/env bash
set -euo pipefail

APP_NAME="overseer"
RELEASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$RELEASE_DIR/../.." && pwd)"

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
    VERSION="$(grep -E '^version\s*=' "$PROJECT_ROOT/pyproject.toml" | head -n1 | sed -E 's/.*=\s*"(.*)"/\1/')"
fi

if [[ -z "$VERSION" ]]; then
    echo "Error: could not determine version."
    echo "Pass it explicitly, e.g. ./build-tarball.sh 0.1.0"
    exit 1
fi

STAGING_ROOT="$RELEASE_DIR/build"
PAYLOAD_DIR="$STAGING_ROOT/${APP_NAME}-linux-${VERSION}"
ARCHIVE_PATH="$RELEASE_DIR/${APP_NAME}-linux-${VERSION}.tar.gz"

echo "Cleaning old build artifacts..."
rm -rf "$STAGING_ROOT"
rm -f "$ARCHIVE_PATH"

echo "Creating payload directory..."
mkdir -p "$PAYLOAD_DIR"

echo "Copying project files..."
cp -r "$PROJECT_ROOT/src" "$PAYLOAD_DIR/"
cp "$PROJECT_ROOT/README.md" "$PAYLOAD_DIR/"
cp "$PROJECT_ROOT/pyproject.toml" "$PAYLOAD_DIR/"

echo "Copying Linux release files..."
cp "$RELEASE_DIR/install.sh" "$PAYLOAD_DIR/"
cp "$RELEASE_DIR/launcher.sh" "$PAYLOAD_DIR/"
cp "$RELEASE_DIR/uninstall.sh" "$PAYLOAD_DIR/"
cp "$RELEASE_DIR/overseer.desktop" "$PAYLOAD_DIR/"

chmod +x "$PAYLOAD_DIR/install.sh"
chmod +x "$PAYLOAD_DIR/launcher.sh"
chmod +x "$PAYLOAD_DIR/uninstall.sh"

echo "Removing unwanted junk..."
find "$PAYLOAD_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$PAYLOAD_DIR" -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete
find "$PAYLOAD_DIR" -type d -name ".git" -prune -exec rm -rf {} +
find "$PAYLOAD_DIR" -type f -name ".DS_Store" -delete

echo "Creating tar.gz archive..."
tar -czf "$ARCHIVE_PATH" -C "$STAGING_ROOT" "$(basename "$PAYLOAD_DIR")"

echo
echo "Done."
echo "Created: $ARCHIVE_PATH"
echo
echo "Contents will extract into:"
echo "  $(basename "$PAYLOAD_DIR")/"
