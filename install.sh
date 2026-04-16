#!/bin/bash
# ─── Claude Editor Installer ──────────────────────────────────────────────
# Install via: curl -fsSL https://raw.githubusercontent.com/kaiden-stowell/Claude-editor/main/install.sh | bash
# ──────────────────────────────────────────────────────────────────────────

set -e

REPO="https://github.com/kaiden-stowell/Claude-editor.git"
INSTALL_DIR="$HOME/Claude-editor"
PORT=12795
PLIST_NAME="com.claude-editor.server"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

echo ""
echo "============================================"
echo "  Claude Editor v2.0.0 — Director's Cut"
echo "  Premium AI Video Editor Installer"
echo "============================================"
echo ""

# ─── Check macOS / Linux ──────────────────────────────────────────────────

OS="$(uname -s)"
if [ "$OS" != "Darwin" ] && [ "$OS" != "Linux" ]; then
    echo "  Error: Unsupported OS: $OS"
    echo "  Claude Editor supports macOS and Linux."
    exit 1
fi

# ─── Check Dependencies ─────────────────────────────────────────────────

echo "[1/6] Checking Python..."
if command -v python3 &>/dev/null; then
    PYTHON=$(which python3)
    PY_VERSION=$($PYTHON --version 2>&1 | awk '{print $2}')
    echo "  Found Python $PY_VERSION"
else
    echo "  Error: Python 3 not found."
    echo "  Install Python 3.9+ from https://python.org"
    exit 1
fi

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
            echo "  Error: Homebrew not found. Install FFmpeg manually:"
            echo "  brew install ffmpeg"
            exit 1
        fi
    else
        if command -v apt-get &>/dev/null; then
            sudo apt-get update && sudo apt-get install -y ffmpeg
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y ffmpeg
        else
            echo "  Error: Install FFmpeg manually: https://ffmpeg.org"
            exit 1
        fi
    fi
    echo "  FFmpeg installed."
fi

# ─── Clone / Update Repository ──────────────────────────────────────────

echo "[3/6] Downloading Claude Editor..."
if [ -d "$INSTALL_DIR" ]; then
    echo "  Found existing install at $INSTALL_DIR"
    # Preserve user data
    TEMP_DATA=$(mktemp -d)
    [ -f "$INSTALL_DIR/.env" ]     && cp "$INSTALL_DIR/.env" "$TEMP_DATA/.env"
    [ -d "$INSTALL_DIR/uploads" ]  && cp -r "$INSTALL_DIR/uploads" "$TEMP_DATA/uploads"
    [ -d "$INSTALL_DIR/outputs" ]  && cp -r "$INSTALL_DIR/outputs" "$TEMP_DATA/outputs"
    [ -d "$INSTALL_DIR/logs" ]     && cp -r "$INSTALL_DIR/logs" "$TEMP_DATA/logs"
    echo "  Backed up user data"

    if [ -d "$INSTALL_DIR/.git" ]; then
        cd "$INSTALL_DIR" && git stash 2>/dev/null; git pull --ff-only origin main
    else
        rm -rf "$INSTALL_DIR"
        git clone "$REPO" "$INSTALL_DIR"
    fi
    cd "$INSTALL_DIR"

    # Restore preserved data
    [ -f "$TEMP_DATA/.env" ]     && cp "$TEMP_DATA/.env" .env
    [ -d "$TEMP_DATA/uploads" ]  && cp -r "$TEMP_DATA/uploads" .
    [ -d "$TEMP_DATA/outputs" ]  && cp -r "$TEMP_DATA/outputs" .
    [ -d "$TEMP_DATA/logs" ]     && cp -r "$TEMP_DATA/logs" .
    rm -rf "$TEMP_DATA"
    echo "  Restored user data"
else
    git clone "$REPO" "$INSTALL_DIR"
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

# ─── Configuration ───────────────────────────────────────────────────────

echo "[6/6] Configuration..."

# Create .env if missing
if [ ! -f .env ]; then
    cat > .env <<'ENVEOF'
# Claude Editor Configuration
# ANTHROPIC_API_KEY=sk-ant-...
# WHISPER_MODEL=base
# CLAUDE_MODEL=claude-sonnet-4-20250514
# EDITOR_HOST=127.0.0.1
# EDITOR_PORT=12795
ENVEOF
    echo ""
    echo "  Edit $INSTALL_DIR/.env with your API key:"
    echo "     nano $INSTALL_DIR/.env"
fi

# Create start script that sources .env and activates venv
cat > "$INSTALL_DIR/start.sh" << 'STARTSCRIPT'
#!/bin/bash
cd "$(dirname "$0")"
[ -f .env ] && set -a && source .env && set +a
source venv/bin/activate 2>/dev/null || true
python3 app.py "$@"
STARTSCRIPT
chmod +x "$INSTALL_DIR/start.sh"

mkdir -p "$INSTALL_DIR/logs"

# ─── Install as persistent background service via launchd (macOS) ────────

if [ "$OS" = "Darwin" ]; then
    PYTHON_BIN="$INSTALL_DIR/venv/bin/python3"

    mkdir -p "$HOME/Library/LaunchAgents"

    cat > "$PLIST_PATH" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${INSTALL_DIR}/start.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${INSTALL_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${INSTALL_DIR}/logs/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${INSTALL_DIR}/logs/stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:${HOME}/.local/bin</string>
    </dict>
</dict>
</plist>
PLISTEOF

    # Unload if already running, then load
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    launchctl load "$PLIST_PATH"

    sleep 2
    echo ""
    if curl -s -o /dev/null "http://127.0.0.1:${PORT}/api/health" 2>/dev/null; then
        echo "  ✅ Claude Editor installed and running!"
        echo ""
        echo "  Open http://127.0.0.1:${PORT}"
    else
        echo "  ✅ Claude Editor installed!"
        echo "  ⚠️  Server may still be starting. Check logs at: $INSTALL_DIR/logs/"
    fi
    echo ""
    echo "  The server runs in the background and starts automatically on boot."
    echo "  To stop:     launchctl unload ~/Library/LaunchAgents/${PLIST_NAME}.plist"
    echo "  To restart:  launchctl unload ~/Library/LaunchAgents/${PLIST_NAME}.plist && launchctl load ~/Library/LaunchAgents/${PLIST_NAME}.plist"
    echo ""

else
    # Linux: just print manual start instructions
    echo ""
    echo "  ✅ Claude Editor installed!"
    echo ""
    echo "  To start:"
    echo "    cd $INSTALL_DIR"
    echo "    ./start.sh"
    echo ""
    echo "  Then open: http://127.0.0.1:${PORT}"
    echo ""
fi
