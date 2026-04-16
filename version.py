"""
Claude Editor — Version Management

Single source of truth for all version information.
Uses Semantic Versioning: MAJOR.MINOR.PATCH

MAJOR — breaking changes to the API or workflow
MINOR — new features (backwards compatible)
PATCH — bug fixes and small improvements
"""

VERSION_MAJOR = 2
VERSION_MINOR = 0
VERSION_PATCH = 0
VERSION_TAG = ""  # e.g. "beta", "rc1", or "" for stable

VERSION = f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"
if VERSION_TAG:
    VERSION = f"{VERSION}-{VERSION_TAG}"

# Human-readable codename for this release
CODENAME = "Director's Cut"

# Build metadata
BUILD_DATE = "2026-04-16"

# Full version string
FULL_VERSION = f"Claude Editor v{VERSION} ({CODENAME})"


def version_info():
    """Return version info as a dict (used by /api/info)."""
    return {
        'version': VERSION,
        'major': VERSION_MAJOR,
        'minor': VERSION_MINOR,
        'patch': VERSION_PATCH,
        'tag': VERSION_TAG or 'stable',
        'codename': CODENAME,
        'build_date': BUILD_DATE,
        'full': FULL_VERSION,
    }
