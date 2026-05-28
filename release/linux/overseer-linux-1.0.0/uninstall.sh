#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Overseer"
APP_AUTHOR="Alex Creiner"

INSTALL_ROOT="$HOME/.local/share/$APP_NAME"
DESKTOP_FILE="$HOME/.local/share/applications/overseer.desktop"
ICON_FILE="$HOME/.local/share/icons/hicolor/256x256/apps/overseer.png"

# These should match your Python-side defaults / platformdirs usage.
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/$APP_NAME"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/$APP_NAME"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/$APP_NAME"

# Your user models location, based on your current design discussions.
MODELS_DIR="$HOME/Documents/Overseer"

confirm() {
    local prompt="$1"
    local reply
    while true; do
        read -r -p "$prompt [y/N]: " reply
        case "$reply" in
            [yY]|[yY][eE][sS]) return 0 ;;
            ""|[nN]|[nN][oO]) return 1 ;;
            *) echo "Please answer y or n." ;;
        esac
    done
}

remove_if_exists() {
    local path="$1"
    if [[ -e "$path" || -L "$path" ]]; then
        rm -rf "$path"
        echo "Removed: $path"
    else
        echo "Not found: $path"
    fi
}

echo "Uninstalling $APP_NAME..."

echo
echo "Removing application files..."
remove_if_exists "$INSTALL_ROOT"
remove_if_exists "$DESKTOP_FILE"
remove_if_exists "$ICON_FILE"
# remove_if_exists "$DATA_DIR" # this is just the install root
remove_if_exists "$CACHE_DIR"

update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true

echo
if confirm "Also delete your config files in $CONFIG_DIR?"; then
    remove_if_exists "$CONFIG_DIR"
else
    echo "Kept config files."
fi

echo
if confirm "Also delete your models in $MODELS_DIR?"; then
    remove_if_exists "$MODELS_DIR"
else
    echo "Kept models."
fi

echo
echo "Uninstall complete."
