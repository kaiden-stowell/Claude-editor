#!/usr/bin/env python3
"""
Claude Editor — AI-powered video editor with agent integration.

Supports three modes of operation:
1. Web UI — drag-and-drop interface at http://127.0.0.1:12795
2. Agent API — REST endpoints for Claude Code / AgentHub integration
3. CLI — command-line usage for scripting

Upload an example video to teach the AI your editing style,
then upload raw footage and get a professionally edited reel back.
"""

import os
import uuid
import json
import threading
import time
import subprocess
import shutil
import urllib.request
import base64
from flask import Flask, request, jsonify, send_file, render_template, Response
from flask_cors import CORS
from config import Config
from version import VERSION, FULL_VERSION, CODENAME, version_info
from editor.analyzer import analyze_video
from editor.transcriber import transcribe_video
from editor.ai_director import create_edit_plan
from editor.video_editor import execute_edit
from editor.brand import (
    get_brand, save_brand, list_brands, delete_brand,
    brand_to_caption_style, PRESETS, DEFAULT_BRAND
)
from editor.effects import list_available_effects, list_available_luts, LUTS
from editor.audio import detect_silence, remove_silence
from editor.captions import list_caption_styles
from editor.export import (
    export_for_platform, export_multi_platform, export_with_quality,
    generate_thumbnail, list_export_presets, list_quality_tiers
)
from editor.transitions import list_transitions
from editor.stabilize import stabilize_video, detect_shakiness
from editor.chromakey import apply_chroma_key, apply_blur_background
from editor.beat_sync import detect_beats, create_beat_synced_edit
from editor.motion_graphics import list_templates as list_mg_templates
from editor.auto_reframe import auto_reframe

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
Config.init_dirs()

# In-memory job tracking
jobs = {}


def _allowed_file(filename):
    exts = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.wmv', '.flv'}
    return os.path.splitext(filename)[1].lower() in exts


def _progress_callback(job_id):
    """Create a progress callback bound to a job."""
    def callback(stage, percent, message):
        if job_id in jobs:
            jobs[job_id]['progress'][stage] = {
                'percent': percent,
                'message': message,
            }
            stages = ['analyzer', 'transcriber', 'ai_director', 'editor']
            total = 0
            for s in stages:
                if s in jobs[job_id]['progress']:
                    total += jobs[job_id]['progress'][s]['percent']
            jobs[job_id]['overall_percent'] = int(total / len(stages))
            jobs[job_id]['current_message'] = message
    return callback


def _process_job(job_id):
    """Run the full editing pipeline in a background thread."""
    job = jobs[job_id]
    cb = _progress_callback(job_id)

    try:
        job['status'] = 'analyzing'
        job['current_message'] = 'Analyzing example video style...'

        # Step 1: Analyze example video
        style_profile = analyze_video(job['example_path'], progress_callback=cb)
        job['style_profile'] = style_profile

        # Override aspect ratio if user requested a specific output format
        output_format = job.get('output_format', 'match')
        if output_format == 'reel':
            style_profile['aspect_category'] = 'portrait'
            style_profile['target_resolution'] = {'width': 1080, 'height': 1920}
        elif output_format == 'landscape':
            style_profile['aspect_category'] = 'landscape'
            style_profile['target_resolution'] = {'width': 1920, 'height': 1080}
        elif output_format == 'square':
            style_profile['aspect_category'] = 'square'
            style_profile['target_resolution'] = {'width': 1080, 'height': 1080}

        # Step 2: Transcribe raw footage
        job['status'] = 'transcribing'
        job['current_message'] = 'Transcribing your footage...'
        transcript = transcribe_video(
            job['raw_path'],
            model_name=Config.WHISPER_MODEL,
            progress_callback=cb
        )
        job['transcript'] = transcript

        # Step 3: AI Director creates edit plan with brand-aware captions
        job['status'] = 'planning'
        job['current_message'] = 'AI is planning your edit...'

        # Apply brand to instructions
        brand_config = job.get('brand', DEFAULT_BRAND)
        brand_instructions = job.get('instructions', '')
        if brand_config.get('name') != 'Default':
            brand_instructions += f"\n\nBRAND STYLE: Use the brand '{brand_config['name']}'. "
            brand_instructions += f"Primary caption color: {brand_config.get('primary_color', 'white')}. "
            brand_instructions += f"Emphasis color: {brand_config.get('emphasis_color', 'gold')}. "
            brand_instructions += f"Caption position: {brand_config.get('caption_position', 'bottom')}."

        edit_plan = create_edit_plan(
            style_profile,
            transcript,
            model=Config.CLAUDE_MODEL,
            user_instructions=brand_instructions,
            progress_callback=cb
        )

        # Override caption style with brand
        edit_plan['caption_style'] = brand_to_caption_style(brand_config)
        job['edit_plan'] = edit_plan

        # Step 4: Execute the edit
        job['status'] = 'editing'
        job['current_message'] = 'Rendering your video...'
        output_filename = f"edited_{job_id}.mp4"
        output_path = os.path.join(Config.OUTPUT_FOLDER, output_filename)

        # Gather word-level timestamps for premium captions
        all_words = []
        for seg in transcript.get('segments', []):
            all_words.extend(seg.get('words', []))

        result = execute_edit(
            job['raw_path'],
            edit_plan,
            output_path,
            output_format=output_format,
            progress_callback=cb,
            transcript_words=all_words
        )

        job['status'] = 'complete'
        job['overall_percent'] = 100
        job['current_message'] = 'Your video is ready!'
        job['output'] = result

    except Exception as e:
        job['status'] = 'error'
        job['error'] = str(e)
        job['current_message'] = f'Error: {str(e)}'


