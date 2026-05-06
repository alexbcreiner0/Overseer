#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

VENV_PYTHON="$INSTALL_ROOT/.venv/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "Error: Python environment not found at $VENV_PYTHON" >&2
    exit 1
fi

# UNCOMMENT FOR DEVELOPMENT
# export PYTHONPATH="$INSTALL_ROOT/src/${PYTHONPATH:+:$PYTHONPATH}"

exec "$VENV_PYTHON" -m overseer "$@"
