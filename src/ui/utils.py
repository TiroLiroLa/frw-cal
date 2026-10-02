"""Text formatting and cleaning utilities for e-paper rendering."""

import re
from typing import List

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


def wrap_text_to_width(text: str, font, max_width_px: int, max_lines: int = 2) -> List[str]:
    """Wraps text into multiple lines based on pixel width up to max_lines.

    If the text exceeds max_lines, the last line is truncated with an ellipsis.
    """
    if not text:
        return []
    cleaned = sanitize_text(text)
    words = cleaned.split()
    if not words:
        return []

    # Quick check if it fits in 1 line
    if font.getbbox(cleaned)[2] - font.getbbox(cleaned)[0] <= max_width_px:
        return [cleaned]

    lines: List[str] = []
    current_words: List[str] = []

    for word in words:
        if len(lines) == max_lines - 1:
            # Building final allowed line
            current_words.append(word)
            continue

        test_line = " ".join(current_words + [word])
        bbox = font.getbbox(test_line)
        if bbox[2] - bbox[0] <= max_width_px:
            current_words.append(word)
        else:
            if current_words:
                lines.append(" ".join(current_words))
                current_words = [word]
            else:
                lines.append(word)
                current_words = []

    if current_words:
        if len(lines) < max_lines:
            lines.append(" ".join(current_words))

    # Format and truncate each line
    formatted: List[str] = []
    for line in lines[:max_lines]:
        formatted.append(truncate_to_width(line, font, max_width_px))

    return formatted