# ─── Web UI ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


# ─── Health & Info ───────────────────────────────────────────────────────────

@app.route('/api/health')
def health():
    """Check system health and available dependencies."""
    checks = {}

    import subprocess
    try:
        r = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        checks['ffmpeg'] = r.returncode == 0
    except FileNotFoundError:
        checks['ffmpeg'] = False

    try:
        import whisper
        checks['whisper'] = True
    except ImportError:
        checks['whisper'] = False

    checks['claude_cli'] = Config.has_claude()

    try:
        import cv2
        checks['opencv'] = True
    except ImportError:
        checks['opencv'] = False

    all_ok = all(checks.values())
    return jsonify({'healthy': all_ok, 'checks': checks})


@app.route('/api/info')
def info():
    """Return editor capabilities and version for agent discovery."""
    return jsonify({
        'name': 'Claude Editor',
        **version_info(),
        'description': 'AI video editor — learns style from example videos, edits raw footage with on-brand captions',
        'capabilities': [
            'style_analysis',
            'transcription',
            'ai_editing',
            'branded_captions',
            'reel_format',
            'landscape_format',
            'square_format',
            'lut_color_grading',
            'speed_ramping',
            'film_grain',
            'vignette',
            'audio_normalization',
            'noise_reduction',
            'voice_enhancement',
            'silence_removal',
            'word_by_word_captions',
            '30_plus_transitions',
            'video_stabilization',
            'chroma_key',
            'beat_sync',
            'motion_graphics',
            'auto_reframe',
            'multi_platform_export',
            'thumbnail_generation',
            'watermarking',
            'picture_in_picture',
        ],
        'supported_formats': ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'],
        'output_formats': ['reel', 'landscape', 'square', 'match'],
        'agent_endpoints': {
            'edit': 'POST /api/agent/edit',
            'analyze': 'POST /api/agent/analyze',
            'transcribe': 'POST /api/agent/transcribe',
            'status': 'GET /api/status/<job_id>',
            'download': 'GET /api/download/<job_id>',
            'brands': 'GET /api/brands',
            'effects': 'GET /api/premium/effects',
            'transitions': 'GET /api/premium/transitions',
            'stabilize': 'POST /api/premium/stabilize',
            'chroma_key': 'POST /api/premium/chroma-key',
            'beat_sync': 'POST /api/premium/beat-sync',
            'auto_reframe': 'POST /api/premium/auto-reframe',
            'export': 'POST /api/premium/export/<job_id>',
            'thumbnail': 'POST /api/premium/thumbnail/<job_id>',
        },
    })


# ─── Integration Manifest (for Agent Hub discovery) ──────────────────────────

@app.route('/api/integration-manifest')
def integration_manifest():
    """Manifest endpoint for agent-hub auto-discovery."""
    base_url = f"http://127.0.0.1:{Config.PORT}"
    return jsonify({
        'kind': 'local-hub',
        'slug': 'claude-editor',
        'name': 'Claude Editor',
        'version': VERSION,
        'base_url': base_url,
        'mode': 'local',
        'status': 'running',
        'desc': f'AI video editor — upload an example video to teach editing style, then edit raw footage with captions, color grading, and effects. Running at {base_url}.',
        'usage': '\n'.join([
            f'Claude Editor is running locally at {base_url}. It edits videos by learning style from an example video and applying it to raw footage.',
            '',
            'FULL EDIT (main workflow):',
            f'  curl -X POST {base_url}/api/agent/edit \\',
            '    -H "Content-Type: application/json" \\',
            '    -d \'{"example_video": "/path/to/example.mp4", "raw_footage": "/path/to/raw.mp4", "instructions": "Make it energetic", "output_format": "reel", "brand": "default", "wait": true}\'',
            '',
            'ANALYZE STYLE ONLY:',
            f'  curl -X POST {base_url}/api/agent/analyze -H "Content-Type: application/json" -d \'{{"video": "/path/to/video.mp4"}}\'',
            '',
            'TRANSCRIBE ONLY:',
            f'  curl -X POST {base_url}/api/agent/transcribe -H "Content-Type: application/json" -d \'{{"video": "/path/to/video.mp4"}}\'',
            '',
            'CHECK STATUS:',
            f'  curl -s {base_url}/api/status/{{job_id}}',
            f'  curl -s {base_url}/api/stream/{{job_id}}    # SSE stream for real-time progress',
            '',
            'DOWNLOAD RESULT:',
            f'  curl -s {base_url}/api/download/{{job_id}} -o output.mp4',
            '',
            'LIST JOBS:',
            f'  curl -s {base_url}/api/jobs',
            '',
            'BRANDS:',
            f'  curl -s {base_url}/api/brands              # list brands',
            f'  curl -X PUT {base_url}/api/brands/my-brand -H "Content-Type: application/json" -d \'{{"primary_color": "#FFFFFF", "accent_color": "#FFD700"}}\'',
            '',
            'EXPORT:',
            f'  curl -X POST {base_url}/api/premium/export/{{job_id}} -H "Content-Type: application/json" -d \'{{"platform": "tiktok"}}\'',
            f'  # platforms: tiktok, youtube-shorts, youtube-hd, youtube-4k, instagram-reel, instagram-post, twitter, linkedin, web-optimized, pro-master',
            '',
            'THUMBNAIL:',
            f'  curl -X POST {base_url}/api/premium/thumbnail/{{job_id}} -H "Content-Type: application/json" -d \'{{}}\'',
            '',
            'HEALTH:',
            f'  curl -s {base_url}/api/health',
            '',
            'OUTPUT FORMATS: reel (9:16), landscape (16:9), square (1:1)',
            'LUTS: cinematic-warm, cinematic-cool, moody-dark, vintage-film, vibrant, golden-hour, cyberpunk, pastel, high-contrast, black-white',
            'CAPTION STYLES: word-highlight, outline, glow, standard',
        ]),
    })


