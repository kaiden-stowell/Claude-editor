"""
Chroma Key / Green Screen — background removal and replacement.

Supports green screen, blue screen, and custom color keying.
"""

import os
import subprocess
import shutil


def apply_chroma_key(foreground_path, background_path, output_path,
                     key_color='green', similarity=0.3, blend=0.05):
    """
    Remove a colored background and replace with another video/image.

    key_color: 'green', 'blue', or hex color like '0x00FF00'
    similarity: how close to key_color to remove (0.0 = exact, 1.0 = everything)
    blend: edge blending (0.0 = hard edge, 1.0 = very soft)
    """
    color_map = {
        'green': '0x00FF00',
        'blue': '0x0000FF',
        'red': '0xFF0000',
        'white': '0xFFFFFF',
    }
    hex_color = color_map.get(key_color, key_color)

    filter_complex = (
        f"[0:v]chromakey={hex_color}:{similarity}:{blend}[fg];"
        f"[1:v][fg]overlay=shortest=1[out]"
    )

    cmd = [
        'ffmpeg', '-y',
        '-i', foreground_path,
        '-i', background_path,
        '-filter_complex', filter_complex,
        '-map', '[out]',
        '-map', '0:a?',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'copy',
        '-movflags', '+faststart',
        '-shortest',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Chroma key failed: {result.stderr}")

    return {'path': output_path, 'key_color': key_color}


def apply_color_key(foreground_path, background_path, output_path,
                    key_color='0x00FF00', similarity=0.15, blend=0.1):
    """
    More precise color keying using FFmpeg colorkey filter.
    Better edge quality than chromakey for certain footage.
    """
    filter_complex = (
        f"[0:v]colorkey={key_color}:{similarity}:{blend}[fg];"
        f"[1:v][fg]overlay=shortest=1[out]"
    )

    cmd = [
        'ffmpeg', '-y',
        '-i', foreground_path,
        '-i', background_path,
        '-filter_complex', filter_complex,
        '-map', '[out]',
        '-map', '0:a?',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'copy',
        '-movflags', '+faststart',
        '-shortest',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Color key failed: {result.stderr}")


def remove_background_solid(input_path, output_path, bg_color='black'):
    """Replace the chroma-keyed background with a solid color."""
    color_map = {
        'black': '0x000000', 'white': '0xFFFFFF',
        'gray': '0x808080', 'blue': '0x1a1a2e',
    }
    hex_bg = color_map.get(bg_color, bg_color)

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', f"chromakey=0x00FF00:0.3:0.05,pad=iw:ih:0:0:{hex_bg}",
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'copy',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Background removal failed: {result.stderr}")


def apply_blur_background(input_path, output_path, blur_strength=20):
    """
    Create a blurred-background effect (like portrait mode).
    Duplicates the video, blurs the copy, and overlays the original centered.
    Great for converting landscape to portrait/reel format.
    """
    filter_complex = (
        f"[0:v]split[original][bg];"
        f"[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,boxblur={blur_strength}[blurred];"
        f"[original]scale=1080:-1:force_original_aspect_ratio=decrease[scaled];"
        f"[blurred][scaled]overlay=(W-w)/2:(H-h)/2[out]"
    )

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-filter_complex', filter_complex,
        '-map', '[out]', '-map', '0:a?',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'copy',
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Blur background failed: {result.stderr}")

    return {'path': output_path}
