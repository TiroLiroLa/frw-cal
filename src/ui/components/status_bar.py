"""Bottom status bar component showing last sync timestamp and status."""

from datetime import datetime
from typing import Tuple
from ..canvas import EPaperCanvas
from ..fonts import get_font


def render_status_bar(
    canvas: EPaperCanvas,
    last_update: datetime,
    rect: Tuple[int, int, int, int],
):
    """Renders small status info at the bottom of the left column with bold font."""
    x0, y0, x1, y1 = rect
    font = get_font("bold", 10)

    # Top thin line
    canvas.draw_line((x0, y0, x1, y0), color="black", width=1)

    time_str = last_update.strftime("%H:%M")
    text = f"Sincronizado: {time_str}"
    canvas.draw_text((x0 + 2, y0 + 4), text, font=font, color="black")
