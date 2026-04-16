"""
Video Stabilization — removes camera shake using FFmpeg vidstab/deshake.

Two-pass stabilization like Premiere's Warp Stabilizer.
"""

import os
import subprocess
import shutil
import tempfile


def stabilize_video(input_path, output_path, strength='medium', crop='keep'):
    """
    Stabilize shaky video footage.

    strength: light (subtle), medium (balanced), heavy (aggressive)
    crop: 'keep' (pad edges), 'crop' (crop to remove black borders)
    """
    strength_map = {
        'light': {'shakiness': 4, 'accuracy': 10, 'smoothing': 6, 'zoom': 2},
        'medium': {'shakiness': 6, 'accuracy': 12, 'smoothing': 12, 'zoom': 5},
        'heavy': {'shakiness': 10, 'accuracy': 15, 'smoothing': 20, 'zoom': 10},
    }
    params = strength_map.get(strength, strength_map['medium'])

    temp_dir = tempfile.mkdtemp(prefix='stabilize_')
    transforms_file = os.path.join(temp_dir, 'transforms.trf')

    try:
        # Pass 1: Analyze motion
        cmd1 = [
            'ffmpeg', '-y', '-i', input_path,
            '-vf', (
                f"vidstabdetect="
                f"shakiness={params['shakiness']}:"
                f"accuracy={params['accuracy']}:"
                f"result='{transforms_file}'"
            ),
            '-f', 'null', '-'
        ]
        result1 = subprocess.run(cmd1, capture_output=True, text=True)

        if result1.returncode != 0 or not os.path.exists(transforms_file):
            # Fallback to deshake (simpler, always available)
            return _deshake_fallback(input_path, output_path, params)

        # Pass 2: Apply stabilization
        border_mode = 'mirror' if crop == 'keep' else 'black'
        cmd2 = [
            'ffmpeg', '-y', '-i', input_path,
            '-vf', (
                f"vidstabtransform="
                f"smoothing={params['smoothing']}:"
                f"zoom={params['zoom']}:"
                f"input='{transforms_file}':"
                f"interpol=bicubic:"
                f"optzoom=1:"
                f"crop=keep:"
                f"border={border_mode}"
            ),
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
            '-c:a', 'copy',
            '-movflags', '+faststart',
            output_path
        ]
        result2 = subprocess.run(cmd2, capture_output=True, text=True)

        if result2.returncode != 0:
            return _deshake_fallback(input_path, output_path, params)

        return {
            'method': 'vidstab',
            'strength': strength,
            'path': output_path,
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _deshake_fallback(input_path, output_path, params):
    """Fallback stabilization using FFmpeg's built-in deshake filter."""
    rx = min(64, params['shakiness'] * 6)
    ry = min(64, params['shakiness'] * 6)

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', f'deshake=rx={rx}:ry={ry}',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'copy',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        # Last resort: just copy
        shutil.copy2(input_path, output_path)

    return {
        'method': 'deshake',
        'path': output_path,
    }


def detect_shakiness(video_path, sample_seconds=5):
    """
    Estimate how shaky a video is by analyzing motion vectors.
    Returns a shakiness score from 0 (stable) to 10 (very shaky).
    """
    # Use vidstabdetect with a short sample
    temp_dir = tempfile.mkdtemp(prefix='shake_detect_')
    trf = os.path.join(temp_dir, 'detect.trf')

    try:
        cmd = [
            'ffmpeg', '-y',
            '-t', str(sample_seconds),
            '-i', video_path,
            '-vf', f"vidstabdetect=shakiness=10:accuracy=15:result='{trf}'",
            '-f', 'null', '-'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0 or not os.path.exists(trf):
            return {'score': -1, 'recommendation': 'unknown'}

        # Parse the transforms file for average motion
        total_motion = 0
        count = 0
        with open(trf) as f:
            for line in f:
                if line.startswith('#'):
                    continue
                parts = line.strip().split()
                if len(parts) >= 4:
                    try:
                        dx = abs(float(parts[1]))
                        dy = abs(float(parts[2]))
                        total_motion += (dx + dy)
                        count += 1
                    except ValueError:
                        pass

        if count == 0:
            return {'score': 0, 'recommendation': 'none'}

        avg_motion = total_motion / count
        # Normalize to 0-10 scale
        score = min(10, avg_motion / 3)

        if score < 2:
            rec = 'none'
        elif score < 4:
            rec = 'light'
        elif score < 7:
            rec = 'medium'
        else:
            rec = 'heavy'

        return {
            'score': round(score, 1),
            'recommendation': rec,
            'avg_motion': round(avg_motion, 2),
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
