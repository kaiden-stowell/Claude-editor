# 🎬 Claude-editor

Fully automated AI video editor that transcribes, captions, and brands your videos with AI logos. No manual editing, no complex software—just upload and download.

**[View on GitHub](https://github.com/kaiden-stowell/Claude-editor)**

## ✨ Features

- ✅ **Fully Automated** — Upload video → Get branded reel (no manual editing)
- ✅ **Auto-Transcription** — Speech-to-text using Whisper AI
- ✅ **Smart Captions** — Automatically timed captions matching your speech
- ✅ **Logo Overlays** — Add Claude, OpenAI, Gemini, Anthropic logos
- ✅ **Web Interface** — Beautiful drag-and-drop UI with real-time progress
- ✅ **Auto-Updates** — Built-in GitHub auto-update checker + installer
- ✅ **AgentHub Ready** — Integrates with AgentHub for agent orchestration
- ✅ **Queue Management** — Process multiple videos simultaneously
- ✅ **No Dependencies** — Pure Python + FFmpeg, runs anywhere

## 🚀 Quick Start

### Option 1: Install via Curl (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/kaiden-stowell/Claude-editor/main/install.sh | bash
```

This will:
- Clone the repository
- Install all dependencies
- Start the web server

Then open: **http://localhost:5000**

## 📖 Usage

1. **Open Web Interface** → http://localhost:5000
2. **Upload Video** → Drag-and-drop or click to select
3. **Select Logos** → Choose which AI logos to overlay
4. **Process** → Click "Start Processing"
5. **Download** → One-click download when complete

## 📦 What's Included

- `app.py` - Flask backend server
- `index.html` - Web UI
- `reel_editor.py` - Video processing engine
- `update_checker.py` - Auto-update from GitHub
- `agenthub_connector.py` - AgentHub integration
- `install.sh` - One-command installer

## 🔄 Auto-Updates

The app automatically checks GitHub for updates.

## 🤖 AgentHub Integration

Fully compatible with AgentHub for agent-based automation.

## 📝 License

MIT License
