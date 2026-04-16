"""
AI Director — uses Claude to create intelligent edit decisions.

Takes a style profile (from the example video) and a transcript (from the raw
footage) and produces a structured edit plan that matches the example's style
while highlighting the best content from the raw footage.
"""

import json
import anthropic


SYSTEM_PROMPT = """You are a world-class video editor AI with access to premium editing tools. Your job is to create a professional edit decision list (EDL) that transforms raw footage into a polished, broadcast-quality video.

You will receive:
1. A STYLE PROFILE from an example video the user likes — this tells you HOW to edit (pacing, color, energy)
2. A TRANSCRIPT of the raw footage — this tells you WHAT the person is saying and doing

Your goal: select the best, most engaging moments from the raw footage and arrange them to match the style/pacing of the example video, using premium editing features.

EDITING PRINCIPLES:
- Hook first: Start with the most attention-grabbing moment
- Match the example's pacing: if the example has fast 2-second cuts, use fast cuts. If it's slow and cinematic, use longer takes
- Keep the story coherent: the selected segments should flow logically
- Highlight key moments: emphasize surprising, funny, emotional, or insightful statements
- Cut dead air: remove pauses, "um"s, "uh"s, and filler
- End strong: finish with a memorable moment or call-to-action

PREMIUM TOOLS AVAILABLE:
- Color Grading LUTs: cinematic-warm, cinematic-cool, moody-dark, vintage-film, vibrant, black-white, golden-hour, cyberpunk, pastel, high-contrast
- Speed Ramping: slow-mo (0.5x) or fast-forward (2x) on specific segments
- Zoom Effects: dynamic zoom on key moments for emphasis
- Film Grain: light, medium, or heavy grain for cinematic texture
- Vignette: darkened edges for focus
- Caption Styles: standard, word-highlight (karaoke), outline, glow
- Audio: normalize, denoise, voice-enhance, silence-removal
- Transitions: cut, crossfade, fade_black

You MUST respond with valid JSON only. No markdown, no explanation outside the JSON."""


def _build_user_prompt(style_profile, transcript, user_instructions=None):
    """Build the user prompt with style profile and transcript."""

    # Summarize the style profile
    pacing = style_profile.get('pacing', {})
    colors = style_profile.get('colors', {})
    audio = style_profile.get('audio', {})

    style_summary = f"""## EXAMPLE VIDEO STYLE PROFILE

**Duration:** {style_profile.get('total_duration', 0):.1f} seconds
**Aspect Ratio:** {style_profile.get('aspect_category', 'landscape')} ({style_profile.get('aspect_ratio', 1.78)})
**Resolution:** {style_profile['resolution']['width']}x{style_profile['resolution']['height']}

**Pacing:**
- Style: {pacing.get('style', 'medium')}
- Average clip duration: {pacing.get('avg_clip_duration', 3.0):.1f} seconds
- Shortest clip: {pacing.get('min_clip_duration', 1.0):.1f}s / Longest: {pacing.get('max_clip_duration', 10.0):.1f}s
- Cuts per minute: {pacing.get('cuts_per_minute', 10.0):.1f}
- Total scenes: {style_profile.get('scene_count', 1)}

**Color Profile:**
- Brightness: {colors.get('brightness', 128):.0f}/255 ({'bright' if colors.get('brightness', 128) > 140 else 'dark' if colors.get('brightness', 128) < 100 else 'neutral'})
- Saturation: {colors.get('saturation', 128):.0f}/255 ({'vivid' if colors.get('saturation', 128) > 150 else 'muted' if colors.get('saturation', 128) < 80 else 'natural'})
- Contrast: {colors.get('contrast', 50):.0f} ({'high contrast' if colors.get('contrast', 50) > 60 else 'low contrast' if colors.get('contrast', 50) < 35 else 'moderate contrast'})

**Audio:**
- Has audio: {audio.get('has_audio', True)}
- Mean volume: {audio.get('mean_volume_db', -20):.1f} dB"""

    # Format transcript segments
    transcript_text = "## RAW FOOTAGE TRANSCRIPT\n\n"
    transcript_text += f"**Total duration:** {transcript.get('duration', 0):.1f} seconds\n"
    transcript_text += f"**Full text:** {transcript.get('text', '')}\n\n"
    transcript_text += "**Timed segments:**\n"

    for seg in transcript.get('segments', []):
        transcript_text += f"[{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text']}\n"

    # User instructions
    instructions = ""
    if user_instructions:
        instructions = f"\n## ADDITIONAL INSTRUCTIONS FROM USER\n{user_instructions}\n"

    target_duration = style_profile.get('total_duration', 30)

    return f"""{style_summary}

{transcript_text}
{instructions}
## YOUR TASK

Create an edit plan for the raw footage that matches the example video's style.
Target duration: approximately {target_duration:.0f} seconds (match the example video's length).

Respond with this exact JSON structure:
{{
    "title": "A short, catchy title for this edit",
    "concept": "1-2 sentence description of the edit concept/narrative",
    "target_duration": {target_duration:.1f},
    "segments": [
        {{
            "start": 0.0,
            "end": 3.5,
            "reason": "Why this segment was selected",
            "is_hook": false,
            "speed": 1.0
        }}
    ],
    "captions": [
        {{
            "text": "The caption text to display",
            "start": 0.5,
            "end": 2.0,
            "style": "standard",
            "emphasis": false
        }}
    ],
    "color_adjustments": {{
        "brightness_factor": 1.0,
        "contrast_factor": 1.0,
        "saturation_factor": 1.0
    }},
    "transition_type": "cut",
    "caption_style": {{
        "position": "bottom",
        "font_size": "medium",
        "color": "white",
        "background": "semi-transparent"
    }},
    "premium": {{
        "lut": "none",
        "caption_mode": "word-highlight",
        "film_grain": "none",
        "vignette": false,
        "audio_normalize": true,
        "audio_denoise": "light",
        "voice_enhance": true,
        "speed_ramps": [],
        "zoom_points": []
    }}
}}

IMPORTANT RULES:
- "segments" timestamps must reference the RAW FOOTAGE timeline, not the example
- Select segments that capture the most interesting/relevant content
- Order segments to create a compelling narrative (not necessarily chronological)
- Place the strongest hook moment first if the example video has fast pacing
- Total selected segment time should approximate the target_duration
- "segments.speed": 1.0 = normal, 0.5 = slow-mo, 2.0 = fast forward. Use slow-mo for dramatic/key moments
- Add captions for key spoken moments — not every word, just impactful phrases
- Set "emphasis": true for especially important captions
- Caption "style" can be: "standard", "bold", "highlight", or "whisper"
- "transition_type" can be: "cut", "crossfade", "fade_black"
- For color_adjustments: 1.0 = no change, >1.0 = increase, <1.0 = decrease
- Make adjustments to approximately match the example video's color feel

PREMIUM FEATURES RULES:
- "premium.lut": Choose a LUT that matches the example video's color feel. Options: none, cinematic-warm, cinematic-cool, moody-dark, vintage-film, vibrant, black-white, golden-hour, cyberpunk, pastel, high-contrast
- "premium.caption_mode": word-highlight (karaoke effect), outline (bold outline no background), glow (glowing text), standard (classic box)
- "premium.film_grain": none, light, medium, heavy — use for cinematic/vintage looks
- "premium.vignette": true/false — adds darkened edges for cinematic focus
- "premium.audio_normalize": true to normalize audio levels
- "premium.audio_denoise": none, light, medium, heavy
- "premium.voice_enhance": true to boost voice clarity
- "premium.speed_ramps": optional list of {{start, end, speed}} for speed changes within selected segments
- "premium.zoom_points": optional list of {{start, end, zoom_start, zoom_end, x, y}} for dynamic zoom on key moments"""


