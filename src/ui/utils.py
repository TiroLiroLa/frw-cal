"""Text formatting and cleaning utilities for e-paper rendering."""

import re

# Regex to match emojis and complex unicode pictorial symbols
_EMOJI_PATTERN = re.compile(
    "["
    "\U00010000-\U0010ffff"  # Supplementary Multilingual Plane (most emojis)
    "\u2600-\u27bf"          # Miscellaneous symbols and dingbats
    "\u2300-\u23ff"          # Miscellaneous technical
    "\u2b50"                 # Star
    "]+",
    flags=re.UNICODE,
)


def sanitize_text(text: str) -> str:
    """Removes unsupported emoji characters and trims excess whitespace."""
    if not text:
        return ""
    cleaned = _EMOJI_PATTERN.sub("", text)
    cleaned = " ".join(cleaned.split())
    return cleaned


def truncate_to_width(text: str, font, max_width_px: int) -> str:
    """Truncates text with ellipsis based on actual pixel width rather than character count."""
    if not text:
        return ""
    cleaned = sanitize_text(text)
    bbox = font.getbbox(cleaned)
    if bbox[2] - bbox[0] <= max_width_px:
        return cleaned

    cur = cleaned
    while cur and (font.getbbox(cur + "…")[2] - font.getbbox(cur + "…")[0]) > max_width_px:
        cur = cur[:-1]

    return cur.rstrip() + "…"
