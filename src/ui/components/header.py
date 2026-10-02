"""Left column header component: Day of week badge, large date, month and year."""

from datetime import date
from typing import Tuple
from ..canvas import EPaperCanvas
from ..fonts import get_font

WEEKDAYS_PT = [
    "SEGUNDA-FEIRA",
    "TERÇA-FEIRA",
    "QUARTA-FEIRA",
    "QUINTA-FEIRA",
    "SEXTA-FEIRA",
    "SÁBADO",
    "DOMINGO",
]

MONTHS_PT = [
    "JANEIRO",
    "FEVEREIRO",
    "MARÇO",
    "ABRIL",
    "MAIO",
    "JUNHO",
    "JULHO",
    "AGOSTO",
    "SETEMBRO",
    "OUTUBRO",
    "NOVEMBRO",
    "DEZEMBRO",
]


def render_header(canvas: EPaperCanvas, current_date: date, rect: Tuple[int, int, int, int]):
    """Renders the date block on the top-left section with large, bold typography."""
    x0, y0, x1, y1 = rect

    # 1. Day of week badge (Capsule in RED with white bold text)
    weekday_str = WEEKDAYS_PT[current_date.weekday()]
    badge_h = 22
    badge_rect = (x0, y0, x1, y0 + badge_h)
    canvas.draw_rounded_rectangle(badge_rect, radius=5, fill="red")

    font_badge = get_font("bold", 12)
    bbox = font_badge.getbbox(weekday_str)
    text_w = bbox[2] - bbox[0]
    badge_w = x1 - x0
    text_x = x0 + (badge_w - text_w) // 2
    canvas.draw_text((text_x, y0 + 3), weekday_str, font=font_badge, color="white")

    # 2. Large Day number
    day_str = f"{current_date.day:02d}"
    font_day = get_font("bold", 44)
    day_y = y0 + badge_h + 3
    canvas.draw_text((x0 + 2, day_y), day_str, font=font_day, color="black")

    # 3. Month and Year beside day number
    month_str = MONTHS_PT[current_date.month - 1]
    year_str = str(current_date.year)

    font_month = get_font("bold", 14)
    font_year = get_font("bold", 14)

    month_x = x0 + 64
    canvas.draw_text((month_x, day_y + 4), month_str, font=font_month, color="black")
    canvas.draw_text((month_x, day_y + 24), year_str, font=font_year, color="red")

    # 4. Divider line underneath header
    divider_y = y1 - 2
    canvas.draw_line((x0, divider_y, x1, divider_y), color="black", width=1)
