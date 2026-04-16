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
from flask import Flask, request, jsonify, send_file, render_template, Response
from flask_cors import CORS
from config import Config
from editor.analyzer import analyze_video
from editor.transcriber import transcribe_video
from editor.ai_director import create_edit_plan
from editor.video_editor import execute_edit
from editor.brand import (
    get_brand, save_brand, list_brands, delete_brand,
    brand_to_caption_style, PRESETS, DEFAULT_BRAND
)

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
            api_key=Config.ANTHROPIC_API_KEY,
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

        result = execute_edit(
            job['raw_path'],
            edit_plan,
            output_path,
            output_format=output_format,
            progress_callback=cb
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

    checks['anthropic_key'] = bool(Config.ANTHROPIC_API_KEY)

    try:
        import cv2
        checks['opencv'] = True
    except ImportError:
        checks['opencv'] = False

    all_ok = all(checks.values())
    return jsonify({'healthy': all_ok, 'checks': checks})


@app.route('/api/info')
def info():
    """Return editor capabilities for agent discovery."""
    return jsonify({
        'name': 'Claude Editor',
        'version': '1.0.0',
        'description': 'AI video editor — learns style from example videos, edits raw footage with on-brand captions',
        'capabilities': [
            'style_analysis',
            'transcription',
            'ai_editing',
            'branded_captions',
            'reel_format',
            'landscape_format',
            'square_format',
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
        },
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
    if not Config.ANTHROPIC_API_KEY:
        return jsonify({'error': 'ANTHROPIC_API_KEY not set. Export it before starting.'}), 400

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
    if not Config.ANTHROPIC_API_KEY:
        return jsonify({'error': 'ANTHROPIC_API_KEY not set'}), 400

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


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print()
    print("=" * 60)
    print("  Claude Editor — AI Video Editor")
    print("  Agent-ready | Reel-optimized | On-brand captions")
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

    if not Config.ANTHROPIC_API_KEY:
        issues.append("  ! ANTHROPIC_API_KEY not set: export ANTHROPIC_API_KEY=sk-...")

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
