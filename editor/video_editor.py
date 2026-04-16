"""
Video Editor Engine — executes an AI-generated edit plan on raw footage.

Handles cutting, arranging, color adjustments, caption rendering,
transitions, and aspect ratio conversion (reel/landscape/square).
"""

import os
import subprocess
import json
import tempfile
import shutil


def _get_video_info(path):
    """Get basic video info via ffprobe."""
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_streams', '-show_format', path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)


def _extract_segment(input_path, start, end, output_path):
    """Extract a segment from a video using FFmpeg (fast seek)."""
    duration = end - start
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(start),
        '-i', input_path,
        '-t', str(duration),
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'aac', '-b:a', '192k',
        '-avoid_negative_ts', 'make_zero',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Segment extraction failed: {result.stderr}")


def _crop_to_format(input_path, output_path, output_format, src_width, src_height):
    """Crop/pad video to target aspect ratio (reel=9:16, square=1:1, landscape=16:9)."""
    format_map = {
        'reel': (1080, 1920),      # 9:16 vertical
        'landscape': (1920, 1080), # 16:9
        'square': (1080, 1080),    # 1:1
    }

    if output_format not in format_map:
        shutil.copy2(input_path, output_path)
        return

    target_w, target_h = format_map[output_format]
    target_ratio = target_w / target_h
    src_ratio = src_width / src_height

    if abs(src_ratio - target_ratio) < 0.05:
        # Already close enough, just scale
        vf = f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black"
    elif src_ratio > target_ratio:
        # Source is wider than target — center crop horizontally
        crop_w = int(src_height * target_ratio)
        crop_x = (src_width - crop_w) // 2
        vf = f"crop={crop_w}:{src_height}:{crop_x}:0,scale={target_w}:{target_h}"
    else:
        # Source is taller than target — center crop vertically
        crop_h = int(src_width / target_ratio)
        crop_y = (src_height - crop_h) // 2
        vf = f"crop={src_width}:{crop_h}:0:{crop_y},scale={target_w}:{target_h}"

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
        raise RuntimeError(f"Format conversion failed: {result.stderr}")


def _apply_color_adjustments(input_path, output_path, adjustments):
    """Apply brightness, contrast, and saturation adjustments."""
    brightness = adjustments.get('brightness_factor', 1.0)
    contrast = adjustments.get('contrast_factor', 1.0)
    saturation = adjustments.get('saturation_factor', 1.0)

    if abs(brightness - 1.0) < 0.01 and abs(contrast - 1.0) < 0.01 and abs(saturation - 1.0) < 0.01:
        shutil.copy2(input_path, output_path)
        return

    brightness_offset = brightness - 1.0
    filter_str = f"eq=brightness={brightness_offset:.2f}:contrast={contrast:.2f}:saturation={saturation:.2f}"

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', filter_str,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'copy',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Color adjustment failed: {result.stderr}")


def _hex_to_ffmpeg_color(hex_color):
    """Convert #RRGGBB to FFmpeg color format."""
    if not hex_color or not hex_color.startswith('#'):
        return hex_color or 'white'
    return '0x' + hex_color.lstrip('#')


def _build_caption_filter(captions, caption_style, video_width, video_height):
    """Build FFmpeg drawtext filter string for on-brand captions."""
    if not captions:
        return None

    size_map = {
        'small': int(video_height * 0.03),
        'medium': int(video_height * 0.045),
        'large': int(video_height * 0.06),
    }
    font_size = size_map.get(caption_style.get('font_size', 'medium'), size_map['medium'])

    position = caption_style.get('position', 'bottom')
    if position == 'top':
        y_expr = str(int(video_height * 0.08))
    elif position == 'center':
        y_expr = '(h-text_h)/2'
    else:
        y_expr = str(int(video_height * 0.82))

    # Brand colors
    primary_color = _hex_to_ffmpeg_color(caption_style.get('color', '#FFFFFF'))
    emphasis_color = _hex_to_ffmpeg_color(caption_style.get('emphasis_color', '#FFD700'))

    # Background
    bg = caption_style.get('background', 'semi-transparent')
    bg_color = caption_style.get('bg_color', '#000000')
    bg_opacity = caption_style.get('bg_opacity', 0.6)

    if bg == 'semi-transparent':
        box_color = f"black@{bg_opacity}"
    elif bg == 'solid':
        box_color = 'black@0.9'
    elif bg == 'none':
        box_color = 'black@0.0'
    else:
        box_color = f'black@{bg_opacity}'

    font = caption_style.get('font', 'Arial')
    emphasis_style = caption_style.get('emphasis_style', 'highlight')

    filters = []
    for cap in captions:
        text = cap['text'].replace("'", "\u2019").replace('"', '\\"').replace(':', '\\:')
        start = float(cap['start'])
        end = float(cap['end'])

        emphasis = cap.get('emphasis', False)

        if emphasis:
            if emphasis_style == 'scale':
                fs = int(font_size * 1.4)
            elif emphasis_style == 'bold':
                fs = int(font_size * 1.15)
            else:
                fs = int(font_size * 1.2)
            fc = emphasis_color
        else:
            fs = font_size
            fc = primary_color

        drawtext = (
            f"drawtext=text='{text}'"
            f":font='{font}'"
            f":fontsize={fs}"
            f":fontcolor={fc}"
            f":x=(w-text_w)/2"
            f":y={y_expr}"
            f":box=1:boxcolor={box_color}:boxborderw=14"
            f":enable='between(t,{start:.3f},{end:.3f})'"
        )
        filters.append(drawtext)

    return ','.join(filters)


