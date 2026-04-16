"""
Motion Graphics — lower thirds, intros, outros, title cards.

Professional templates for text animations and overlays
like Premiere's Essential Graphics or Final Cut's titles.
"""

import os
import subprocess
import shutil


# ─── Template Definitions ────────────────────────────────────────────────

TEMPLATES = {
    'lower-third-clean': {
        'name': 'Clean Lower Third',
        'category': 'lower-third',
        'description': 'Minimal lower third with name and title',
    },
    'lower-third-bold': {
        'name': 'Bold Lower Third',
        'category': 'lower-third',
        'description': 'Bold colored bar with text',
    },
    'title-centered': {
        'name': 'Centered Title',
        'category': 'title',
        'description': 'Large centered title text',
    },
    'title-cinematic': {
        'name': 'Cinematic Title',
        'category': 'title',
        'description': 'Letterboxed title with thin font',
    },
    'intro-fade': {
        'name': 'Fade In Intro',
        'category': 'intro',
        'description': 'Title fades in from black',
    },
    'outro-subscribe': {
        'name': 'Subscribe Outro',
        'category': 'outro',
        'description': 'Call-to-action end card',
    },
    'chapter-marker': {
        'name': 'Chapter Marker',
        'category': 'overlay',
        'description': 'Chapter/section title that pops up briefly',
    },
}


def apply_lower_third(input_path, output_path, name, title='',
                      start=0, duration=4, style='clean',
                      color='white', accent_color='0x6366f1',
                      position='bottom-left'):
    """
    Add a lower third graphic (name + title bar) to the video.

    name: primary text (e.g. person's name)
    title: secondary text (e.g. "CEO, Acme Corp")
    """
    name = name.replace("'", "\u2019").replace(':', '\\:')
    title = title.replace("'", "\u2019").replace(':', '\\:')
    end = start + duration
    fade_in = min(0.5, duration / 4)
    fade_out = min(0.5, duration / 4)

    # Position calculations
    x_pos = '40'
    y_name = 'h-120'
    y_title = 'h-80'

    if position == 'bottom-right':
        x_pos = 'w-text_w-40'
    elif position == 'top-left':
        y_name = '40'
        y_title = '80'

    filters = []

    # Background bar
    bar_filter = (
        f"drawbox=x=0:y=h-150:w=iw*0.45:h=100"
        f":color={accent_color}@0.85:t=fill"
        f":enable='between(t,{start},{end})'"
    )
    filters.append(bar_filter)

    # Name text
    name_filter = (
        f"drawtext=text='{name}'"
        f":fontsize=36:fontcolor={color}"
        f":x={x_pos}:y={y_name}"
        f":box=0"
        f":enable='between(t,{start + fade_in},{end - fade_out})'"
    )
    filters.append(name_filter)

    # Title text (if provided)
    if title:
        title_filter = (
            f"drawtext=text='{title}'"
            f":fontsize=22:fontcolor={color}@0.8"
            f":x={x_pos}:y={y_title}"
            f":box=0"
            f":enable='between(t,{start + fade_in},{end - fade_out})'"
        )
        filters.append(title_filter)

    vf = ','.join(filters)

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'copy',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Lower third failed: {result.stderr}")


def apply_title_card(input_path, output_path, title, subtitle='',
                     duration=3, position='center',
                     bg_color='black', text_color='white',
                     font_size=72):
    """
    Add a title card (solid background + text) at the beginning of the video.
    """
    title = title.replace("'", "\u2019").replace(':', '\\:')
    subtitle = subtitle.replace("'", "\u2019").replace(':', '\\:')

    temp_dir = os.path.dirname(output_path) or '.'

    # Create title card video
    title_path = os.path.join(temp_dir, '_title_card.mp4')

    filters = [
        f"drawtext=text='{title}'"
        f":fontsize={font_size}:fontcolor={text_color}"
        f":x=(w-text_w)/2:y=(h-text_h)/2-30"
    ]

    if subtitle:
        filters.append(
            f"drawtext=text='{subtitle}'"
            f":fontsize={int(font_size * 0.4)}:fontcolor={text_color}@0.7"
            f":x=(w-text_w)/2:y=(h-text_h)/2+50"
        )

    vf = ','.join(filters)

    # Get input video dimensions
    probe = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', input_path],
        capture_output=True, text=True
    )
    import json
    streams = json.loads(probe.stdout).get('streams', [])
    width, height = 1920, 1080
    for s in streams:
        if s.get('codec_type') == 'video':
            width = int(s.get('width', 1920))
            height = int(s.get('height', 1080))
            break

    # Generate solid color + text
    cmd_title = [
        'ffmpeg', '-y',
        '-f', 'lavfi', '-i', f'color=c={bg_color}:s={width}x{height}:d={duration}:r=30',
        '-f', 'lavfi', '-i', f'anullsrc=channel_layout=stereo:sample_rate=44100',
        '-vf', vf,
        '-t', str(duration),
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'aac', '-b:a', '192k',
        '-shortest',
        title_path
    ]
    subprocess.run(cmd_title, capture_output=True, text=True)

    # Concatenate title + main video
    list_file = output_path + '.titles.txt'
    with open(list_file, 'w') as f:
        f.write(f"file '{title_path}'\n")
        f.write(f"file '{os.path.abspath(input_path)}'\n")

    cmd_concat = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_file,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'aac', '-b:a', '192k',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd_concat, capture_output=True, text=True)

    # Cleanup
    for f in [title_path, list_file]:
        if os.path.exists(f):
            os.remove(f)

    if result.returncode != 0:
        raise RuntimeError(f"Title card failed: {result.stderr}")