# ─── Update Check & Apply ────────────────────────────────────────────────────

REPO_API_URL = 'https://api.github.com/repos/kaiden-stowell/Claude-editor/contents/version.py?ref=main'
_cached_remote_version = None
_last_version_check = 0


def _get_local_version():
    return VERSION


def _parse_remote_version(content):
    """Extract version string from remote version.py content."""
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('VERSION') and '=' in line and not line.startswith('VERSION_'):
            val = line.split('=', 1)[1].strip().strip('"').strip("'")
            if val and val[0].isdigit():
                return val
    return '0.0.0'


@app.route('/api/update/check')
def update_check():
    """Check GitHub for a newer version."""
    global _cached_remote_version, _last_version_check

    local = _get_local_version()
    force = request.args.get('force') == '1'

    if not force and time.time() - _last_version_check < 120 and _cached_remote_version:
        return jsonify({
            'local': local,
            'remote': _cached_remote_version,
            'updateAvailable': _cached_remote_version != local,
        })

    try:
        req = urllib.request.Request(REPO_API_URL, headers={'User-Agent': 'Claude-Editor'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        content = base64.b64decode(data['content']).decode('utf-8')
        remote = _parse_remote_version(content)
        _cached_remote_version = remote
        _last_version_check = time.time()
        return jsonify({
            'local': local,
            'remote': remote,
            'updateAvailable': remote != local,
        })
    except Exception as e:
        return jsonify({
            'local': local,
            'remote': None,
            'updateAvailable': False,
            'error': str(e),
        })


@app.route('/api/update/apply', methods=['POST'])
def update_apply():
    """Submit pending bugs, pull latest from GitHub, and restart."""
    global _cached_remote_version, _last_version_check

    base_dir = Config.BASE_DIR
    git_dir = os.path.join(base_dir, '.git')

    if not os.path.isdir(git_dir):
        return jsonify({'error': 'Not a git repo. Run the install script first.'}), 400

    # Auto-submit pending bug reports before updating
    try:
        gh_bin = shutil.which('gh')
        if gh_bin:
            bugs = _load_bugs()
            pending = [b for b in bugs if b.get('status') == 'pending']
            if pending:
                for bug in pending:
                    body = f"**Type:** {bug.get('type', 'unknown')}\n"
                    body += f"**Version:** {bug.get('context', {}).get('version', 'unknown')}\n"
                    body += f"**Reported:** {bug.get('created_at', 'unknown')}\n\n"
                    if bug.get('description'):
                        body += f"## Description\n{bug['description']}\n\n"
                    if bug.get('stack'):
                        body += f"## Stack Trace\n```\n{bug['stack']}\n```\n"
                    body += "\n---\n*Auto-submitted during update*"
                    title = bug.get('title', 'Bug Report')[:256]
                    try:
                        r = subprocess.run(
                            [gh_bin, 'issue', 'create', '--repo', GITHUB_REPO,
                             '--title', f'[Auto] {title}', '--body', body, '--label', 'bug'],
                            capture_output=True, text=True, timeout=15
                        )
                        if r.returncode == 0:
                            bug['status'] = 'submitted'
                            bug['github_url'] = r.stdout.strip()
                    except Exception:
                        pass
                _save_bugs(bugs)
    except Exception:
        pass

    try:
        # Backup user data
        backup_name = f"pre-update_{time.strftime('%Y%m%d_%H%M%S')}"
        backup_dir = os.path.join(base_dir, 'backups', backup_name)
        os.makedirs(backup_dir, exist_ok=True)

        for folder in ['uploads', 'outputs', 'logs']:
            src = os.path.join(base_dir, folder)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(backup_dir, folder), dirs_exist_ok=True)

        env_file = os.path.join(base_dir, '.env')
        if os.path.isfile(env_file):
            shutil.copy2(env_file, os.path.join(backup_dir, '.env'))

        # Git pull
        try:
            subprocess.run(
                ['git', 'stash'],
                cwd=base_dir, capture_output=True, timeout=10
            )
        except Exception:
            pass

        try:
            subprocess.run(
                ['git', 'pull', '--ff-only', 'origin', 'main'],
                cwd=base_dir, capture_output=True, text=True, timeout=30, check=True
            )
        except subprocess.CalledProcessError:
            subprocess.run(
                ['git', 'fetch', 'origin', 'main'],
                cwd=base_dir, capture_output=True, timeout=30, check=True
            )
            subprocess.run(
                ['git', 'reset', '--hard', 'origin/main'],
                cwd=base_dir, capture_output=True, timeout=10, check=True
            )

        # Reinstall Python dependencies
        venv_pip = os.path.join(base_dir, 'venv', 'bin', 'pip')
        if os.path.isfile(venv_pip):
            subprocess.run(
                [venv_pip, 'install', '-r', os.path.join(base_dir, 'requirements.txt'), '-q'],
                cwd=base_dir, capture_output=True, timeout=120
            )

        _cached_remote_version = None
        _last_version_check = 0

        # Read new version
        new_version = _get_local_version()
        try:
            vp = os.path.join(base_dir, 'version.py')
            with open(vp) as f:
                new_version = _parse_remote_version(f.read())
        except Exception:
            pass

        # Schedule restart — launchd will restart us
        def _restart():
            time.sleep(1)
            os._exit(0)

        threading.Thread(target=_restart, daemon=True).start()

        return jsonify({'ok': True, 'version': new_version, 'restarting': True})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Bug Tracking ────────────────────────────────────────────────────────────

BUGS_FILE = os.path.join(Config.BASE_DIR, 'data', 'bugs.json')
GITHUB_REPO = 'kaiden-stowell/Claude-editor'


def _load_bugs():
    try:
        with open(BUGS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_bugs(bugs):
    os.makedirs(os.path.dirname(BUGS_FILE), exist_ok=True)
    with open(BUGS_FILE, 'w') as f:
        json.dump(bugs, f, indent=2)


@app.route('/api/bugs', methods=['GET'])
def list_bugs():
    return jsonify({'bugs': _load_bugs()})


@app.route('/api/bugs', methods=['POST'])
def report_bug():
    data = request.get_json(silent=True) or {}
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    error_type = data.get('type', 'user-report')
    stack = data.get('stack', '')
    context = data.get('context', {})

    if not title and not description and not stack:
        return jsonify({'error': 'Provide a title, description, or error details'}), 400

    bug = {
        'id': str(uuid.uuid4())[:8],
        'title': title or f'Auto-captured: {error_type}',
        'description': description,
        'type': error_type,
        'stack': stack[:2000] if stack else '',
        'context': {
            'version': VERSION,
            'platform': os.uname().sysname if hasattr(os, 'uname') else 'unknown',
            'python': os.popen('python3 --version 2>&1').read().strip(),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            **context,
        },
        'status': 'pending',
        'created_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
    }

    bugs = _load_bugs()
    bugs.append(bug)
    _save_bugs(bugs)

    return jsonify({'ok': True, 'bug': bug}), 201


@app.route('/api/bugs/<bug_id>', methods=['DELETE'])
def delete_bug(bug_id):
    bugs = _load_bugs()
    bugs = [b for b in bugs if b['id'] != bug_id]
    _save_bugs(bugs)
    return jsonify({'ok': True})


@app.route('/api/bugs/submit', methods=['POST'])
def submit_bugs_to_github():
    """Submit all pending bugs to GitHub as issues using gh CLI."""
    gh_bin = shutil.which('gh')
    if not gh_bin:
        return jsonify({'error': 'GitHub CLI (gh) not installed. Install it: brew install gh'}), 400

    try:
        auth_check = subprocess.run(
            [gh_bin, 'auth', 'status'],
            capture_output=True, text=True, timeout=10
        )
        if auth_check.returncode != 0:
            return jsonify({'error': 'Not logged in to GitHub. Run: gh auth login'}), 400
    except Exception as e:
        return jsonify({'error': f'gh auth check failed: {e}'}), 500

    bugs = _load_bugs()
    pending = [b for b in bugs if b.get('status') == 'pending']

    if not pending:
        return jsonify({'ok': True, 'submitted': 0, 'message': 'No pending bugs to submit'})

    submitted = 0
    errors = []

    for bug in pending:
        body = f"**Type:** {bug.get('type', 'unknown')}\n"
        body += f"**Version:** {bug.get('context', {}).get('version', 'unknown')}\n"
        body += f"**Platform:** {bug.get('context', {}).get('platform', 'unknown')}\n"
        body += f"**Reported:** {bug.get('created_at', 'unknown')}\n\n"

        if bug.get('description'):
            body += f"## Description\n{bug['description']}\n\n"

        if bug.get('stack'):
            body += f"## Stack Trace\n```\n{bug['stack']}\n```\n\n"

        ctx = bug.get('context', {})
        extra = {k: v for k, v in ctx.items() if k not in ('version', 'platform', 'python', 'timestamp')}
        if extra:
            body += f"## Context\n```json\n{json.dumps(extra, indent=2)}\n```\n\n"

        body += "---\n*Auto-reported from Claude Editor bug tracker*"

        title = bug.get('title', 'Bug Report')[:256]
        label = 'bug' if bug.get('type') != 'feature-request' else 'enhancement'

        try:
            result = subprocess.run(
                [gh_bin, 'issue', 'create',
                 '--repo', GITHUB_REPO,
                 '--title', f'[Auto] {title}',
                 '--body', body,
                 '--label', label],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                bug['status'] = 'submitted'
                bug['github_url'] = result.stdout.strip()
                submitted += 1
            else:
                errors.append(f"{bug['id']}: {result.stderr.strip()}")
        except Exception as e:
            errors.append(f"{bug['id']}: {str(e)}")

    _save_bugs(bugs)

    return jsonify({
        'ok': True,
        'submitted': submitted,
        'total': len(pending),
        'errors': errors if errors else None,
    })


# ─── File Upload ─────────────────────────────────────────────────────────────

@app.route('/api/upload/example', methods=['POST'])
def upload_example():
    """Upload an example video for style analysis."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename or not _allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Supported: MP4, MOV, AVI, MKV, WebM'}), 400

    file_id = str(uuid.uuid4())[:8]
    ext = os.path.splitext(file.filename)[1]
    save_name = f"example_{file_id}{ext}"
    save_path = os.path.join(Config.UPLOAD_FOLDER, save_name)
    file.save(save_path)

    return jsonify({
        'id': file_id,
        'filename': file.filename,
        'path': save_path,
        'size_mb': round(os.path.getsize(save_path) / (1024 * 1024), 2),
    })


@app.route('/api/upload/raw', methods=['POST'])
def upload_raw():
    """Upload raw footage to be edited."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename or not _allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Supported: MP4, MOV, AVI, MKV, WebM'}), 400

    file_id = str(uuid.uuid4())[:8]
    ext = os.path.splitext(file.filename)[1]
    save_name = f"raw_{file_id}{ext}"
    save_path = os.path.join(Config.UPLOAD_FOLDER, save_name)
    file.save(save_path)

    return jsonify({
        'id': file_id,
        'filename': file.filename,
        'path': save_path,
        'size_mb': round(os.path.getsize(save_path) / (1024 * 1024), 2),
    })


# ─── Processing Pipeline ────────────────────────────────────────────────────

@app.route('/api/process', methods=['POST'])
def start_processing():
    """Start the editing pipeline (web UI flow)."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    example_path = data.get('example_path')
    raw_path = data.get('raw_path')
    instructions = data.get('instructions', '')
    output_format = data.get('output_format', 'reel')
    brand_name = data.get('brand', 'default')

    if not example_path or not os.path.exists(example_path):
        return jsonify({'error': 'Example video not found'}), 400
    if not raw_path or not os.path.exists(raw_path):
        return jsonify({'error': 'Raw footage not found'}), 400
    if not Config.has_claude():
        return jsonify({'error': 'Claude Code CLI not found. Install it first: npm install -g @anthropic-ai/claude-code'}), 400

    brand_config = get_brand(brand_name)

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        'id': job_id,
        'status': 'queued',
        'overall_percent': 0,
        'current_message': 'Queued for processing...',
        'progress': {},
        'example_path': example_path,
        'raw_path': raw_path,
        'instructions': instructions,
        'output_format': output_format,
        'brand': brand_config,
        'created_at': time.time(),
    }

    thread = threading.Thread(target=_process_job, args=(job_id,), daemon=True)
    thread.start()

    return jsonify({'job_id': job_id, 'status': 'queued'})


@app.route('/api/status/<job_id>')
def job_status(job_id):
    """Get job processing status."""
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404

    job = jobs[job_id]
    response = {
        'id': job_id,
        'status': job['status'],
        'overall_percent': job.get('overall_percent', 0),
        'current_message': job.get('current_message', ''),
        'progress': job.get('progress', {}),
    }

    if job['status'] == 'complete':
        response['output'] = job.get('output', {})
        response['edit_plan'] = {
            'title': job.get('edit_plan', {}).get('title', ''),
            'concept': job.get('edit_plan', {}).get('concept', ''),
            'segments_used': len(job.get('edit_plan', {}).get('segments', [])),
        }
        if job.get('style_profile'):
            response['style_profile'] = {
                'pacing': job['style_profile'].get('pacing', {}),
                'aspect_category': job['style_profile'].get('aspect_category', ''),
                'total_duration': job['style_profile'].get('total_duration', 0),
            }
        if job.get('transcript'):
            response['transcript_preview'] = job['transcript'].get('text', '')[:500]

    if job['status'] == 'error':
        response['error'] = job.get('error', 'Unknown error')

    return jsonify(response)


@app.route('/api/stream/<job_id>')
def stream_status(job_id):
    """Server-Sent Events stream for real-time progress updates."""
    def generate():
        last_msg = ''
        while True:
            if job_id not in jobs:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                break

            job = jobs[job_id]
            msg = json.dumps({
                'status': job['status'],
                'overall_percent': job.get('overall_percent', 0),
                'current_message': job.get('current_message', ''),
            })

            if msg != last_msg:
                yield f"data: {msg}\n\n"
                last_msg = msg

            if job['status'] in ('complete', 'error'):
                final = {
                    'status': job['status'],
                    'overall_percent': job.get('overall_percent', 0),
                    'current_message': job.get('current_message', ''),
                }
                if job['status'] == 'complete':
                    final['output'] = job.get('output', {})
                else:
                    final['error'] = job.get('error', '')
                yield f"data: {json.dumps(final)}\n\n"
                break

            time.sleep(0.5)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/api/download/<job_id>')
def download(job_id):
    """Download the finished video."""
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404

    job = jobs[job_id]
    if job['status'] != 'complete':
        return jsonify({'error': 'Video not ready yet'}), 400

    output_path = job['output']['path']
    if not os.path.exists(output_path):
        return jsonify({'error': 'Output file not found'}), 404

    title = job.get('edit_plan', {}).get('title', 'edited_video')
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
    download_name = f"{safe_title}.mp4" if safe_title else "edited_video.mp4"

    return send_file(output_path, as_attachment=True, download_name=download_name)


@app.route('/api/edit-plan/<job_id>')
def get_edit_plan(job_id):
    """Get the full edit plan for a completed job."""
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404

    job = jobs[job_id]
    return jsonify({
        'style_profile': job.get('style_profile'),
        'transcript': job.get('transcript'),
        'edit_plan': job.get('edit_plan'),
    })


# ─── Brand Management ───────────────────────────────────────────────────────

@app.route('/api/brands')
def api_list_brands():
    """List all brand presets and saved brands."""
    return jsonify(list_brands())


@app.route('/api/brands/<name>', methods=['GET'])
def api_get_brand(name):
    """Get a specific brand config."""
    if name in PRESETS:
        return jsonify({**DEFAULT_BRAND, **PRESETS[name]})
    return jsonify(get_brand(name))


@app.route('/api/brands/<name>', methods=['PUT'])
def api_save_brand(name):
    """Save/update a brand config."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400
    brand = save_brand(name, data)
    return jsonify(brand)


@app.route('/api/brands/<name>', methods=['DELETE'])
def api_delete_brand(name):
    """Delete a saved brand."""
    if delete_brand(name):
        return jsonify({'deleted': True})
    return jsonify({'error': 'Brand not found'}), 404


# ─── Agent API (for Claude Code / AgentHub) ──────────────────────────────────

@app.route('/api/agent/edit', methods=['POST'])
def agent_edit():
    """
    All-in-one agent endpoint: provide file paths and get an edited video.

    This is designed for programmatic use by AI agents (Claude Code, AgentHub).
    Accepts local file paths directly — no file upload needed.

    JSON body:
    {
        "example_video": "/path/to/example.mp4",
        "raw_footage": "/path/to/raw.mp4",
        "instructions": "Make it energetic and fun",
        "output_format": "reel",
        "brand": "default",
        "output_path": "/optional/custom/output.mp4",
        "wait": false
    }

    If wait=true, blocks until complete and returns the result.
    If wait=false (default), returns immediately with a job_id for polling.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    example_path = data.get('example_video')
    raw_path = data.get('raw_footage')
    instructions = data.get('instructions', '')
    output_format = data.get('output_format', 'reel')
    brand_name = data.get('brand', 'default')
    wait = data.get('wait', False)

    if not example_path:
        return jsonify({'error': 'example_video path required'}), 400
    if not os.path.exists(example_path):
        return jsonify({'error': f'Example video not found: {example_path}'}), 400
    if not raw_path:
        return jsonify({'error': 'raw_footage path required'}), 400
    if not os.path.exists(raw_path):
        return jsonify({'error': f'Raw footage not found: {raw_path}'}), 400
    if not Config.has_claude():
        return jsonify({'error': 'Claude Code CLI not found. Install it first: npm install -g @anthropic-ai/claude-code'}), 400

    brand_config = get_brand(brand_name)
    custom_output = data.get('output_path')

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        'id': job_id,
        'status': 'queued',
        'overall_percent': 0,
        'current_message': 'Queued for processing...',
        'progress': {},
        'example_path': example_path,
        'raw_path': raw_path,
        'instructions': instructions,
        'output_format': output_format,
        'brand': brand_config,
        'custom_output': custom_output,
        'created_at': time.time(),
    }

    if wait:
        _process_job(job_id)
        job = jobs[job_id]
        if job['status'] == 'error':
            return jsonify({'error': job.get('error')}), 500
        return jsonify({
            'job_id': job_id,
            'status': 'complete',
            'output': job.get('output'),
            'edit_plan': {
                'title': job.get('edit_plan', {}).get('title'),
                'concept': job.get('edit_plan', {}).get('concept'),
            },
        })
    else:
        thread = threading.Thread(target=_process_job, args=(job_id,), daemon=True)
        thread.start()
        return jsonify({
            'job_id': job_id,
            'status': 'queued',
            'poll_url': f'/api/status/{job_id}',
            'stream_url': f'/api/stream/{job_id}',
            'download_url': f'/api/download/{job_id}',
        })


@app.route('/api/agent/analyze', methods=['POST'])
def agent_analyze():
    """
    Agent endpoint: analyze a video's editing style.

    JSON body: {"video": "/path/to/video.mp4"}
    Returns the full style profile.
    """
    data = request.get_json()
    if not data or not data.get('video'):
        return jsonify({'error': 'video path required'}), 400

    path = data['video']
    if not os.path.exists(path):
        return jsonify({'error': f'Video not found: {path}'}), 400

    try:
        profile = analyze_video(path)
        return jsonify(profile)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/agent/transcribe', methods=['POST'])
def agent_transcribe():
    """
    Agent endpoint: transcribe a video's audio.

    JSON body: {"video": "/path/to/video.mp4", "model": "base"}
    Returns the full transcript with timestamps.
    """
    data = request.get_json()
    if not data or not data.get('video'):
        return jsonify({'error': 'video path required'}), 400

    path = data['video']
    if not os.path.exists(path):
        return jsonify({'error': f'Video not found: {path}'}), 400

    model = data.get('model', Config.WHISPER_MODEL)

    try:
        transcript = transcribe_video(path, model_name=model)
        return jsonify(transcript)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/jobs')
def list_jobs():
    """List all jobs (for agent monitoring)."""
    job_list = []
    for jid, job in jobs.items():
        job_list.append({
            'id': jid,
            'status': job['status'],
            'overall_percent': job.get('overall_percent', 0),
            'current_message': job.get('current_message', ''),
            'created_at': job.get('created_at', 0),
        })
    job_list.sort(key=lambda j: j['created_at'], reverse=True)
    return jsonify(job_list)


# ─── Premium Features API ────────────────────────────────────────────────────

@app.route('/api/premium/effects')
def api_effects():
    """List all available premium effects."""
    return jsonify(list_available_effects())


@app.route('/api/premium/luts')
def api_luts():
    """List all available LUT color grades."""
    return jsonify(list_available_luts())


@app.route('/api/premium/caption-styles')
def api_caption_styles():
    """List all available caption styles."""
    return jsonify(list_caption_styles())


@app.route('/api/premium/export-presets')
def api_export_presets():
    """List all platform export presets."""
    return jsonify(list_export_presets())


@app.route('/api/premium/quality-tiers')
def api_quality_tiers():
    """List all quality tiers."""
    return jsonify(list_quality_tiers())


@app.route('/api/premium/export/<job_id>', methods=['POST'])
def api_export(job_id):
    """
    Export a completed job's video to a specific platform format.

    JSON body: {"platform": "tiktok"} or {"platforms": ["tiktok", "youtube-shorts"]}
    """
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404

    job = jobs[job_id]
    if job['status'] != 'complete':
        return jsonify({'error': 'Job not complete'}), 400

    data = request.get_json() or {}
    source = job['output']['path']

    platform = data.get('platform')
    platforms = data.get('platforms')

    if platforms:
        output_dir = os.path.join(Config.OUTPUT_FOLDER, f'export_{job_id}')
        results = export_multi_platform(source, output_dir, platforms)
        return jsonify({'exports': results})
    elif platform:
        output_path = os.path.join(
            Config.OUTPUT_FOLDER, f'export_{job_id}_{platform}.mp4'
        )
        result = export_for_platform(source, output_path, platform)
        return jsonify(result)
    else:
        return jsonify({'error': 'Specify platform or platforms'}), 400


@app.route('/api/premium/thumbnail/<job_id>', methods=['POST'])
def api_thumbnail(job_id):
    """Generate a thumbnail from a completed job's video."""
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404

    job = jobs[job_id]
    if job['status'] != 'complete':
        return jsonify({'error': 'Job not complete'}), 400

    data = request.get_json() or {}
    source = job['output']['path']
    time_offset = data.get('time_offset')

    thumb_path = os.path.join(Config.OUTPUT_FOLDER, f'thumb_{job_id}.jpg')
    result = generate_thumbnail(source, thumb_path, time_offset)
    return jsonify(result)


@app.route('/api/premium/thumbnail/<job_id>/download')
def api_thumbnail_download(job_id):
    """Download the thumbnail image."""
    thumb_path = os.path.join(Config.OUTPUT_FOLDER, f'thumb_{job_id}.jpg')
    if not os.path.exists(thumb_path):
        return jsonify({'error': 'Thumbnail not found. Generate it first.'}), 404
    return send_file(thumb_path, mimetype='image/jpeg')


@app.route('/api/premium/silence-detect', methods=['POST'])
def api_silence_detect():
    """Detect silent segments in a video (useful for jump-cut editing)."""
    data = request.get_json()
    if not data or not data.get('video'):
        return jsonify({'error': 'video path required'}), 400

    path = data['video']
    if not os.path.exists(path):
        return jsonify({'error': f'Video not found: {path}'}), 400

    min_duration = data.get('min_duration', 0.5)
    threshold = data.get('threshold', -35)

    silences = detect_silence(path, min_duration, threshold)
    return jsonify({
        'silences': silences,
        'total_silence': round(sum(s['duration'] for s in silences), 2),
        'silent_segments': len(silences),
    })


@app.route('/api/premium/silence-remove', methods=['POST'])
def api_silence_remove():
    """Auto-remove silent segments (jump-cut style)."""
    data = request.get_json()
    if not data or not data.get('video'):
        return jsonify({'error': 'video path required'}), 400

    path = data['video']
    if not os.path.exists(path):
        return jsonify({'error': f'Video not found: {path}'}), 400

    output_path = data.get('output', os.path.join(Config.OUTPUT_FOLDER, f'jumpcut_{uuid.uuid4().hex[:8]}.mp4'))
    result = remove_silence(path, output_path)
    return jsonify(result)


@app.route('/api/premium/transitions')
def api_transitions():
    """List all 30+ transitions."""
    return jsonify(list_transitions())


@app.route('/api/premium/stabilize', methods=['POST'])
def api_stabilize():
    """Stabilize shaky video (like Premiere's Warp Stabilizer)."""
    data = request.get_json()
    if not data or not data.get('video'):
        return jsonify({'error': 'video path required'}), 400

    path = data['video']
    if not os.path.exists(path):
        return jsonify({'error': f'Video not found: {path}'}), 400

    strength = data.get('strength', 'medium')
    output_path = data.get('output', os.path.join(Config.OUTPUT_FOLDER, f'stabilized_{uuid.uuid4().hex[:8]}.mp4'))

    try:
        result = stabilize_video(path, output_path, strength)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/premium/shake-detect', methods=['POST'])
def api_shake_detect():
    """Analyze how shaky a video is and recommend stabilization level."""
    data = request.get_json()
    if not data or not data.get('video'):
        return jsonify({'error': 'video path required'}), 400

    path = data['video']
    if not os.path.exists(path):
        return jsonify({'error': f'Video not found: {path}'}), 400

    result = detect_shakiness(path)
    return jsonify(result)


@app.route('/api/premium/chroma-key', methods=['POST'])
def api_chroma_key():
    """Green screen / chroma key removal."""
    data = request.get_json()
    if not data or not data.get('foreground'):
        return jsonify({'error': 'foreground video path required'}), 400
    if not data.get('background'):
        return jsonify({'error': 'background video/image path required'}), 400

    fg = data['foreground']
    bg = data['background']
    if not os.path.exists(fg) or not os.path.exists(bg):
        return jsonify({'error': 'File not found'}), 400

    color = data.get('key_color', 'green')
    output_path = data.get('output', os.path.join(Config.OUTPUT_FOLDER, f'keyed_{uuid.uuid4().hex[:8]}.mp4'))

    try:
        result = apply_chroma_key(fg, bg, output_path, color)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/premium/blur-background', methods=['POST'])
def api_blur_bg():
    """Create a blurred-background portrait mode effect."""
    data = request.get_json()
    if not data or not data.get('video'):
        return jsonify({'error': 'video path required'}), 400

    path = data['video']
    if not os.path.exists(path):
        return jsonify({'error': f'Video not found: {path}'}), 400

    output_path = data.get('output', os.path.join(Config.OUTPUT_FOLDER, f'blur_bg_{uuid.uuid4().hex[:8]}.mp4'))

    try:
        result = apply_blur_background(path, output_path)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/premium/beat-detect', methods=['POST'])
def api_beat_detect():
    """Detect beats in music/audio for beat-synced editing."""
    data = request.get_json()
    if not data or not data.get('audio'):
        return jsonify({'error': 'audio/video path required'}), 400

    path = data['audio']
    if not os.path.exists(path):
        return jsonify({'error': f'File not found: {path}'}), 400

    sensitivity = data.get('sensitivity', 'medium')
    result = detect_beats(path, sensitivity)
    return jsonify(result)


@app.route('/api/premium/beat-sync', methods=['POST'])
def api_beat_sync():
    """Create a beat-synced edit (cuts on the beat)."""
    data = request.get_json()
    if not data or not data.get('video') or not data.get('music'):
        return jsonify({'error': 'video and music paths required'}), 400

    video = data['video']
    music = data['music']
    if not os.path.exists(video) or not os.path.exists(music):
        return jsonify({'error': 'File not found'}), 400

    output_path = data.get('output', os.path.join(Config.OUTPUT_FOLDER, f'beatsync_{uuid.uuid4().hex[:8]}.mp4'))
    target_duration = data.get('duration', 30)

    try:
        result = create_beat_synced_edit(video, music, output_path, target_duration)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/premium/auto-reframe', methods=['POST'])
def api_auto_reframe():
    """Auto-reframe video with face/subject tracking."""
    data = request.get_json()
    if not data or not data.get('video'):
        return jsonify({'error': 'video path required'}), 400

    path = data['video']
    if not os.path.exists(path):
        return jsonify({'error': f'Video not found: {path}'}), 400

    target = data.get('format', 'reel')
    method = data.get('method', 'face')
    output_path = data.get('output', os.path.join(Config.OUTPUT_FOLDER, f'reframed_{uuid.uuid4().hex[:8]}.mp4'))

    try:
        result = auto_reframe(path, output_path, target, method)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/premium/templates')
def api_templates():
    """List motion graphics templates (lower thirds, titles, intros, outros)."""
    return jsonify(list_mg_templates())


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print()
    print("=" * 60)
    print(f"  {FULL_VERSION}")
    print(f"  Premium AI Video Editor")
    print("=" * 60)

    issues = []
    try:
        import whisper
    except ImportError:
        issues.append("  ! Whisper not installed: pip install openai-whisper")
    try:
        import cv2
    except ImportError:
        issues.append("  ! OpenCV not installed: pip install opencv-python-headless")

    import subprocess
    try:
        r = subprocess.run(['ffmpeg', '-version'], capture_output=True)
        if r.returncode != 0:
            issues.append("  ! FFmpeg not found")
    except FileNotFoundError:
        issues.append("  ! FFmpeg not found: install via your package manager")

    if not Config.has_claude():
        issues.append("  ! Claude Code CLI not found: npm install -g @anthropic-ai/claude-code")

    if issues:
        print("\n  Setup needed:")
        for i in issues:
            print(i)

    print()
    print("  Web UI:    http://127.0.0.1:12795")
    print("  Agent API: http://127.0.0.1:12795/api/agent/edit")
    print("  Health:    http://127.0.0.1:12795/api/health")
    print("=" * 60)
    print()

    app.run(host=Config.HOST, port=Config.PORT, debug=False)
