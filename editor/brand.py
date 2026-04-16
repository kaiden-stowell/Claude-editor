"""
Brand System — manages on-brand caption styles and visual identity.

Stores brand presets (colors, fonts, styles) so every edit looks consistent
with the user's brand. Can be configured via the web UI or agent API.
"""

import os
import json

BRANDS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'brands')

DEFAULT_BRAND = {
    'name': 'Default',
    'primary_color': '#FFFFFF',
    'secondary_color': '#000000',
    'accent_color': '#FFD700',
    'caption_font': 'Arial',
    'caption_position': 'bottom',
    'caption_size': 'medium',
    'caption_bg': 'semi-transparent',
    'caption_bg_color': '#000000',
    'caption_bg_opacity': 0.6,
    'emphasis_style': 'highlight',  # highlight, bold, scale, color
    'emphasis_color': '#FFD700',
    'logo_path': None,
    'logo_position': 'top-right',
    'logo_scale': 0.12,
    'output_format': 'reel',  # reel (9:16), landscape (16:9), square (1:1)
}

PRESETS = {
    'clean-white': {
        'name': 'Clean White',
        'primary_color': '#FFFFFF',
        'secondary_color': '#1A1A1A',
        'accent_color': '#3B82F6',
        'caption_bg': 'semi-transparent',
        'caption_bg_color': '#000000',
        'emphasis_color': '#3B82F6',
    },
    'bold-dark': {
        'name': 'Bold Dark',
        'primary_color': '#FFFFFF',
        'secondary_color': '#000000',
        'accent_color': '#EF4444',
        'caption_bg': 'solid',
        'caption_bg_color': '#000000',
        'emphasis_color': '#EF4444',
        'emphasis_style': 'scale',
    },
    'neon-pop': {
        'name': 'Neon Pop',
        'primary_color': '#00FF88',
        'secondary_color': '#0A0A0A',
        'accent_color': '#FF00FF',
        'caption_bg': 'semi-transparent',
        'caption_bg_color': '#0A0A0A',
        'emphasis_color': '#FF00FF',
        'emphasis_style': 'color',
    },
    'minimal': {
        'name': 'Minimal',
        'primary_color': '#F5F5F5',
        'secondary_color': '#333333',
        'accent_color': '#666666',
        'caption_bg': 'none',
        'caption_bg_color': '#000000',
        'caption_size': 'small',
        'emphasis_style': 'bold',
    },
    'warm-creator': {
        'name': 'Warm Creator',
        'primary_color': '#FFF8E7',
        'secondary_color': '#2D1B00',
        'accent_color': '#FF8C00',
        'caption_bg': 'semi-transparent',
        'caption_bg_color': '#2D1B00',
        'emphasis_color': '#FF8C00',
    },
}


def _ensure_brands_dir():
    os.makedirs(BRANDS_DIR, exist_ok=True)


def get_brand(name='default'):
    """Load a saved brand config, or return default."""
    _ensure_brands_dir()
    path = os.path.join(BRANDS_DIR, f'{name}.json')
    if os.path.exists(path):
        with open(path) as f:
            brand = json.load(f)
        # Merge with defaults for any missing keys
        merged = {**DEFAULT_BRAND, **brand}
        return merged
    return {**DEFAULT_BRAND}


def save_brand(name, config):
    """Save a brand config."""
    _ensure_brands_dir()
    brand = {**DEFAULT_BRAND, **config, 'name': name}
    path = os.path.join(BRANDS_DIR, f'{name}.json')
    with open(path, 'w') as f:
        json.dump(brand, f, indent=2)
    return brand


def list_brands():
    """List all saved brands plus presets."""
    _ensure_brands_dir()
    brands = {'presets': PRESETS}
    saved = {}
    for f in os.listdir(BRANDS_DIR):
        if f.endswith('.json'):
            name = f[:-5]
            with open(os.path.join(BRANDS_DIR, f)) as fh:
                saved[name] = json.load(fh)
    brands['saved'] = saved
    return brands


def delete_brand(name):
    """Delete a saved brand."""
    path = os.path.join(BRANDS_DIR, f'{name}.json')
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def brand_to_caption_style(brand):
    """Convert brand config to caption style dict for the editor."""
    def _hex_to_ffmpeg(hex_color):
        """Convert #RRGGBB to FFmpeg-compatible color."""
        hex_color = hex_color.lstrip('#')
        return hex_color

    bg_map = {
        'none': 'none',
        'semi-transparent': 'semi-transparent',
        'solid': 'solid',
    }

    return {
        'position': brand.get('caption_position', 'bottom'),
        'font_size': brand.get('caption_size', 'medium'),
        'color': brand.get('primary_color', '#FFFFFF'),
        'background': bg_map.get(brand.get('caption_bg', 'semi-transparent'), 'semi-transparent'),
        'bg_color': brand.get('caption_bg_color', '#000000'),
        'bg_opacity': brand.get('caption_bg_opacity', 0.6),
        'emphasis_style': brand.get('emphasis_style', 'highlight'),
        'emphasis_color': brand.get('emphasis_color', '#FFD700'),
        'font': brand.get('caption_font', 'Arial'),
    }
