"""Font management and loading utilities."""

import os
from pathlib import Path
from typing import Dict, Tuple
from PIL import ImageFont

FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"

_FONT_CACHE: Dict[Tuple[str, int], ImageFont.FreeTypeFont] = {}


def get_font(name: str = "regular", size: int = 12) -> ImageFont.FreeTypeFont:
    """Load and cache TTF font with fallback to standard default fonts."""
    cache_key = (name, size)
    if cache_key in _FONT_CACHE:
        return _FONT_CACHE[cache_key]

    font_filenames = {
        "regular": ["LiberationSans-Regular.ttf", "DejaVuSans.ttf", "Arial.ttf"],
        "bold": ["LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf", "Arial-Bold.ttf"],
        "italic": ["LiberationSans-Italic.ttf", "DejaVuSans-Oblique.ttf"],
    }

    candidates = font_filenames.get(name, font_filenames["regular"])

    # 1. Look in bundled assets/fonts
    for fname in candidates:
        bundled_path = FONTS_DIR / fname
        if bundled_path.exists():
            try:
                font = ImageFont.truetype(str(bundled_path), size)
                _FONT_CACHE[cache_key] = font
                return font
            except Exception:
                pass

    # 2. Look in system font directories
    system_dirs = [
        Path("/usr/share/fonts/liberation"),
        Path("/usr/share/fonts/TTF"),
        Path("/usr/share/fonts/truetype"),
        Path("/usr/share/fonts/dejavu"),
    ]
    for sdir in system_dirs:
        for fname in candidates:
            spath = sdir / fname
            if spath.exists():
                try:
                    font = ImageFont.truetype(str(spath), size)
                    _FONT_CACHE[cache_key] = font
                    return font
                except Exception:
                    pass

    # 3. Fallback to PIL default
    font = ImageFont.load_default()
    _FONT_CACHE[cache_key] = font
    return font
