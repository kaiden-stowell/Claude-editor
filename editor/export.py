"""
Multi-Platform Export — presets, quality tiers, thumbnails, watermarks.

Export to platform-specific formats with proper encoding settings.
"""

import os
import subprocess
import json
import shutil


# ─── Platform Export Presets ─────────────────────────────────────────────

EXPORT_PRESETS = {
    'tiktok': {
        'name': 'TikTok / Reels',
        'width': 1080, 'height': 1920,
        'fps': 30, 'max_duration': 180,
        'video_bitrate': '6M', 'audio_bitrate': '128k',
        'codec': 'libx264', 'crf': 20,
    },
    'youtube-shorts': {
        'name': 'YouTube Shorts',
        'width': 1080, 'height': 1920,
        'fps': 30, 'max_duration': 60,
        'video_bitrate': '8M', 'audio_bitrate': '192k',
        'codec': 'libx264', 'crf': 18,
    },
    'youtube-hd': {
        'name': 'YouTube HD (1080p)',
        'width': 1920, 'height': 1080,
        'fps': 30, 'max_duration': None,
        'video_bitrate': '12M', 'audio_bitrate': '192k',
        'codec': 'libx264', 'crf': 18,
    },
    'youtube-4k': {
        'name': 'YouTube 4K',
        'width': 3840, 'height': 2160,
        'fps': 30, 'max_duration': None,
        'video_bitrate': '35M', 'audio_bitrate': '256k',
        'codec': 'libx264', 'crf': 16,
    },
    'instagram-reel': {
        'name': 'Instagram Reel',
        'width': 1080, 'height': 1920,
        'fps': 30, 'max_duration': 90,
        'video_bitrate': '6M', 'audio_bitrate': '128k',
        'codec': 'libx264', 'crf': 20,
    },
    'instagram-post': {
        'name': 'Instagram Post (Square)',
        'width': 1080, 'height': 1080,
        'fps': 30, 'max_duration': 60,
        'video_bitrate': '5M', 'audio_bitrate': '128k',
        'codec': 'libx264', 'crf': 20,
    },
    'twitter': {
        'name': 'Twitter/X Video',
        'width': 1920, 'height': 1080,
        'fps': 30, 'max_duration': 140,
        'video_bitrate': '8M', 'audio_bitrate': '192k',
        'codec': 'libx264', 'crf': 20,
    },
    'linkedin': {
        'name': 'LinkedIn Video',
        'width': 1920, 'height': 1080,
        'fps': 30, 'max_duration': 600,
        'video_bitrate': '8M', 'audio_bitrate': '192k',
        'codec': 'libx264', 'crf': 20,
    },
    'web-optimized': {
        'name': 'Web Optimized (Small File)',
        'width': 1280, 'height': 720,
        'fps': 30, 'max_duration': None,
        'video_bitrate': '3M', 'audio_bitrate': '128k',
        'codec': 'libx264', 'crf': 24,
    },
    'pro-master': {
        'name': 'Pro Master (Best Quality)',
        'width': None, 'height': None,  # Keep original
        'fps': None,  # Keep original
        'max_duration': None,
        'video_bitrate': '50M', 'audio_bitrate': '320k',
        'codec': 'libx264', 'crf': 14,
    },
}

# ─── Quality Tiers ───────────────────────────────────────────────────────

QUALITY_TIERS = {
    'draft': {'crf': 28, 'preset': 'ultrafast', 'description': 'Fast preview render'},
    'standard': {'crf': 22, 'preset': 'fast', 'description': 'Good quality, reasonable speed'},
    'high': {'crf': 18, 'preset': 'medium', 'description': 'High quality'},
    'maximum': {'crf': 14, 'preset': 'slow', 'description': 'Maximum quality, slow render'},
    'lossless': {'crf': 0, 'preset': 'veryslow', 'description': 'Lossless quality'},
}


def export_for_platform(input_path, output_path, platform='tiktok'):
    """Export video optimized for a specific platform."""
    if platform not in EXPORT_PRESETS:
        raise ValueError(f"Unknown platform: {platform}. Available: {list(EXPORT_PRESETS.keys())}")

    preset = EXPORT_PRESETS[platform]

    # Build FFmpeg command
    vf_parts = []

    # Scale if needed
    if preset['width'] and preset['height']:
        vf_parts.append(
            f"scale={preset['width']}:{preset['height']}"
            f":force_original_aspect_ratio=decrease,"
            f"pad={preset['width']}:{preset['height']}:(ow-iw)/2:(oh-ih)/2:black"
        )

    # FPS if specified
    if preset['fps']:
        vf_parts.append(f"fps={preset['fps']}")

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
    ]

    if vf_parts:
        cmd.extend(['-vf', ','.join(vf_parts)])

    cmd.extend([
        '-c:v', preset['codec'],
        '-crf', str(preset['crf']),
        '-b:v', preset['video_bitrate'],
        '-maxrate', preset['video_bitrate'],
        '-bufsize', str(int(preset['video_bitrate'].rstrip('Mk')) * 2) + preset['video_bitrate'][-1],
        '-c:a', 'aac', '-b:a', preset['audio_bitrate'],
        '-movflags', '+faststart',
        '-pix_fmt', 'yuv420p',
    ])

    # Duration limit
    if preset.get('max_duration'):
        cmd.extend(['-t', str(preset['max_duration'])])

    cmd.append(output_path)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Export failed: {result.stderr}")

    return {
        'platform': platform,
        'preset_name': preset['name'],
        'path': output_path,
        'size_mb': round(os.path.getsize(output_path) / (1024 * 1024), 2),
    }


