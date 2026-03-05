#!/usr/bin/env bash
# Wrapper for backward compatibility — delegates to install.py
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/install.py"
