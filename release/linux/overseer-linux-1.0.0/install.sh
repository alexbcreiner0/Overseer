#!/usr/bin/bash
# make sure script crashes when it should to avoid doing damage
set -euo pipefail 

APP_NAME="Overseer"
INSTALL_ROOT="$HOME/.local/share/$APP_NAME"
BIN_DIR="$INSTALL_ROOT/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"

# computes the absolute path to the project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAYLOAD_ROOT="$SCRIPT_DIR"

echo "Checking for Python installation..."
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD=python
else
    echo "Error: Python does not appear to be installed. If you think this is not the case, you should check to make sure it was added to your system PATH at the time of installation."
    echo "Please ensure Python 3.10 or higher is installed on your system, and then run this installer again."
    exit 1
fi

PY_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')

REQUIRED_MAJOR=3
REQUIRED_MINOR=10

PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [[ "$PY_MAJOR" -lt "$REQUIRED_MAJOR" ]] || \
   [[ "$PY_MAJOR" -eq "$REQUIRED_MAJOR" && "$PY_MINOR" -lt "$REQUIRED_MINOR" ]]; then
    echo "Error: Python $REQUIRED_MAJOR.$REQUIRED_MINOR or newer is required."
    echo "Detected Python version: $PY_VERSION."
    echo "Please update your Python version and then run this installer again."
    exit 1
fi

echo "Using Python $PY_VERSION ($PYTHON_CMD)"
echo "Installing..."

# payload integrity check
for required in \
    "$PAYLOAD_ROOT/src" \
    "$PAYLOAD_ROOT/pyproject.toml" \
    "$PAYLOAD_ROOT/README.md" \
    "$PAYLOAD_ROOT/launcher.sh" \
    "$PAYLOAD_ROOT/overseer.desktop" \
    "$PAYLOAD_ROOT/src/overseer/assets/icon.png" \
    "$PAYLOAD_ROOT/src/overseer/defaults"
do
    if [[ ! -e "$required" ]]; then
        echo "Error: expected release file not found:"
        echo "  $required"
        echo "Make sure you extracted the full tar.gz and are running install.sh from inside that extracted folder."
        exit 1
    fi
done

# make any missing folders
mkdir -p "$INSTALL_ROOT" "$BIN_DIR" "$DESKTOP_DIR" "$ICON_DIR"

# copy necessary files over to the install root
# (destroy files that are already in the install root but not here)
echo "Copying application files..."
rm -rf "$INSTALL_ROOT/src"

cp -r "$PAYLOAD_ROOT/src" "$INSTALL_ROOT/"
cp "$PAYLOAD_ROOT/README.md" "$INSTALL_ROOT/"
cp "$PAYLOAD_ROOT/pyproject.toml" "$INSTALL_ROOT/"

# create a virtual environment for the app
echo "Creating virtual environment..."
# "$PYTHON_CMD" -m venv "$INSTALL_ROOT/.venv"
rm -rf "$INSTALL_ROOT/.venv"
"$PYTHON_CMD" -m venv "$INSTALL_ROOT/.venv"

echo "Upgrading pip..."
"$INSTALL_ROOT/.venv/bin/python" -m pip install --upgrade pip # not a typo - inside a venv, interpreter is always just python
# install the package (includes dependencies as specified in pyproject.toml)
"$INSTALL_ROOT/.venv/bin/python" -m pip install "$INSTALL_ROOT"

echo "Installing launcher..."
install -m 755 "$PAYLOAD_ROOT/launcher.sh" "$BIN_DIR/launcher.sh"

# fill in the executable path of the desktop file and 
# pipe it to where the rest of the .desktop files are
echo "Installing desktop file..."
sed "s|@EXEC_PATH@|$BIN_DIR/launcher.sh|g" \
    "$PAYLOAD_ROOT/overseer.desktop" \
    > "$DESKTOP_DIR/overseer.desktop"

chmod 644 "$DESKTOP_DIR/overseer.desktop"

if [[ -f "$PAYLOAD_ROOT/src/overseer/assets/icon.png" ]]; then
    install -m 644 \
      "$PAYLOAD_ROOT/src/overseer/assets/icon.png" \
      "$ICON_DIR/overseer.png"
fi

update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true

echo "Installed!"
echo "You should now find the app where you find your other programs."
echo "Alternatively, you can find the launcher script in $BIN_DIR"
