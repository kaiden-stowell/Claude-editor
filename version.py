"""
Claude Editor — Version Management

Single source of truth for all version information.
Uses date-based versioning: YYYY.M.DD
"""

VERSION = "2026.4.17"

# Human-readable codename for this release
CODENAME = "Director's Cut"

# Build metadata
BUILD_DATE = "2026-04-17"

# Full version string
FULL_VERSION = f"Claude Editor v{VERSION} ({CODENAME})"


def version_info():
    """Return version info as a dict (used by /api/info)."""
    parts = VERSION.split('.')
    return {
        'version': VERSION,
        'major': int(parts[0]) if len(parts) > 0 else 0,
        'minor': int(parts[1]) if len(parts) > 1 else 0,
        'patch': int(parts[2]) if len(parts) > 2 else 0,
        'tag': 'stable',
        'codename': CODENAME,
        'build_date': BUILD_DATE,
        'full': FULL_VERSION,
    }
