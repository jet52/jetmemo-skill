#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="bench-memo"
INSTALL_DIR="$HOME/.claude/skills/$SKILL_NAME"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing $SKILL_NAME skill..."

# Create target directory
mkdir -p "$INSTALL_DIR"

# Copy skill files
cp -a "$SCRIPT_DIR/skill/"* "$INSTALL_DIR/"

echo "Installed to $INSTALL_DIR"

# Check external dependencies
WARNINGS=0

if ! python3 -c "import pypdf" &>/dev/null 2>&1; then
    echo "WARNING: pypdf Python package not found"
    echo "  Install with: pip install pypdf"
    WARNINGS=$((WARNINGS + 1))
fi

if [ ! -d "$HOME/refs/opin" ]; then
    echo "WARNING: ~/refs/opin/ not found"
    echo "  This directory should contain ND Supreme Court opinions (markdown)."
    WARNINGS=$((WARNINGS + 1))
fi

if [ ! -d "$HOME/refs/ndcc" ]; then
    echo "WARNING: ~/refs/ndcc/ not found"
    echo "  This directory should contain North Dakota Century Code files."
    WARNINGS=$((WARNINGS + 1))
fi

if [ ! -d "$HOME/refs/ndac" ]; then
    echo "WARNING: ~/refs/ndac/ not found"
    echo "  This directory should contain North Dakota Administrative Code files."
    WARNINGS=$((WARNINGS + 1))
fi

if [ "$WARNINGS" -gt 0 ]; then
    echo ""
    echo "$WARNINGS warning(s). The skill will work but some features may be limited."
else
    echo "All dependencies found."
fi

echo "Done."
