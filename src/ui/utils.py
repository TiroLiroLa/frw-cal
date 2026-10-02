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
    # Strip emojis to prevent empty square glyph boxes on e-ink
    cleaned = _EMOJI_PATTERN.sub("", text)
    # Normalize spaces
    cleaned = " ".join(cleaned.split())
    return cleaned
