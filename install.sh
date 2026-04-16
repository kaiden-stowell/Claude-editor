#!/bin/bash
# ─── Claude Editor Installer ──────────────────────────────────────────────
# Install via: curl -fsSL https://raw.githubusercontent.com/kaiden-stowell/Claude-editor/main/install.sh | bash
# ──────────────────────────────────────────────────────────────────────────

set -e

REPO="kaiden-stowell/Claude-editor"
INSTALL_DIR="$HOME/Claude-editor"
PORT=12795

echo ""
echo "============================================"
echo "  Claude Editor v2.0.0 — Director's Cut"
echo "  Premium AI Video Editor Installer"
echo "============================================"
echo ""

# ─── Check macOS / Linux ──────────────────────────────────────────────────

OS="$(uname -s)"
if [ "$OS" != "Darwin" ] && [ "$OS" != "Linux" ]; then
    echo "ERROR: Unsupported OS: $OS"
    echo "Claude Editor supports macOS and Linux."
    exit 1
fi

# ─── Check Python ─────────────────────────────────────────────────────────

echo "[1/6] Checking Python..."
if command -v python3 &>/dev/null; then
    PYTHON=python3
    PY_VERSION=$($PYTHON --version 2>&1 | awk '{print $2}')
    echo "  Found Python $PY_VERSION"
else
    echo "  ERROR: Python 3 not found."
    echo "  Install Python 3.9+ from https://python.org"
    exit 1
fi

# ─── Check FFmpeg ─────────────────────────────────────────────────────────

echo "[2/6] Checking FFmpeg..."
if command -v ffmpeg &>/dev/null; then
    FF_VERSION=$(ffmpeg -version 2>&1 | head -1 | awk '{print $3}')
    echo "  Found FFmpeg $FF_VERSION"
else
    echo "  FFmpeg not found. Installing..."
    if [ "$OS" = "Darwin" ]; then
        if command -v brew &>/dev/null; then
            brew install ffmpeg
        else
            echo "  ERROR: Homebrew not found. Install FFmpeg manually:"
            echo "  brew install ffmpeg"
            echo "  or download from https://ffmpeg.org"
            exit 1
        fi
    else
        if command -v apt-get &>/dev/null; then
            sudo apt-get update && sudo apt-get install -y ffmpeg
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y ffmpeg
        else
            echo "  ERROR: Install FFmpeg manually: https://ffmpeg.org"
            exit 1
        fi
    fi
    echo "  FFmpeg installed."
fi

# ─── Clone Repository ────────────────────────────────────────────────────

echo "[3/6] Downloading Claude Editor..."
if [ -d "$INSTALL_DIR" ]; then
    echo "  Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull origin main 2>/dev/null || true
else
    git clone "https://github.com/$REPO.git" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# ─── Create Virtual Environment ──────────────────────────────────────────

echo "[4/6] Setting up Python environment..."
if [ ! -d "venv" ]; then
    $PYTHON -m venv venv
fi
source venv/bin/activate

# ─── Install Dependencies ────────────────────────────────────────────────

echo "[5/6] Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  Dependencies installed."

# ─── Check API Key ───────────────────────────────────────────────────────

echo "[6/6] Configuration..."
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo ""
    echo "  NOTE: ANTHROPIC_API_KEY is not set."
    echo "  You need this for the AI editing features."
    echo "  Set it with: export ANTHROPIC_API_KEY=your-key-here"
    echo ""
fi

# ─── Create start script ─────────────────────────────────────────────────

cat > "$INSTALL_DIR/start.sh" << 'STARTSCRIPT'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate 2>/dev/null || true
python3 app.py "$@"
STARTSCRIPT
chmod +x "$INSTALL_DIR/start.sh"

# ─── Done ─────────────────────────────────────────────────────────────────

echo ""
echo "============================================"
echo "  Installation complete!"
echo "============================================"
echo ""
echo "  To start Claude Editor:"
echo ""
echo "    cd $INSTALL_DIR"
echo "    export ANTHROPIC_API_KEY=your-key-here"
echo "    ./start.sh"
echo ""
echo "  Then open: http://127.0.0.1:$PORT"
echo ""
echo "  Agent API: http://127.0.0.1:$PORT/api/agent/edit"
echo ""
echo "============================================"
echo ""
