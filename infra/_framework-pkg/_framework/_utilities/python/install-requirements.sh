#!/usr/bin/env bash
# install-requirements.sh — install Python packages from a requirements.txt file.
# Prefers uv if available; falls back to pip with --break-system-packages on PEP 668 errors.
# Usage: install-requirements.sh <requirements.txt>

set -euo pipefail

REQ="${1:?Usage: $(basename "$0") <requirements.txt>}"
[[ -f "$REQ" ]] || { echo "ERROR: requirements file not found: $REQ" >&2; exit 1; }

if command -v uv >/dev/null 2>&1 && [[ -n "${VIRTUAL_ENV:-}" ]]; then
    # Inside a venv: uv is fast and correct.
    uv pip install -r "$REQ"
elif python3 -m pip --version >/dev/null 2>&1; then
    # Outside a venv: uv --system requires root; pip --user installs to ~/.local.
    python3 -m pip install -r "$REQ" --quiet --user 2>/dev/null \
        || python3 -m pip install -r "$REQ" --quiet --user --break-system-packages
else
    echo "ERROR: pip not available — cannot install Python packages" >&2
    exit 1
fi
