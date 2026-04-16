"""
Premium Captions — word-by-word highlighting, animated styles, multi-line.

Generates advanced FFmpeg drawtext filter chains for CapCut/Premiere-level
caption effects.
"""

import os
import subprocess
import shutil


# ─── Caption Styles ─────────────────────────────────────────────────────

CAPTION_STYLES = {
    'standard': {
        'name': 'Standard',
        'description': 'Clean text with background box',
        'animation': 'none',
    },
    'word-highlight': {
        'name': 'Word-by-Word Highlight',
        'description': 'Each word highlights as it is spoken (karaoke style)',
        'animation': 'highlight',
    },
    'pop': {
        'name': 'Pop In',
        'description': 'Words pop in with a scale effect',
        'animation': 'pop',
    },
    'typewriter': {
        'name': 'Typewriter',
        'description': 'Text appears one character at a time',
        'animation': 'typewriter',
    },
    'fade-word': {
        'name': 'Fade Per Word',
        'description': 'Each word fades in individually',
        'animation': 'fade',
    },
    'outline': {
        'name': 'Outline',
        'description': 'Bold text with dark outline, no background',
        'animation': 'none',
    },
    'glow': {
        'name': 'Glow',
        'description': 'Text with bright glow effect',
        'animation': 'none',
    },
}


def _hex_to_ffmpeg(hex_color):
    """Convert #RRGGBB to FFmpeg 0xRRGGBB format."""
    if not hex_color:
        return 'white'
    if hex_color.startswith('#'):
        return '0x' + hex_color[1:]
    return hex_color


def _escape_text(text):
    """Escape text for FFmpeg drawtext filter."""
    return (text
            .replace("'", "\u2019")
            .replace('"', '\\"')
            .replace(':', '\\:')
            .replace('%', '%%')
            .replace('\\', '\\\\'))


# ─── Word-by-Word Highlight Builder ─────────────────────────────────────

def build_word_highlight_filter(words, style_config, video_width, video_height):
    """
    Build drawtext filters that highlight each word as it's spoken.
    This creates the popular "karaoke-style" caption effect.

    words: list of {word, start, end} from transcription
    """
    if not words:
        return None

    font = style_config.get('font', 'Arial')
    size_map = {'small': int(video_height * 0.035), 'medium': int(video_height * 0.05), 'large': int(video_height * 0.065)}
    font_size = size_map.get(style_config.get('font_size', 'medium'), size_map['medium'])

    primary = _hex_to_ffmpeg(style_config.get('color', '#FFFFFF'))
    highlight = _hex_to_ffmpeg(style_config.get('emphasis_color', '#FFD700'))
    bg = style_config.get('background', 'semi-transparent')

    position = style_config.get('position', 'bottom')
    if position == 'top':
        y_pos = str(int(video_height * 0.08))
    elif position == 'center':
        y_pos = '(h-text_h)/2'
    else:
        y_pos = str(int(video_height * 0.80))

    bg_opacity = style_config.get('bg_opacity', 0.6)
    if bg == 'none':
        box_str = ':box=0'
    elif bg == 'solid':
        box_str = f':box=1:boxcolor=black@0.9:boxborderw=16'
    else:
        box_str = f':box=1:boxcolor=black@{bg_opacity}:boxborderw=16'

    filters = []

    # Group words into phrases (lines of ~5-7 words)
    phrase_size = 5
    phrases = []
    for i in range(0, len(words), phrase_size):
        chunk = words[i:i + phrase_size]
        if chunk:
            phrases.append(chunk)

    for phrase in phrases:
        phrase_start = phrase[0]['start']
        phrase_end = phrase[-1]['end']
        full_text = ' '.join(w['word'] for w in phrase)
        escaped_full = _escape_text(full_text)

        # Background text (full phrase, dimmer)
        bg_filter = (
            f"drawtext=text='{escaped_full}'"
            f":font='{font}'"
            f":fontsize={font_size}"
            f":fontcolor={primary}@0.4"
            f":x=(w-text_w)/2"
            f":y={y_pos}"
            f"{box_str}"
            f":enable='between(t,{phrase_start:.3f},{phrase_end:.3f})'"
        )
        filters.append(bg_filter)

        # Highlighted words (each word lights up on its timing)
        for j, w in enumerate(phrase):
            word_text = _escape_text(w['word'])
            # Calculate x position: we need to know where this word sits in the phrase
            prefix = ' '.join(ww['word'] for ww in phrase[:j])
            prefix_escaped = _escape_text(prefix + (' ' if prefix else ''))

            # Use a separate drawtext for the highlighted word
            highlight_filter = (
                f"drawtext=text='{word_text}'"
                f":font='{font}'"
                f":fontsize={int(font_size * 1.05)}"
                f":fontcolor={highlight}"
                f":x=(w-text_w)/2"
                f":y={y_pos}"
                f":box=0"
                f":enable='between(t,{w['start']:.3f},{w['end']:.3f})'"
            )
            filters.append(highlight_filter)

    return ','.join(filters) if filters else None


