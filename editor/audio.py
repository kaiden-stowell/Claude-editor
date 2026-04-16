"""
Premium Audio Processing — normalization, noise reduction, ducking, silence removal.

Professional audio treatment using FFmpeg audio filters.
"""

import os
import subprocess
import json
import shutil
import tempfile


# ─── Audio Normalization ─────────────────────────────────────────────────

def normalize_audio(input_path, output_path, target_lufs=-14.0):
    """
    Normalize audio to a target loudness (LUFS).
    -14 LUFS is standard for social media.
    -16 LUFS for podcasts.
    -23 LUFS for broadcast.
    """
    # Two-pass loudnorm for accurate normalization
    # Pass 1: Measure
    cmd1 = [
        'ffmpeg', '-i', input_path,
        '-af', f'loudnorm=I={target_lufs}:TP=-1.5:LRA=11:print_format=json',
        '-f', 'null', '-'
    ]
    result1 = subprocess.run(cmd1, capture_output=True, text=True)

    # Parse measured values from stderr
    stderr = result1.stderr
    measured = {}
    try:
        # Find JSON in output
        json_start = stderr.rfind('{')
        json_end = stderr.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            measured = json.loads(stderr[json_start:json_end])
    except json.JSONDecodeError:
        pass

    # Pass 2: Apply with measured values
    if measured:
        mi = measured.get('input_i', '-24.0')
        mtp = measured.get('input_tp', '-2.0')
        mlra = measured.get('input_lra', '7.0')
        mt = measured.get('input_thresh', '-34.0')
        mo = measured.get('target_offset', '0.0')

        loudnorm = (
            f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11"
            f":measured_I={mi}:measured_TP={mtp}"
            f":measured_LRA={mlra}:measured_thresh={mt}"
            f":offset={mo}:linear=true"
        )
    else:
        loudnorm = f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11"

    cmd2 = [
        'ffmpeg', '-y', '-i', input_path,
        '-af', loudnorm,
        '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '192k',
        '-movflags', '+faststart',
        output_path
    ]
    result2 = subprocess.run(cmd2, capture_output=True, text=True)
    if result2.returncode != 0:
        raise RuntimeError(f"Audio normalization failed: {result2.stderr}")


# ─── Noise Reduction ────────────────────────────────────────────────────

def reduce_noise(input_path, output_path, strength='medium'):
    """
    Apply noise reduction using FFmpeg's afftdn filter.

    strength: light (subtle), medium (balanced), heavy (aggressive)
    """
    strength_map = {
        'light': 'afftdn=nr=6:nf=-25',
        'medium': 'afftdn=nr=12:nf=-20',
        'heavy': 'afftdn=nr=20:nf=-15',
    }
    af = strength_map.get(strength, strength_map['medium'])

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-af', af,
        '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '192k',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Noise reduction failed: {result.stderr}")


# ─── Audio Ducking ───────────────────────────────────────────────────────