def apply_outro_card(input_path, output_path, text='Thanks for watching!',
                     cta='Subscribe for more', duration=4,
                     bg_color='black', text_color='white'):
    """Add an outro/end card to the video."""
    text = text.replace("'", "\u2019").replace(':', '\\:')
    cta = cta.replace("'", "\u2019").replace(':', '\\:')

    temp_dir = os.path.dirname(output_path) or '.'

    probe = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', input_path],
        capture_output=True, text=True
    )
    import json
    streams = json.loads(probe.stdout).get('streams', [])
    width, height = 1920, 1080
    for s in streams:
        if s.get('codec_type') == 'video':
            width = int(s.get('width', 1920))
            height = int(s.get('height', 1080))
            break

    outro_path = os.path.join(temp_dir, '_outro_card.mp4')

    vf = (
        f"drawtext=text='{text}'"
        f":fontsize=56:fontcolor={text_color}"
        f":x=(w-text_w)/2:y=(h-text_h)/2-40,"
        f"drawtext=text='{cta}'"
        f":fontsize=30:fontcolor={text_color}@0.7"
        f":x=(w-text_w)/2:y=(h-text_h)/2+40"
    )

    cmd_outro = [
        'ffmpeg', '-y',
        '-f', 'lavfi', '-i', f'color=c={bg_color}:s={width}x{height}:d={duration}:r=30',
        '-f', 'lavfi', '-i', f'anullsrc=channel_layout=stereo:sample_rate=44100',
        '-vf', vf,
        '-t', str(duration),
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'aac', '-shortest',
        outro_path
    ]
    subprocess.run(cmd_outro, capture_output=True, text=True)

    list_file = output_path + '.outro.txt'
    with open(list_file, 'w') as f:
        f.write(f"file '{os.path.abspath(input_path)}'\n")
        f.write(f"file '{outro_path}'\n")

    cmd_concat = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_file,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'aac', '-b:a', '192k',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd_concat, capture_output=True, text=True)

    for f in [outro_path, list_file]:
        if os.path.exists(f):
            os.remove(f)


def apply_text_overlay(input_path, output_path, text, start, end,
                       x='center', y='center', font_size=48,
                       color='white', bg_opacity=0.0):
    """
    Generic animated text overlay at any position/time.
    Like Premiere's text tool.
    """
    text = text.replace("'", "\u2019").replace(':', '\\:')

    if x == 'center':
        x_expr = '(w-text_w)/2'
    elif x == 'left':
        x_expr = '40'
    elif x == 'right':
        x_expr = 'w-text_w-40'
    else:
        x_expr = str(x)

    if y == 'center':
        y_expr = '(h-text_h)/2'
    elif y == 'top':
        y_expr = '40'
    elif y == 'bottom':
        y_expr = 'h-text_h-40'
    else:
        y_expr = str(y)

    box_str = f':box=1:boxcolor=black@{bg_opacity}:boxborderw=12' if bg_opacity > 0 else ':box=0'

    vf = (
        f"drawtext=text='{text}'"
        f":fontsize={font_size}:fontcolor={color}"
        f":x={x_expr}:y={y_expr}"
        f"{box_str}"
        f":enable='between(t,{start},{end})'"
    )

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'copy',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Text overlay failed: {result.stderr}")


def list_templates():
    """Return all motion graphics templates."""
    return TEMPLATES