def export_with_quality(input_path, output_path, quality='high'):
    """Export video with a specific quality tier."""
    if quality not in QUALITY_TIERS:
        quality = 'high'

    tier = QUALITY_TIERS[quality]

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-c:v', 'libx264',
        '-crf', str(tier['crf']),
        '-preset', tier['preset'],
        '-c:a', 'aac', '-b:a', '192k',
        '-movflags', '+faststart',
        '-pix_fmt', 'yuv420p',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Quality export failed: {result.stderr}")

    return {
        'quality': quality,
        'description': tier['description'],
        'path': output_path,
        'size_mb': round(os.path.getsize(output_path) / (1024 * 1024), 2),
    }


# ─── Multi-Platform Batch Export ─────────────────────────────────────────

def export_multi_platform(input_path, output_dir, platforms):
    """Export a video to multiple platform formats at once."""
    os.makedirs(output_dir, exist_ok=True)
    results = []

    for platform in platforms:
        if platform not in EXPORT_PRESETS:
            continue

        ext = '.mp4'
        output_path = os.path.join(output_dir, f'{platform}{ext}')

        try:
            result = export_for_platform(input_path, output_path, platform)
            results.append(result)
        except Exception as e:
            results.append({
                'platform': platform,
                'error': str(e),
            })

    return results


# ─── Thumbnail Generation ───────────────────────────────────────────────

def generate_thumbnail(video_path, output_path, time_offset=None,
                       width=1280, height=720):
    """
    Generate a thumbnail from a video frame.

    time_offset: timestamp in seconds (None = auto-detect best frame)
    """
    if time_offset is None:
        # Get duration, use 30% mark (usually a good frame)
        probe = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', video_path],
            capture_output=True, text=True
        )
        duration = float(json.loads(probe.stdout)['format']['duration'])
        time_offset = duration * 0.3

    cmd = [
        'ffmpeg', '-y',
        '-ss', str(time_offset),
        '-i', video_path,
        '-vframes', '1',
        '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black',
        '-q:v', '2',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Thumbnail generation failed: {result.stderr}")

    return {
        'path': output_path,
        'width': width,
        'height': height,
        'time_offset': round(time_offset, 2),
    }


def generate_thumbnail_grid(video_path, output_path, columns=4, rows=3,
                            thumb_width=320, thumb_height=180):
    """Generate a contact sheet / thumbnail grid from a video."""
    probe = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', video_path],
        capture_output=True, text=True
    )
    duration = float(json.loads(probe.stdout)['format']['duration'])
    total_frames = columns * rows
    interval = duration / (total_frames + 1)

    grid_width = thumb_width * columns
    grid_height = thumb_height * rows

    # Use FFmpeg select filter to pick frames at intervals
    select_expr = '+'.join(
        f"eq(n,{int(i * interval * 30)})" for i in range(1, total_frames + 1)
    )

    cmd = [
        'ffmpeg', '-y', '-i', video_path,
        '-vf', f"select='{select_expr}',scale={thumb_width}:{thumb_height},tile={columns}x{rows}",
        '-frames:v', '1',
        '-q:v', '2',
        '-vsync', 'vfr',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Thumbnail grid failed: {result.stderr}")

    return {'path': output_path, 'columns': columns, 'rows': rows}


# ─── Watermark ───────────────────────────────────────────────────────────

def apply_watermark(input_path, output_path, watermark_path=None,
                    watermark_text=None, position='bottom-right',
                    opacity=0.5, scale=0.15):
    """
    Apply a watermark (image or text) to a video.

    watermark_path: path to a PNG/image watermark
    watermark_text: text watermark (used if no image provided)
    """
    pos_map = {
        'top-left': 'x=20:y=20',
        'top-right': 'x=W-w-20:y=20',
        'bottom-left': 'x=20:y=H-h-20',
        'bottom-right': 'x=W-w-20:y=H-h-20',
        'center': 'x=(W-w)/2:y=(H-h)/2',
    }
    pos = pos_map.get(position, pos_map['bottom-right'])

    if watermark_path and os.path.exists(watermark_path):
        # Image watermark
        filter_complex = (
            f"[1:v]scale=iw*{scale}:ih*{scale},format=rgba,"
            f"colorchannelmixer=aa={opacity}[wm];"
            f"[0:v][wm]overlay={pos}[out]"
        )
        cmd = [
            'ffmpeg', '-y', '-i', input_path, '-i', watermark_path,
            '-filter_complex', filter_complex,
            '-map', '[out]', '-map', '0:a?',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
            '-c:a', 'copy',
            '-movflags', '+faststart',
            output_path
        ]
    elif watermark_text:
        # Text watermark
        text = watermark_text.replace("'", "\u2019")
        x_pos = '20' if 'left' in position else 'w-text_w-20'
        y_pos = '20' if 'top' in position else 'h-text_h-20'
        if position == 'center':
            x_pos = '(w-text_w)/2'
            y_pos = '(h-text_h)/2'

        vf = (
            f"drawtext=text='{text}'"
            f":fontsize=24:fontcolor=white@{opacity}"
            f":x={x_pos}:y={y_pos}"
            f":box=0"
        )
        cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-vf', vf,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
            '-c:a', 'copy',
            '-movflags', '+faststart',
            output_path
        ]
    else:
        shutil.copy2(input_path, output_path)
        return

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Watermark failed: {result.stderr}")


# ─── Listings ────────────────────────────────────────────────────────────

def list_export_presets():
    """Return all available export presets."""
    return {k: {'name': v['name'], 'resolution': f"{v['width']}x{v['height']}" if v['width'] else 'Original'}
            for k, v in EXPORT_PRESETS.items()}


def list_quality_tiers():
    """Return all quality tiers."""
    return QUALITY_TIERS