def apply_ducking(video_path, music_path, output_path, duck_level=0.15,
                  speech_threshold=-30):
    """
    Mix background music with auto-ducking during speech.

    The music volume is lowered when speech is detected in the video.
    duck_level: music volume during speech (0.15 = 15% volume)
    """
    # Use sidechaincompress to duck music based on speech audio
    filter_complex = (
        f"[0:a]asplit=2[speech][sc];"
        f"[1:a]volume=0.3[music];"
        f"[music][sc]sidechaincompress=threshold={speech_threshold}dB"
        f":ratio=8:attack=200:release=1000:level_sc=1[ducked];"
        f"[speech][ducked]amix=inputs=2:duration=first:weights=1 0.4[aout]"
    )

    cmd = [
        'ffmpeg', '-y', '-i', video_path, '-i', music_path,
        '-filter_complex', filter_complex,
        '-map', '0:v', '-map', '[aout]',
        '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '192k',
        '-movflags', '+faststart',
        '-shortest',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Audio ducking failed: {result.stderr}")


def mix_background_music(video_path, music_path, output_path, music_volume=0.2):
    """Mix background music with video at a set volume (no ducking)."""
    filter_complex = (
        f"[1:a]volume={music_volume}[music];"
        f"[0:a][music]amix=inputs=2:duration=first[aout]"
    )

    cmd = [
        'ffmpeg', '-y', '-i', video_path, '-i', music_path,
        '-filter_complex', filter_complex,
        '-map', '0:v', '-map', '[aout]',
        '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '192k',
        '-movflags', '+faststart',
        '-shortest',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Music mixing failed: {result.stderr}")


# ─── Silence Detection & Removal ────────────────────────────────────────

def detect_silence(video_path, min_duration=0.5, threshold=-35):
    """
    Detect silent segments in video.

    Returns list of {start, end, duration} for each silent period.
    """
    cmd = [
        'ffmpeg', '-i', video_path,
        '-af', f'silencedetect=noise={threshold}dB:d={min_duration}',
        '-f', 'null', '-'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    silences = []
    current_start = None

    for line in result.stderr.split('\n'):
        if 'silence_start:' in line:
            try:
                current_start = float(line.split('silence_start:')[1].strip().split()[0])
            except (ValueError, IndexError):
                pass
        elif 'silence_end:' in line and current_start is not None:
            try:
                parts = line.split('silence_end:')[1].strip().split()
                end = float(parts[0])
                silences.append({
                    'start': round(current_start, 3),
                    'end': round(end, 3),
                    'duration': round(end - current_start, 3),
                })
                current_start = None
            except (ValueError, IndexError):
                pass

    return silences


def remove_silence(video_path, output_path, min_silence=0.5, threshold=-35,
                   keep_padding=0.1):
    """
    Remove silent segments from video (jump-cut style).

    min_silence: minimum silence duration to cut (seconds)
    threshold: audio level below which counts as silence (dB)
    keep_padding: seconds of silence to keep at cut points
    """
    silences = detect_silence(video_path, min_silence, threshold)

    if not silences:
        shutil.copy2(video_path, output_path)
        return {'segments_removed': 0, 'time_saved': 0}

    # Get total duration
    probe = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', video_path],
        capture_output=True, text=True
    )
    total_dur = float(json.loads(probe.stdout)['format']['duration'])

    # Build keep-segments (inverse of silence)
    keep_segments = []
    cursor = 0.0

    for s in silences:
        seg_start = cursor
        seg_end = s['start'] + keep_padding
        if seg_end > seg_start + 0.1:
            keep_segments.append({'start': seg_start, 'end': seg_end})
        cursor = s['end'] - keep_padding

    if cursor < total_dur:
        keep_segments.append({'start': max(cursor, 0), 'end': total_dur})

    if not keep_segments:
        shutil.copy2(video_path, output_path)
        return {'segments_removed': 0, 'time_saved': 0}

    # Extract and concatenate keep segments
    temp_dir = tempfile.mkdtemp(prefix='silence_rm_')
    seg_paths = []

    try:
        for i, seg in enumerate(keep_segments):
            seg_path = os.path.join(temp_dir, f'keep_{i:03d}.mp4')
            duration = seg['end'] - seg['start']
            cmd = [
                'ffmpeg', '-y',
                '-ss', str(seg['start']),
                '-i', video_path,
                '-t', str(duration),
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                '-c:a', 'aac', '-b:a', '192k',
                '-avoid_negative_ts', 'make_zero',
                seg_path
            ]
            subprocess.run(cmd, capture_output=True, text=True)
            seg_paths.append(seg_path)

        # Concatenate
        list_file = os.path.join(temp_dir, 'concat.txt')
        with open(list_file, 'w') as f:
            for p in seg_paths:
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

        time_saved = sum(s['duration'] for s in silences)
        return {
            'segments_removed': len(silences),
            'time_saved': round(time_saved, 2),
            'original_duration': round(total_dur, 2),
            'new_duration': round(total_dur - time_saved, 2),
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ─── Audio Enhancement ──────────────────────────────────────────────────

def enhance_voice(input_path, output_path):
    """Enhance voice clarity with EQ and compression."""
    # High-pass filter (remove rumble), presence boost, light compression
    af = (
        "highpass=f=80,"
        "lowpass=f=12000,"
        "equalizer=f=2500:t=q:w=1.5:g=3,"  # Presence boost
        "equalizer=f=200:t=q:w=2:g=-2,"     # Reduce muddiness
        "compand=attacks=0.1:decays=0.3:points=-80/-80|-45/-25|-27/-15|0/-5:gain=3"
    )

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-af', af,
        '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '192k',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Voice enhancement failed: {result.stderr}")


def add_audio_fade(input_path, output_path, fade_in=0.5, fade_out=1.0):
    """Add fade-in and fade-out to audio."""
    # Get duration for fade-out calculation
    probe = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', input_path],
        capture_output=True, text=True
    )
    total_dur = float(json.loads(probe.stdout)['format']['duration'])
    fade_out_start = total_dur - fade_out

    af_parts = []
    if fade_in > 0:
        af_parts.append(f"afade=t=in:st=0:d={fade_in}")
    if fade_out > 0:
        af_parts.append(f"afade=t=out:st={fade_out_start:.3f}:d={fade_out}")

    if not af_parts:
        shutil.copy2(input_path, output_path)
        return

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-af', ','.join(af_parts),
        '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '192k',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Audio fade failed: {result.stderr}")
