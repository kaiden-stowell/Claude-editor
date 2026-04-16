# Changelog

All notable changes to Claude Editor are documented here.
Format follows [Semantic Versioning](https://semver.org/).

---

## [2.0.0] — 2026-04-16 — "Director's Cut"

The full premium release. Feature parity with Premiere Pro and Final Cut Pro,
powered by AI.

### Added — Premium Visual Effects
- 10 cinematic LUT color grades (warm, cool, moody, vintage, cyberpunk, etc.)
- Film grain overlay (light / medium / heavy)
- Vignette effect
- Speed ramping — slow-mo and fast-forward per segment
- Zoom / Ken Burns effects
- Picture-in-picture overlay
- Video sharpening (light / medium / heavy)
- Cinematic letterbox bars

### Added — 30+ Professional Transitions
- Basic: hard cut, cross dissolve, fade through black, fade through white
- Wipes: left, right, up, down
- Slides: all 4 directions + smooth eased variants
- Shape: circle reveal, circle open, circle close
- Stylized: pixelize, radial wipe, barn door (h/v), diagonal (4 corners), squeeze (h/v)

### Added — Premium Audio Processing
- LUFS-standard audio normalization (–14 LUFS for social media)
- AI noise reduction (light / medium / heavy)
- Voice clarity enhancement (EQ + compression)
- Audio ducking — auto-lower music during speech
- Silence detection and auto-removal (jump-cut style)
- Audio fade in / fade out

### Added — Advanced Captions
- Word-by-word highlight (karaoke style, like CapCut Pro)
- Bold outline captions (no background box)
- Glow effect captions
- Brand-aware emphasis colors and sizing

### Added — Video Stabilization
- Two-pass vidstab (like Premiere's Warp Stabilizer)
- Light / medium / heavy strength presets
- Auto shake detection with recommendation

### Added — Chroma Key / Green Screen
- Green, blue, red, or custom color keying
- Background replacement with any video or image
- Blurred background portrait mode effect

### Added — Beat-Synced Editing
- Music beat detection with BPM estimation
- Auto-cut video segments to beat positions
- Beat-synced editing with music track overlay

### Added — Motion Graphics Templates
- Lower thirds (clean bar, bold bar)
- Title cards (centered, cinematic)
- Intro fade-in cards
- Outro / subscribe end cards
- Chapter markers
- Generic text overlays at any position and time

### Added — Auto-Reframe
- Face detection for smart cropping (landscape to reel)
- Smooth crop path (no jitter)
- Center-crop fallback when no face detected

### Added — Multi-Platform Export
- 10 platform presets: TikTok, YouTube Shorts, YouTube HD, YouTube 4K, Instagram Reel, Instagram Post, Twitter/X, LinkedIn, Web Optimized, Pro Master
- 5 quality tiers: draft, standard, high, maximum, lossless
- Thumbnail generation (single frame or contact sheet grid)
- Watermarking (image or text)
- Batch multi-platform export

### Added — Brand System
- 5 built-in brand presets (Clean White, Bold Dark, Neon Pop, Minimal, Warm Creator)
- Custom brand save / load / delete
- Per-brand caption colors, sizes, emphasis styles, positioning

---

## [1.0.0] — 2026-04-16 — "First Cut"

Initial release. Core AI editing pipeline.

### Added
- Example video style analysis (pacing, scene detection, color profiling, audio)
- Whisper AI transcription with word-level timestamps
- AI Director — Claude-powered intelligent edit planning
- FFmpeg video editing engine (cuts, joins, color adjustments, captions)
- Reel (9:16), landscape (16:9), and square (1:1) output formats
- Flask REST API with web UI and agent endpoints
- Dark Premiere-style web interface with drag-and-drop
- Real-time progress via Server-Sent Events
- Agent API for Claude Code and AgentHub integration
- curl installer (`install.sh`)
- Runs on `127.0.0.1:12795`
