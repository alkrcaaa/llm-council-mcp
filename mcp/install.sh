#!/bin/bash
# install.sh — LLM Council MCP Server installation script
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "📦 Installing LLM Council MCP Server..."
echo "   Location: $SCRIPT_DIR"

# ── Python venv ──────────────────────────────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    echo "🔨 Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
else
    echo "✅ Virtual environment already exists"
fi

echo "📚 Installing dependencies..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"

echo "✅ LLM Council MCP server installed successfully"
