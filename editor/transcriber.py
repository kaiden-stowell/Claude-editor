"""
Audio Transcriber — extracts speech from video using Whisper AI.

Provides word-level and segment-level timestamps for caption placement
and content understanding by the AI Director.
"""

import os
import subprocess
import json
import tempfile


def _extract_audio(video_path, output_path):
    """Extract audio from video file using FFmpeg."""
    cmd = [
        'ffmpeg', '-i', video_path,
        '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
        '-y', output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Audio extraction failed: {result.stderr}")
    return output_path


def _transcribe_whisper(audio_path, model_name='base'):
    """Transcribe using OpenAI Whisper (local)."""
    import whisper
    model = whisper.load_model(model_name)
    result = model.transcribe(
        audio_path,
        word_timestamps=True,
        verbose=False
    )
    return result


def _format_segments(whisper_result):
    """Convert Whisper output to our standard format."""
    segments = []
    for seg in whisper_result.get('segments', []):
        segment = {
            'start': round(seg['start'], 3),
            'end': round(seg['end'], 3),
            'text': seg['text'].strip(),
            'words': []
        }

        for word in seg.get('words', []):
            segment['words'].append({
                'word': word['word'].strip(),
                'start': round(word['start'], 3),
                'end': round(word['end'], 3),
            })

        segments.append(segment)

    return segments


def transcribe_video(video_path, model_name='base', progress_callback=None):
    """
    Transcribe speech from a video file.

    Returns:
        dict with 'text' (full transcript), 'segments' (timed segments with words),
        and 'language' (detected language).
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    if progress_callback:
        progress_callback('transcriber', 10, 'Extracting audio...')

    # Extract audio to temp WAV
    temp_dir = tempfile.mkdtemp()
    audio_path = os.path.join(temp_dir, 'audio.wav')
    _extract_audio(video_path, audio_path)

    if progress_callback:
        progress_callback('transcriber', 30, f'Loading Whisper model ({model_name})...')

    try:
        whisper_result = _transcribe_whisper(audio_path, model_name)
    finally:
        # Clean up temp audio
        if os.path.exists(audio_path):
            os.remove(audio_path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)

    if progress_callback:
        progress_callback('transcriber', 90, 'Formatting transcript...')

    segments = _format_segments(whisper_result)
    full_text = whisper_result.get('text', '').strip()
    language = whisper_result.get('language', 'en')

    if progress_callback:
        progress_callback('transcriber', 100, 'Transcription complete!')

    return {
        'text': full_text,
        'language': language,
        'segments': segments,
        'segment_count': len(segments),
        'word_count': sum(len(s.get('words', [])) for s in segments),
        'duration': segments[-1]['end'] if segments else 0,
    }
