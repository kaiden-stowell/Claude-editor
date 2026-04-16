"""
Premium Visual Effects — LUTs, speed ramping, zoom, Ken Burns, picture-in-picture.

Professional-grade visual effects powered by FFmpeg filters.
"""

import os
import subprocess
import json
import shutil
import tempfile


# ─── Built-in Cinematic LUTs (FFmpeg eq/colorbalance chains) ─────────────

LUTS = {
    'cinematic-warm': {
        'name': 'Cinematic Warm',
        'description': 'Hollywood warm tones with lifted shadows',
        'filter': 'colorbalance=rs=0.05:gs=-0.02:bs=-0.05:rm=0.08:gm=0.02:bm=-0.03:rh=0.03:gh=0.01:bh=-0.02,eq=contrast=1.1:brightness=0.02:saturation=1.15',
    },
    'cinematic-cool': {
        'name': 'Cinematic Cool',
        'description': 'Teal and orange color grade',
        'filter': 'colorbalance=rs=-0.03:gs=-0.05:bs=0.08:rm=0.06:gm=-0.02:bm=-0.04:rh=0.02:gh=-0.01:bh=0.05,eq=contrast=1.15:brightness=-0.02:saturation=1.1',
    },
    'moody-dark': {
        'name': 'Moody Dark',
        'description': 'Dark, desaturated moody look',
        'filter': 'eq=contrast=1.3:brightness=-0.08:saturation=0.7,colorbalance=rs=-0.02:gs=-0.03:bs=0.04:rm=-0.02:gm=-0.01:bm=0.03',
    },
    'vintage-film': {
        'name': 'Vintage Film',
        'description': 'Retro film grain with faded blacks',
        'filter': 'eq=contrast=0.9:brightness=0.05:saturation=0.8,colorbalance=rs=0.06:gs=0.03:bs=-0.04:rm=0.03:gm=0.02:bm=-0.02,curves=m=0.05/0.15:0.95/0.90',
    },
    'vibrant': {
        'name': 'Vibrant',
        'description': 'Punchy, saturated colors',
        'filter': 'eq=contrast=1.2:brightness=0.03:saturation=1.4,colorbalance=rs=0.02:gs=0.01:bs=0.01',
    },
    'black-white': {
        'name': 'Black & White',
        'description': 'High contrast monochrome',
        'filter': 'hue=s=0,eq=contrast=1.3:brightness=0.02',
    },
    'golden-hour': {
        'name': 'Golden Hour',
        'description': 'Warm golden sunset tones',
        'filter': 'colorbalance=rs=0.1:gs=0.05:bs=-0.08:rm=0.12:gm=0.04:bm=-0.06,eq=brightness=0.04:saturation=1.2:contrast=1.05',
    },
    'cyberpunk': {
        'name': 'Cyberpunk',
        'description': 'Neon-tinged futuristic look',
        'filter': 'colorbalance=rs=-0.05:gs=-0.08:bs=0.12:rm=0.1:gm=-0.05:bm=0.08,eq=contrast=1.25:saturation=1.3:brightness=-0.03',
    },
    'pastel': {
        'name': 'Pastel',
        'description': 'Soft, light pastel tones',
        'filter': 'eq=brightness=0.08:contrast=0.85:saturation=0.75,colorbalance=rs=0.04:gs=0.02:bs=0.03',
    },
    'high-contrast': {
        'name': 'High Contrast',
        'description': 'Bold, punchy contrast',
        'filter': 'eq=contrast=1.5:brightness=-0.02:saturation=1.1',
    },
}


def apply_lut(input_path, output_path, lut_name):
    """Apply a built-in LUT/color grade to a video."""
    if lut_name not in LUTS:
        shutil.copy2(input_path, output_path)
        return

    lut = LUTS[lut_name]
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', lut['filter'],
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'copy',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"LUT application failed: {result.stderr}")


def apply_custom_lut_file(input_path, output_path, lut_file_path):
    """Apply a custom .cube LUT file."""
    if not os.path.exists(lut_file_path):
        raise FileNotFoundError(f"LUT file not found: {lut_file_path}")

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', f"lut3d='{lut_file_path}'",
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'copy',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Custom LUT failed: {result.stderr}")


# ─── Speed Ramping ───────────────────────────────────────────────────────