def create_edit_plan(style_profile, transcript, api_key, model=None,
                     user_instructions=None, progress_callback=None):
    """
    Use Claude to generate an intelligent edit plan.

    Args:
        style_profile: dict from analyzer.analyze_video()
        transcript: dict from transcriber.transcribe_video()
        api_key: Anthropic API key
        model: Claude model to use
        user_instructions: optional additional instructions from user
        progress_callback: optional callback for progress updates

    Returns:
        dict with the complete edit plan
    """
    if not api_key:
        raise ValueError(
            "Anthropic API key is required. Set the ANTHROPIC_API_KEY environment variable."
        )

    if progress_callback:
        progress_callback('ai_director', 10, 'Preparing edit brief for Claude...')

    client = anthropic.Anthropic(api_key=api_key)
    model = model or 'claude-sonnet-4-20250514'

    user_prompt = _build_user_prompt(style_profile, transcript, user_instructions)

    if progress_callback:
        progress_callback('ai_director', 30, 'Claude is analyzing your footage...')

    message = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}]
    )

    if progress_callback:
        progress_callback('ai_director', 80, 'Parsing edit plan...')

    # Extract JSON from response
    response_text = message.content[0].text.strip()

    # Handle potential markdown wrapping
    if response_text.startswith('```'):
        lines = response_text.split('\n')
        # Remove first and last lines (```json and ```)
        response_text = '\n'.join(lines[1:-1])

    try:
        edit_plan = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude returned invalid JSON: {e}\nResponse: {response_text[:500]}")

    # Validate the edit plan
    _validate_edit_plan(edit_plan, transcript.get('duration', 0))

    if progress_callback:
        progress_callback('ai_director', 100, 'Edit plan ready!')

    return edit_plan


def _validate_edit_plan(plan, source_duration):
    """Validate the edit plan structure and fix common issues."""
    if 'segments' not in plan:
        raise ValueError("Edit plan missing 'segments'")

    if not plan['segments']:
        raise ValueError("Edit plan has no segments")

    # Clamp segment times to source duration
    for seg in plan['segments']:
        seg['start'] = max(0, min(float(seg['start']), source_duration))
        seg['end'] = max(seg['start'] + 0.1, min(float(seg['end']), source_duration))

    # Ensure captions exist
    if 'captions' not in plan:
        plan['captions'] = []

    # Ensure color adjustments exist with defaults
    defaults = {'brightness_factor': 1.0, 'contrast_factor': 1.0, 'saturation_factor': 1.0}
    plan.setdefault('color_adjustments', defaults)
    for k, v in defaults.items():
        plan['color_adjustments'].setdefault(k, v)

    # Ensure other fields
    plan.setdefault('transition_type', 'cut')
    plan.setdefault('title', 'Untitled Edit')
    plan.setdefault('concept', '')
    plan.setdefault('caption_style', {
        'position': 'bottom',
        'font_size': 'medium',
        'color': 'white',
        'background': 'semi-transparent'
    })

    # Ensure premium fields exist with defaults
    premium_defaults = {
        'lut': 'none',
        'caption_mode': 'standard',
        'film_grain': 'none',
        'vignette': False,
        'audio_normalize': True,
        'audio_denoise': 'none',
        'voice_enhance': False,
        'speed_ramps': [],
        'zoom_points': [],
    }
    plan.setdefault('premium', premium_defaults)
    for k, v in premium_defaults.items():
        plan['premium'].setdefault(k, v)
