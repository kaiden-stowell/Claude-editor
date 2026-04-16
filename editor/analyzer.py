"""
Video Style Analyzer — extracts editing style from an example video.

Analyzes pacing, color profile, aspect ratio, scene structure, and audio
characteristics so the AI Director can replicate the style on new footage.
"""

import os
import json
import subprocess
import cv2
import numpy as np

def _probe_video(path):
    """Use ffprobe to get video metadata."""
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', '-show_streams', path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    return json.loads(result.stdout)


def _detect_scenes(path, threshold=27.0):
    """Detect scene changes using scenedetect."""
    try:
        from scenedetect import detect, ContentDetector
        scenes = detect(path, ContentDetector(threshold=threshold))
        return [
            {
                'start': scene[0].get_seconds(),
                'end': scene[1].get_seconds(),
                'duration': scene[1].get_seconds() - scene[0].get_seconds()
            }
            for scene in scenes
        ]
    except ImportError:
        return _detect_scenes_opencv(path)


def _detect_scenes_opencv(path):
    """Fallback scene detection using OpenCV frame differencing."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    scenes = []
    prev_frame = None
    scene_start = 0.0
    threshold = 40.0
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (160, 90))

        if prev_frame is not None:
            diff = cv2.absdiff(prev_frame, gray)
            mean_diff = np.mean(diff)
            if mean_diff > threshold:
                current_time = frame_idx / fps
                scenes.append({
                    'start': scene_start,
                    'end': current_time,
                    'duration': current_time - scene_start
                })
                scene_start = current_time

        prev_frame = gray
        frame_idx += 1

    total_duration = frame_idx / fps
    if scene_start < total_duration:
        scenes.append({
            'start': scene_start,
            'end': total_duration,
            'duration': total_duration - scene_start
        })

    cap.release()
    return scenes


def _analyze_colors(path, sample_count=20):
    """Sample frames and compute average color properties."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return {'brightness': 128, 'saturation': 128, 'contrast': 50}

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames < 1:
        cap.release()
        return {'brightness': 128, 'saturation': 128, 'contrast': 50}

    step = max(1, total_frames // sample_count)
    brightness_vals = []
    saturation_vals = []
    contrast_vals = []

    for i in range(0, total_frames, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        brightness_vals.append(float(np.mean(gray)))
        saturation_vals.append(float(np.mean(hsv[:, :, 1])))
        contrast_vals.append(float(np.std(gray)))

    cap.release()

    return {
        'brightness': round(np.mean(brightness_vals), 1) if brightness_vals else 128,
        'saturation': round(np.mean(saturation_vals), 1) if saturation_vals else 128,
        'contrast': round(np.mean(contrast_vals), 1) if contrast_vals else 50,
    }


def _detect_audio_properties(path):
    """Analyze audio characteristics using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_entries', 'stream=codec_type,duration,channels,sample_rate',
        '-select_streams', 'a', path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    has_audio = False
    audio_duration = 0

    if result.returncode == 0:
        data = json.loads(result.stdout)
        streams = data.get('streams', [])
        if streams:
            has_audio = True
            audio_duration = float(streams[0].get('duration', 0))

    # Detect mean volume
    mean_volume = -20.0
    if has_audio:
        cmd2 = [
            'ffmpeg', '-i', path, '-af', 'volumedetect',
            '-f', 'null', '-', '-v', 'quiet', '-stats'
        ]
        result2 = subprocess.run(cmd2, capture_output=True, text=True)
        stderr = result2.stderr
        for line in stderr.split('\n'):
            if 'mean_volume' in line:
                try:
                    mean_volume = float(line.split('mean_volume:')[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass

    return {
        'has_audio': has_audio,
        'audio_duration': round(audio_duration, 2),
        'mean_volume_db': round(mean_volume, 1),
    }


def analyze_video(path, progress_callback=None):
    """
    Analyze an example video and return a complete style profile.

    Returns a dict describing the video's editing style:
    - pacing (clip durations, cuts per minute)
    - color profile (brightness, saturation, contrast)
    - structure (scene count, total duration)
    - audio properties
    - aspect ratio and resolution
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Video not found: {path}")

    if progress_callback:
        progress_callback('analyzer', 10, 'Reading video metadata...')

    # 1. Probe metadata
    probe = _probe_video(path)
    video_stream = None
    for s in probe.get('streams', []):
        if s.get('codec_type') == 'video':
            video_stream = s
            break

    if not video_stream:
        raise ValueError("No video stream found in file")

    width = int(video_stream.get('width', 1920))
    height = int(video_stream.get('height', 1080))
    fps = eval(video_stream.get('r_frame_rate', '30/1'))
    total_duration = float(probe.get('format', {}).get('duration', 0))

    # Determine aspect ratio category
    ratio = width / height if height > 0 else 1.78
    if ratio > 1.5:
        aspect_category = 'landscape'  # 16:9
    elif ratio < 0.75:
        aspect_category = 'portrait'   # 9:16 (reels/shorts)
    else:
        aspect_category = 'square'     # 1:1

    if progress_callback:
        progress_callback('analyzer', 30, 'Detecting scenes...')

    # 2. Scene detection
    scenes = _detect_scenes(path)

    clip_durations = [s['duration'] for s in scenes] if scenes else [total_duration]
    avg_clip_duration = np.mean(clip_durations) if clip_durations else total_duration
    cuts_per_minute = (len(scenes) / total_duration * 60) if total_duration > 0 and len(scenes) > 1 else 0

    # Categorize pacing
    if avg_clip_duration < 1.5:
        pacing_style = 'very_fast'
    elif avg_clip_duration < 3.0:
        pacing_style = 'fast'
    elif avg_clip_duration < 6.0:
        pacing_style = 'medium'
    elif avg_clip_duration < 12.0:
        pacing_style = 'slow'
    else:
        pacing_style = 'very_slow'

    if progress_callback:
        progress_callback('analyzer', 60, 'Analyzing colors...')

    # 3. Color analysis
    colors = _analyze_colors(path)

    if progress_callback:
        progress_callback('analyzer', 80, 'Analyzing audio...')

    # 4. Audio analysis
    audio = _detect_audio_properties(path)

    if progress_callback:
        progress_callback('analyzer', 100, 'Analysis complete!')

    return {
        'resolution': {'width': width, 'height': height},
        'aspect_ratio': round(ratio, 2),
        'aspect_category': aspect_category,
        'fps': round(fps, 2),
        'total_duration': round(total_duration, 2),
        'scene_count': len(scenes),
        'scenes': scenes,
        'pacing': {
            'avg_clip_duration': round(avg_clip_duration, 2),
            'min_clip_duration': round(min(clip_durations), 2) if clip_durations else 0,
            'max_clip_duration': round(max(clip_durations), 2) if clip_durations else 0,
            'cuts_per_minute': round(cuts_per_minute, 1),
            'style': pacing_style,
        },
        'colors': colors,
        'audio': audio,
    }
