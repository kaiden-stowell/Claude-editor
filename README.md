# Claude Editor — AI Video Editor

**v2.0.0 "Director's Cut"** | Premium AI Video Editor

AI-powered video editor that learns editing style from an example video, then edits your raw footage to match. Built for creators, controlled by agents.

**Upload an example reel. Upload your raw footage. Get a professionally edited video back.**

## How It Works

1. **Upload an Example Video** — Show the AI a video with the editing style you want (pacing, cuts, energy, vibe)
2. **Upload Your Raw Footage** — The AI transcribes what you're saying and understands what you're doing
3. **AI Edits Your Video** — Claude analyzes the style + your content, selects the best moments, adds on-brand captions, and renders the final edit

## Features

- **Style Learning** — Analyzes example videos for pacing, cuts per minute, color profile, and structure
- **Smart Transcription** — Whisper AI transcribes your speech with word-level timestamps
- **AI Director** — Claude picks the best moments, creates a compelling narrative, matches the example's energy
- **On-Brand Captions** — Customizable caption styles with brand colors, fonts, emphasis effects
- **Reel-Ready** — Output in 9:16 (reel/short), 16:9 (landscape), or 1:1 (square)
- **Agent API** — Full REST API for Claude Code and AgentHub integration
- **Web UI** — Dark Premiere-style interface with drag-and-drop, live progress, timeline view
- **Brand Presets** — Save and reuse your brand identity across edits

## Quick Start

### Install via curl

```bash
curl -fsSL https://raw.githubusercontent.com/kaiden-stowell/Claude-editor/main/install.sh | bash
```

### Manual Setup

```bash
git clone https://github.com/kaiden-stowell/Claude-editor.git
cd Claude-editor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Then open: **http://127.0.0.1:12795**

## Requirements

- Python 3.9+
- FFmpeg
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)

## Agent API

Claude Code and AgentHub can control the editor programmatically:

### Full Edit

```bash
curl -X POST http://127.0.0.1:12795/api/agent/edit \
  -H "Content-Type: application/json" \
  -d '{
    "example_video": "/path/to/example.mp4",
    "raw_footage": "/path/to/raw.mp4",
    "instructions": "Make it energetic and fun",
    "output_format": "reel",
    "brand": "default",
    "wait": true
  }'
```

### Analyze Style Only

```bash
curl -X POST http://127.0.0.1:12795/api/agent/analyze \
  -H "Content-Type: application/json" \
  -d '{"video": "/path/to/video.mp4"}'
```

### Transcribe Only

```bash
curl -X POST http://127.0.0.1:12795/api/agent/transcribe \
  -H "Content-Type: application/json" \
  -d '{"video": "/path/to/video.mp4"}'
```

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | System health check |
| `GET` | `/api/info` | Editor capabilities |
| `POST` | `/api/agent/edit` | Full edit pipeline |
| `POST` | `/api/agent/analyze` | Analyze video style |
| `POST` | `/api/agent/transcribe` | Transcribe video |
| `GET` | `/api/status/<job_id>` | Job status |
| `GET` | `/api/stream/<job_id>` | SSE progress stream |
| `GET` | `/api/download/<job_id>` | Download result |
| `GET` | `/api/jobs` | List all jobs |
| `GET` | `/api/brands` | List brand presets |
| `PUT` | `/api/brands/<name>` | Save brand config |

## Project Structure

```
Claude-editor/
├── app.py                 # Flask server + API routes
├── config.py              # Configuration
├── requirements.txt       # Python dependencies
├── install.sh             # curl installer
├── start.sh               # Start script
├── editor/
│   ├── analyzer.py        # Example video style analyzer
│   ├── transcriber.py     # Whisper transcription
│   ├── ai_director.py     # Claude AI edit planning
│   ├── video_editor.py    # FFmpeg editing engine
│   └── brand.py           # Brand/caption management
├── templates/
│   └── index.html         # Web UI
└── static/
    ├── css/style.css      # Dark theme
    └── js/app.js          # Frontend logic
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_BIN` | (auto-detected) | Path to claude CLI binary |
| `WHISPER_MODEL` | `base` | Whisper model size (tiny/base/small/medium/large) |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Claude model for AI Director |
| `EDITOR_HOST` | `127.0.0.1` | Server host |
| `EDITOR_PORT` | `12795` | Server port |

## License

MIT License
