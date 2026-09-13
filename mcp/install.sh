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
# Never call .venv/bin/pip: its shebang hard-codes the path the venv was created
# at, so it breaks once the checkout moves. uv venvs have no pip at all.
if command -v uv &>/dev/null; then
    uv pip install --quiet --python "$VENV_DIR/bin/python" -r "$SCRIPT_DIR/requirements.txt"
else
    "$VENV_DIR/bin/python" -m pip install --quiet --upgrade pip
    "$VENV_DIR/bin/python" -m pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
fi

echo "✅ LLM Council MCP server installed successfully"