def _concatenate_segments(segment_paths, output_path, transition_type='cut'):
    """Concatenate video segments with optional transitions."""
    if not segment_paths:
        raise ValueError("No segments to concatenate")

    if len(segment_paths) == 1:
        shutil.copy2(segment_paths[0], output_path)
        return

    if transition_type == 'cut':
        list_file = output_path + '.txt'
        with open(list_file, 'w') as f:
            for p in segment_paths:
                f.write(f"file '{p}'\n")

        cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', list_file,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
            '-c:a', 'aac', '-b:a', '192k',
            '-movflags', '+faststart',
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if os.path.exists(list_file):
            os.remove(list_file)
        if result.returncode != 0:
            raise RuntimeError(f"Concatenation failed: {result.stderr}")

    elif transition_type in ('crossfade', 'fade_black'):
        _concat_with_transitions(segment_paths, output_path, transition_type)


def _concat_with_transitions(segment_paths, output_path, transition_type, fade_duration=0.5):
    """Concatenate with crossfade or fade-through-black transitions."""
    if len(segment_paths) <= 1:
        if segment_paths:
            shutil.copy2(segment_paths[0], output_path)
        return

    inputs = ''
    for p in segment_paths:
        inputs += f'-i "{p}" '

    durations = []
    for p in segment_paths:
        info = _get_video_info(p)
        dur = float(info.get('format', {}).get('duration', 3))
        durations.append(dur)

    n = len(segment_paths)
    transition = 'fadeblack' if transition_type == 'fade_black' else 'fade'

    filter_parts = []
    offset = durations[0] - fade_duration
    filter_parts.append(
        f"[0:v][1:v]xfade=transition={transition}:duration={fade_duration}:offset={offset:.3f}[v01]"
    )

    for i in range(2, n):
        prev_label = f"v{str(i-2).zfill(1)}{str(i-1).zfill(1)}"
        new_label = f"v{str(i-1).zfill(1)}{str(i).zfill(1)}"
        offset += durations[i-1] - fade_duration
        filter_parts.append(
            f"[{prev_label}][{i}:v]xfade=transition={transition}:duration={fade_duration}:offset={offset:.3f}[{new_label}]"
        )

    final_video_label = f"v{str(n-2).zfill(1)}{str(n-1).zfill(1)}" if n > 2 else "v01"

    audio_inputs = ''.join(f'[{i}:a]' for i in range(n))
    audio_filter = f"{audio_inputs}concat=n={n}:v=0:a=1[aout]"

    filter_complex = ';'.join(filter_parts) + ';' + audio_filter

    cmd_str = (
        f"ffmpeg -y {inputs}"
        f'-filter_complex "{filter_complex}" '
        f'-map "[{final_video_label}]" -map "[aout]" '
        f'-c:v libx264 -preset fast -crf 18 '
        f'-c:a aac -b:a 192k '
        f'-movflags +faststart '
        f'"{output_path}"'
    )

    result = subprocess.run(cmd_str, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        _concatenate_segments(segment_paths, output_path, 'cut')


def _apply_captions(input_path, output_path, captions, caption_style, width, height):
    """Burn on-brand captions into video using FFmpeg drawtext."""
    if not captions:
        shutil.copy2(input_path, output_path)
        return

    filter_str = _build_caption_filter(captions, caption_style, width, height)
    if not filter_str:
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
        raise RuntimeError(f"Caption rendering failed: {result.stderr}")


def _remap_caption_times(captions, segments):
    """Remap caption timestamps from source video time to output video time."""
    remapped = []
    output_offset = 0.0

    for seg in segments:
        seg_start = float(seg['start'])
        seg_end = float(seg['end'])
        seg_duration = seg_end - seg_start

        for cap in captions:
            cap_start = float(cap['start'])
            cap_end = float(cap['end'])

            overlap_start = max(cap_start, seg_start)
            overlap_end = min(cap_end, seg_end)

            if overlap_start < overlap_end:
                new_start = output_offset + (overlap_start - seg_start)
                new_end = output_offset + (overlap_end - seg_start)
                remapped.append({
                    **cap,
                    'start': round(new_start, 3),
                    'end': round(new_end, 3),
                })

        output_offset += seg_duration

    return remapped


def execute_edit(raw_footage_path, edit_plan, output_path,
                 output_format='match', progress_callback=None,
                 transcript_words=None):
    """
    Execute an edit plan on raw footage to produce the final video.
    Includes premium effects pipeline: LUTs, audio processing, advanced captions.

    Args:
        raw_footage_path: path to the raw video file
        edit_plan: dict from ai_director.create_edit_plan()
        output_path: where to save the final video
        output_format: 'reel' (9:16), 'landscape' (16:9), 'square' (1:1), or 'match'
        progress_callback: optional callback(stage, percent, message)
        transcript_words: word-level timestamps for word-by-word captions

    Returns:
        dict with output info (path, duration, size)
    """
    # Import premium modules
    from editor.effects import apply_lut, apply_film_grain, apply_vignette, apply_zoom_effect, apply_speed_ramp
    from editor.audio import normalize_audio, reduce_noise, enhance_voice
    from editor.captions import apply_premium_captions

    if not os.path.exists(raw_footage_path):
        raise FileNotFoundError(f"Raw footage not found: {raw_footage_path}")

    source_info = _get_video_info(raw_footage_path)
    video_stream = None
    for s in source_info.get('streams', []):
        if s.get('codec_type') == 'video':
            video_stream = s
            break

    src_width = int(video_stream.get('width', 1920)) if video_stream else 1920
    src_height = int(video_stream.get('height', 1080)) if video_stream else 1080

    segments = edit_plan.get('segments', [])
    captions = edit_plan.get('captions', [])
    color_adj = edit_plan.get('color_adjustments', {})
    transition_type = edit_plan.get('transition_type', 'cut')
    caption_style = edit_plan.get('caption_style', {})
    premium = edit_plan.get('premium', {})

    # Determine final dimensions based on output format
    format_dims = {
        'reel': (1080, 1920),
        'landscape': (1920, 1080),
        'square': (1080, 1080),
    }
    if output_format in format_dims:
        final_width, final_height = format_dims[output_format]
    else:
        final_width, final_height = src_width, src_height

    temp_dir = tempfile.mkdtemp(prefix='claude_edit_')
    step_counter = [0]
    total_steps = 9  # Max possible steps

    def step(msg):
        step_counter[0] += 1
        pct = min(95, int(step_counter[0] / total_steps * 100))
        if progress_callback:
            progress_callback('editor', pct, msg)

    try:
        # ── Step 1: Extract segments ─────────────────────────────────────
        step(f'Cutting {len(segments)} segments...')

        segment_paths = []
        for i, seg in enumerate(segments):
            seg_path = os.path.join(temp_dir, f'segment_{i:03d}.mp4')
            _extract_segment(raw_footage_path, seg['start'], seg['end'], seg_path)

            # Apply per-segment speed if specified
            speed = float(seg.get('speed', 1.0))
            if abs(speed - 1.0) > 0.05:
                speed_path = os.path.join(temp_dir, f'speed_{i:03d}.mp4')
                try:
                    apply_speed_ramp(seg_path, speed_path,
                                     [{'start': 0, 'end': 9999, 'speed': speed}])
                    seg_path = speed_path
                except Exception:
                    pass  # Keep original if speed ramp fails

            segment_paths.append(seg_path)

        # ── Step 2: Concatenate segments ─────────────────────────────────
        step('Joining segments...')
        concat_path = os.path.join(temp_dir, 'concat.mp4')
        _concatenate_segments(segment_paths, concat_path, transition_type)

        # ── Step 3: Crop/convert to target format ────────────────────────
        step(f'Converting to {output_format} format...')
        format_path = os.path.join(temp_dir, 'formatted.mp4')
        if output_format in format_dims:
            _crop_to_format(concat_path, format_path, output_format, src_width, src_height)
        else:
            shutil.copy2(concat_path, format_path)

        # ── Step 4: Apply color adjustments ──────────────────────────────
        step('Applying color adjustments...')
        color_path = os.path.join(temp_dir, 'colored.mp4')
        _apply_color_adjustments(format_path, color_path, color_adj)

        # ── Step 5: Apply LUT color grade ────────────────────────────────
        current = color_path
        lut_name = premium.get('lut', 'none')
        if lut_name and lut_name != 'none':
            step(f'Applying {lut_name} color grade...')
            lut_path = os.path.join(temp_dir, 'lut.mp4')
            try:
                apply_lut(current, lut_path, lut_name)
                current = lut_path
            except Exception:
                pass  # Keep un-graded if LUT fails
        else:
            step('Skipping LUT...')

        # ── Step 6: Apply film grain + vignette ──────────────────────────
        grain = premium.get('film_grain', 'none')
        if grain and grain != 'none':
            step(f'Adding {grain} film grain...')
            grain_path = os.path.join(temp_dir, 'grain.mp4')
            try:
                apply_film_grain(current, grain_path, grain)
                current = grain_path
            except Exception:
                pass

        if premium.get('vignette', False):
            step('Adding vignette...')
            vig_path = os.path.join(temp_dir, 'vignette.mp4')
            try:
                apply_vignette(current, vig_path)
                current = vig_path
            except Exception:
                pass

        # ── Step 7: Audio processing ─────────────────────────────────────
        audio_processed = False
        if premium.get('audio_normalize', False):
            step('Normalizing audio...')
            norm_path = os.path.join(temp_dir, 'normalized.mp4')
            try:
                normalize_audio(current, norm_path)
                current = norm_path
                audio_processed = True
            except Exception:
                pass

        denoise = premium.get('audio_denoise', 'none')
        if denoise and denoise != 'none':
            step(f'Reducing noise ({denoise})...')
            dn_path = os.path.join(temp_dir, 'denoised.mp4')
            try:
                reduce_noise(current, dn_path, denoise)
                current = dn_path
                audio_processed = True
            except Exception:
                pass

        if premium.get('voice_enhance', False):
            step('Enhancing voice...')
            ve_path = os.path.join(temp_dir, 'voice_enhanced.mp4')
            try:
                enhance_voice(current, ve_path)
                current = ve_path
                audio_processed = True
            except Exception:
                pass

        # ── Step 8: Apply captions ───────────────────────────────────────
        step('Rendering on-brand captions...')
        remapped_captions = _remap_caption_times(captions, segments)

        caption_mode = premium.get('caption_mode', 'standard')
        caption_path = os.path.join(temp_dir, 'captioned.mp4')

        if caption_mode in ('word-highlight', 'outline', 'glow') and remapped_captions:
            # Remap word timestamps too
            remapped_words = _remap_caption_times(
                transcript_words or [], segments
            ) if transcript_words else []

            try:
                apply_premium_captions(
                    current, caption_path, remapped_captions, remapped_words,
                    caption_style, final_width, final_height, caption_mode
                )
                current = caption_path
            except Exception:
                # Fallback to standard captions
                _apply_captions(current, caption_path, remapped_captions,
                               caption_style, final_width, final_height)
                current = caption_path
        elif remapped_captions:
            _apply_captions(current, caption_path, remapped_captions,
                           caption_style, final_width, final_height)
            current = caption_path

        # ── Step 9: Final output ─────────────────────────────────────────
        step('Finalizing...')
        if current != output_path:
            shutil.copy2(current, output_path)

        # Get final output info
        output_info = _get_video_info(output_path)
        output_duration = float(output_info.get('format', {}).get('duration', 0))
        output_size = os.path.getsize(output_path)

        if progress_callback:
            progress_callback('editor', 100, 'Edit complete!')

        # Build premium features summary
        premium_applied = []
        if lut_name and lut_name != 'none':
            premium_applied.append(f'LUT: {lut_name}')
        if grain and grain != 'none':
            premium_applied.append(f'Film grain: {grain}')
        if premium.get('vignette'):
            premium_applied.append('Vignette')
        if audio_processed:
            premium_applied.append('Audio enhanced')
        if caption_mode != 'standard':
            premium_applied.append(f'Captions: {caption_mode}')

        return {
            'path': output_path,
            'duration': round(output_duration, 2),
            'size_bytes': output_size,
            'size_mb': round(output_size / (1024 * 1024), 2),
            'resolution': f'{final_width}x{final_height}',
            'format': output_format,
            'segments_used': len(segments),
            'captions_added': len(remapped_captions),
            'title': edit_plan.get('title', 'Untitled'),
            'premium_features': premium_applied,
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