def apply_speed_ramp(input_path, output_path, speed_points):
    """
    Apply speed changes to video segments.

    speed_points: list of {start, end, speed}
        speed: 0.5 = half speed (slow-mo), 2.0 = double speed, 1.0 = normal
    """
    if not speed_points:
        shutil.copy2(input_path, output_path)
        return

    temp_dir = tempfile.mkdtemp(prefix='speed_ramp_')
    segments = []

    try:
        # Get video duration
        probe = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', input_path],
            capture_output=True, text=True
        )
        total_dur = float(json.loads(probe.stdout)['format']['duration'])

        # Sort speed points by start time
        points = sorted(speed_points, key=lambda p: p['start'])

        # Fill gaps with normal speed
        full_points = []
        cursor = 0.0
        for p in points:
            if p['start'] > cursor:
                full_points.append({'start': cursor, 'end': p['start'], 'speed': 1.0})
            full_points.append(p)
            cursor = p['end']
        if cursor < total_dur:
            full_points.append({'start': cursor, 'end': total_dur, 'speed': 1.0})

        # Process each segment
        for i, pt in enumerate(full_points):
            seg_path = os.path.join(temp_dir, f'speed_{i:03d}.mp4')
            speed = float(pt['speed'])

            # PTS modification for speed change
            video_filter = f"setpts={1.0/speed}*PTS"
            audio_filter = f"atempo={speed}"

            # atempo only supports 0.5-2.0 range, chain for extreme values
            if speed > 2.0:
                audio_filter = f"atempo=2.0,atempo={speed/2.0}"
            elif speed < 0.5:
                audio_filter = f"atempo=0.5,atempo={speed/0.5}"

            cmd = [
                'ffmpeg', '-y',
                '-ss', str(pt['start']), '-to', str(pt['end']),
                '-i', input_path,
                '-vf', video_filter,
                '-af', audio_filter,
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                '-c:a', 'aac', '-b:a', '192k',
                output_path if len(full_points) == 1 else seg_path,
            ]
            subprocess.run(cmd, capture_output=True, text=True)
            if len(full_points) > 1:
                segments.append(seg_path)

        if len(segments) > 1:
            _concat_files(segments, output_path)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ─── Zoom / Ken Burns Effect ────────────────────────────────────────────

def apply_zoom_effect(input_path, output_path, zoom_points):
    """
    Apply zoom/pan effects to specific moments.

    zoom_points: list of {start, end, zoom_start, zoom_end, x, y}
        zoom_start/end: 1.0 = no zoom, 1.5 = 50% zoom in
        x, y: center point (0.5, 0.5 = center)
    """
    if not zoom_points:
        shutil.copy2(input_path, output_path)
        return

    # Build zoompan filter chain
    filters = []
    for zp in zoom_points:
        start = float(zp['start'])
        end = float(zp['end'])
        z_start = float(zp.get('zoom_start', 1.0))
        z_end = float(zp.get('zoom_end', 1.5))
        cx = float(zp.get('x', 0.5))
        cy = float(zp.get('y', 0.5))

        # Use the zoompan filter with enable expression
        duration_frames = (end - start) * 30  # Assume 30fps
        z_expr = f"{z_start}+({z_end}-{z_start})*on/{duration_frames}"

        zp_filter = (
            f"zoompan=z='{z_expr}'"
            f":x='(iw-iw/zoom)*{cx}'"
            f":y='(ih-ih/zoom)*{cy}'"
            f":d={int(duration_frames)}"
            f":s=1920x1080"
            f":fps=30"
        )
        filters.append(zp_filter)

    # For simplicity, apply to the whole video if there's one zoom point
    if len(filters) == 1:
        cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-vf', filters[0],
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
            '-c:a', 'copy',
            '-movflags', '+faststart',
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            shutil.copy2(input_path, output_path)
    else:
        shutil.copy2(input_path, output_path)


def apply_ken_burns(input_path, output_path, duration=5.0, direction='zoom_in'):
    """Apply Ken Burns (slow zoom + pan) to an image or video."""
    if direction == 'zoom_in':
        z_expr = "1+0.002*on"
    elif direction == 'zoom_out':
        z_expr = "1.5-0.002*on"
    else:
        z_expr = "1+0.001*on"

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', f"zoompan=z='{z_expr}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d={int(duration*30)}:s=1920x1080:fps=30",
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-t', str(duration),
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        shutil.copy2(input_path, output_path)