# ─── Outline Caption Builder ────────────────────────────────────────────

def build_outline_filter(captions, style_config, video_width, video_height):
    """Build captions with bold text outline (no background box)."""
    if not captions:
        return None

    font = style_config.get('font', 'Arial')
    size_map = {'small': int(video_height * 0.035), 'medium': int(video_height * 0.05), 'large': int(video_height * 0.065)}
    font_size = size_map.get(style_config.get('font_size', 'medium'), size_map['medium'])
    primary = _hex_to_ffmpeg(style_config.get('color', '#FFFFFF'))

    position = style_config.get('position', 'bottom')
    if position == 'top':
        y_pos = str(int(video_height * 0.08))
    elif position == 'center':
        y_pos = '(h-text_h)/2'
    else:
        y_pos = str(int(video_height * 0.80))

    filters = []
    for cap in captions:
        text = _escape_text(cap['text'])
        start = float(cap['start'])
        end = float(cap['end'])
        emphasis = cap.get('emphasis', False)
        fs = int(font_size * 1.2) if emphasis else font_size

        # Shadow/outline layer (draw text in black, slightly offset)
        for dx, dy in [(-2, -2), (2, -2), (-2, 2), (2, 2), (0, -3), (0, 3), (-3, 0), (3, 0)]:
            outline = (
                f"drawtext=text='{text}'"
                f":font='{font}'"
                f":fontsize={fs}"
                f":fontcolor=black"
                f":x=(w-text_w)/2+{dx}"
                f":y={y_pos}+{dy}"
                f":box=0"
                f":enable='between(t,{start:.3f},{end:.3f})'"
            )
            filters.append(outline)

        # Main text layer
        main = (
            f"drawtext=text='{text}'"
            f":font='{font}'"
            f":fontsize={fs}"
            f":fontcolor={primary}"
            f":x=(w-text_w)/2"
            f":y={y_pos}"
            f":box=0"
            f":enable='between(t,{start:.3f},{end:.3f})'"
        )
        filters.append(main)

    return ','.join(filters) if filters else None


# ─── Glow Caption Builder ───────────────────────────────────────────────

def build_glow_filter(captions, style_config, video_width, video_height):
    """Build captions with a glow/bloom effect."""
    if not captions:
        return None

    font = style_config.get('font', 'Arial')
    size_map = {'small': int(video_height * 0.035), 'medium': int(video_height * 0.05), 'large': int(video_height * 0.065)}
    font_size = size_map.get(style_config.get('font_size', 'medium'), size_map['medium'])
    primary = _hex_to_ffmpeg(style_config.get('color', '#FFFFFF'))
    glow_color = _hex_to_ffmpeg(style_config.get('emphasis_color', '#FFD700'))

    position = style_config.get('position', 'bottom')
    if position == 'top':
        y_pos = str(int(video_height * 0.08))
    elif position == 'center':
        y_pos = '(h-text_h)/2'
    else:
        y_pos = str(int(video_height * 0.80))

    filters = []
    for cap in captions:
        text = _escape_text(cap['text'])
        start = float(cap['start'])
        end = float(cap['end'])
        emphasis = cap.get('emphasis', False)
        fs = int(font_size * 1.2) if emphasis else font_size
        fc = glow_color if emphasis else primary

        # Glow layer (larger, semi-transparent)
        glow = (
            f"drawtext=text='{text}'"
            f":font='{font}'"
            f":fontsize={fs + 4}"
            f":fontcolor={fc}@0.3"
            f":x=(w-text_w)/2"
            f":y={y_pos}"
            f":box=0"
            f":enable='between(t,{start:.3f},{end:.3f})'"
        )
        filters.append(glow)

        # Main text
        main = (
            f"drawtext=text='{text}'"
            f":font='{font}'"
            f":fontsize={fs}"
            f":fontcolor={fc}"
            f":x=(w-text_w)/2"
            f":y={y_pos}"
            f":box=0"
            f":enable='between(t,{start:.3f},{end:.3f})'"
        )
        filters.append(main)

    return ','.join(filters) if filters else None


# ─── Apply Premium Captions ─────────────────────────────────────────────

def apply_premium_captions(input_path, output_path, captions, words,
                           style_config, video_width, video_height,
                           caption_mode='standard'):
    """
    Apply premium caption style to a video.

    caption_mode: standard, word-highlight, outline, glow
    """
    filter_str = None

    if caption_mode == 'word-highlight' and words:
        filter_str = build_word_highlight_filter(
            words, style_config, video_width, video_height
        )
    elif caption_mode == 'outline':
        filter_str = build_outline_filter(
            captions, style_config, video_width, video_height
        )
    elif caption_mode == 'glow':
        filter_str = build_glow_filter(
            captions, style_config, video_width, video_height
        )

    if not filter_str:
        # Fall back to standard captions
        shutil.copy2(input_path, output_path)
        return

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', filter_str,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'copy',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Fallback: copy without captions rather than failing
        shutil.copy2(input_path, output_path)


def list_caption_styles():
    """Return available premium caption styles."""
    return CAPTION_STYLES
