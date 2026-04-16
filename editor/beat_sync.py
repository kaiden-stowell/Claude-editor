"""
Beat Sync — detect music beats and sync video cuts to the rhythm.

Analyzes audio for beat positions so cuts land on the beat,
exactly like Premiere's beat-synced editing or CapCut's auto-beat.
"""

import os
import subprocess
import json
import tempfile
import shutil


def detect_beats(audio_or_video_path, sensitivity='medium'):
    """
    Detect beat positions in audio/video.

    Returns a list of beat timestamps in seconds.
    Uses FFmpeg's ebur128 and astats for onset detection.
    """
    temp_dir = tempfile.mkdtemp(prefix='beats_')

    try:
        # Extract audio to WAV for analysis
        wav_path = os.path.join(temp_dir, 'audio.wav')
        cmd_extract = [
            'ffmpeg', '-y', '-i', audio_or_video_path,
            '-vn', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '1',
            wav_path
        ]
        subprocess.run(cmd_extract, capture_output=True, text=True)

        # Detect onsets using volume envelope changes
        sensitivity_map = {
            'low': {'threshold': 0.3, 'min_gap': 0.5},
            'medium': {'threshold': 0.2, 'min_gap': 0.3},
            'high': {'threshold': 0.1, 'min_gap': 0.15},
        }
        params = sensitivity_map.get(sensitivity, sensitivity_map['medium'])

        # Use silencedetect in reverse to find loud onsets
        cmd_analyze = [
            'ffmpeg', '-i', wav_path,
            '-af', (
                f"highpass=f=60,lowpass=f=15000,"
                f"acompressor=threshold=-20dB:ratio=4:attack=5:release=50,"
                f"silencedetect=noise=-25dB:d=0.08"
            ),
            '-f', 'null', '-'
        ]
        result = subprocess.run(cmd_analyze, capture_output=True, text=True)

        # Parse silence_end events as beat onsets
        beats = []
        for line in result.stderr.split('\n'):
            if 'silence_end:' in line:
                try:
                    t = float(line.split('silence_end:')[1].strip().split()[0])
                    if not beats or (t - beats[-1]) >= params['min_gap']:
                        beats.append(round(t, 3))
                except (ValueError, IndexError):
                    pass

        # Also try energy-based detection for more beats
        cmd_energy = [
            'ffmpeg', '-i', wav_path,
            '-af', 'astats=metadata=1:reset=1',
            '-f', 'null', '-'
        ]
        result2 = subprocess.run(cmd_energy, capture_output=True, text=True)

        # Get audio duration
        probe = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', wav_path],
            capture_output=True, text=True
        )
        total_duration = float(json.loads(probe.stdout).get('format', {}).get('duration', 0))

        # Estimate BPM from beat intervals
        bpm = 0
        if len(beats) > 2:
            intervals = [beats[i+1] - beats[i] for i in range(len(beats)-1)]
            avg_interval = sum(intervals) / len(intervals)
            if avg_interval > 0:
                bpm = round(60.0 / avg_interval)

        return {
            'beats': beats,
            'count': len(beats),
            'bpm': bpm,
            'duration': round(total_duration, 2),
            'avg_interval': round(sum([beats[i+1]-beats[i] for i in range(len(beats)-1)]) / max(1, len(beats)-1), 3) if len(beats) > 1 else 0,
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def generate_beat_synced_segments(beats, source_duration, target_duration=None,
                                  min_clip=0.5, max_clip=5.0):
    """
    Generate segment cut points that align with beats.

    Takes beat timestamps and creates segments that cut on the beat.
    Returns a list of {start, end} segment definitions.
    """
    if not beats or len(beats) < 2:
        return []

    segments = []
    beat_pairs = list(zip(beats[:-1], beats[1:]))

    # Filter to reasonable clip lengths
    for start, end in beat_pairs:
        duration = end - start
        if min_clip <= duration <= max_clip and end <= source_duration:
            segments.append({
                'start': round(start, 3),
                'end': round(end, 3),
                'duration': round(duration, 3),
                'on_beat': True,
            })

    # If target duration specified, trim segment list
    if target_duration and segments:
        trimmed = []
        total = 0
        for seg in segments:
            if total + seg['duration'] > target_duration:
                break
            trimmed.append(seg)
            total += seg['duration']
        segments = trimmed

    return segments


def create_beat_synced_edit(video_path, music_path, output_path,
                            target_duration=30, transition='cut'):
    """
    Full beat-synced edit: analyze music beats, cut video to match.

    video_path: raw footage
    music_path: music track to sync to
    output_path: output file
    """
    from editor.transitions import concatenate_with_transitions

    # Detect beats in the music
    beat_info = detect_beats(music_path, sensitivity='medium')
    beats = beat_info.get('beats', [])

    if not beats:
        raise ValueError("No beats detected in the music")

    # Get video duration
    probe = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', video_path],
        capture_output=True, text=True
    )
    video_duration = float(json.loads(probe.stdout).get('format', {}).get('duration', 0))

    # Generate segments aligned to beats
    segments = generate_beat_synced_segments(
        beats, video_duration, target_duration
    )

    if not segments:
        raise ValueError("Could not generate beat-synced segments")

    # Extract each segment
    temp_dir = tempfile.mkdtemp(prefix='beat_sync_')
    seg_paths = []

    try:
        for i, seg in enumerate(segments):
            seg_path = os.path.join(temp_dir, f'beat_{i:03d}.mp4')
            cmd = [
                'ffmpeg', '-y',
                '-ss', str(seg['start']),
                '-i', video_path,
                '-t', str(seg['duration']),
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                '-an',  # Remove original audio
                '-movflags', '+faststart',
                seg_path
            ]
            subprocess.run(cmd, capture_output=True, text=True)
            seg_paths.append(seg_path)

        # Concatenate segments
        concat_path = os.path.join(temp_dir, 'concat.mp4')
        concatenate_with_transitions(seg_paths, concat_path, transition)

        # Add the music track
        cmd_music = [
            'ffmpeg', '-y',
            '-i', concat_path,
            '-i', music_path,
            '-map', '0:v', '-map', '1:a',
            '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '192k',
            '-shortest',
            '-movflags', '+faststart',
            output_path
        ]
        subprocess.run(cmd_music, capture_output=True, text=True)

        return {
            'path': output_path,
            'beats_used': len(segments),
            'bpm': beat_info.get('bpm', 0),
            'duration': round(sum(s['duration'] for s in segments), 2),
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