# ─── Picture-in-Picture ─────────────────────────────────────────────────

def apply_pip(main_path, pip_path, output_path, position='bottom-right',
              scale=0.3, start=0, end=None, border=True):
    """
    Overlay a picture-in-picture video on the main video.

    position: top-left, top-right, bottom-left, bottom-right, center
    scale: size relative to main video (0.3 = 30%)
    """
    pos_map = {
        'top-left': f'x=20:y=20',
        'top-right': f'x=W-w-20:y=20',
        'bottom-left': f'x=20:y=H-h-20',
        'bottom-right': f'x=W-w-20:y=H-h-20',
        'center': f'x=(W-w)/2:y=(H-h)/2',
    }
    pos = pos_map.get(position, pos_map['bottom-right'])

    # Build filter
    pip_scale = f"[1:v]scale=iw*{scale}:ih*{scale}"
    if border:
        pip_scale += f",drawbox=x=0:y=0:w=iw:h=ih:color=white:t=2"
    pip_scale += "[pip]"

    overlay = f"[0:v][pip]overlay={pos}"
    if start or end:
        enable = f":enable='between(t,{start},{end or 9999})'"
        overlay += enable

    filter_complex = f"{pip_scale};{overlay}"

    cmd = [
        'ffmpeg', '-y', '-i', main_path, '-i', pip_path,
        '-filter_complex', filter_complex,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'copy',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"PiP failed: {result.stderr}")


# ─── Film Grain ──────────────────────────────────────────────────────────

def apply_film_grain(input_path, output_path, intensity='medium'):
    """Add film grain overlay for a cinematic look."""
    strength_map = {'light': 5, 'medium': 12, 'heavy': 25}
    strength = strength_map.get(intensity, 12)

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', f"noise=alls={strength}:allf=t",
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'copy',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Film grain failed: {result.stderr}")


# ─── Vignette ────────────────────────────────────────────────────────────

def apply_vignette(input_path, output_path, intensity=0.4):
    """Add vignette (darkened edges) effect."""
    angle = f"PI/{2 + (1 - intensity) * 3}"

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', f"vignette=angle={angle}",
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'copy',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Vignette failed: {result.stderr}")


# ─── Letterbox (Cinematic Bars) ──────────────────────────────────────────

def apply_letterbox(input_path, output_path, ratio=2.35):
    """Add cinematic letterbox bars."""
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', f"crop=iw:iw/{ratio},pad=iw:iw/(16/9):(ow-iw)/2:(oh-ih)/2:black",
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'copy',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        shutil.copy2(input_path, output_path)


# ─── Sharpen ─────────────────────────────────────────────────────────────

def apply_sharpen(input_path, output_path, intensity='medium'):
    """Apply sharpening filter."""
    strength_map = {'light': '3:3:0.5', 'medium': '5:5:1.0', 'heavy': '5:5:1.5'}
    params = strength_map.get(intensity, strength_map['medium'])

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', f'unsharp={params}',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'copy',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Sharpen failed: {result.stderr}")


# ─── Utility ─────────────────────────────────────────────────────────────

def _concat_files(file_paths, output_path):
    """Concatenate multiple video files."""
    list_file = output_path + '.concat.txt'
    with open(list_file, 'w') as f:
        for p in file_paths:
            f.write(f"file '{p}'\n")

    cmd = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
        '-i', list_file,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'aac', '-b:a', '192k',
        '-movflags', '+faststart',
        output_path
    ]
    subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(list_file):
        os.remove(list_file)


def list_available_luts():
    """Return all available LUT presets."""
    return {k: {'name': v['name'], 'description': v['description']} for k, v in LUTS.items()}


def list_available_effects():
    """Return all available premium effects."""
    return {
        'luts': list_available_luts(),
        'speed_ramp': 'Variable speed changes (slow-mo, fast forward)',
        'zoom': 'Dynamic zoom on key moments',
        'ken_burns': 'Slow pan & zoom (great for images)',
        'pip': 'Picture-in-picture overlay',
        'film_grain': 'Cinematic film grain (light/medium/heavy)',
        'vignette': 'Darkened edge vignette',
        'letterbox': 'Cinematic widescreen bars',
        'sharpen': 'Video sharpening (light/medium/heavy)',
    }
