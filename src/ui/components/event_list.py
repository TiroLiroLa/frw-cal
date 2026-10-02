"""Right column component: Agenda header, upcoming events, appointments, and birthdays."""

from datetime import date
from typing import List, Optional, Tuple
from ..canvas import EPaperCanvas
from ..fonts import get_font
from ..utils import sanitize_text
from ...calendar_provider.base import CalendarEvent
from ...weather import WeatherInfo

WEEKDAYS_SHORT_PT = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"]


def render_event_list(
    canvas: EPaperCanvas,
    current_date: date,
    events: List[CalendarEvent],
    weather: Optional[WeatherInfo],
    rect: Tuple[int, int, int, int],
    max_events: int = 5,
):
    """Renders the agenda and upcoming appointments list."""
    x0, y0, x1, y1 = rect

    font_title = get_font("bold", 13)
    font_weather = get_font("bold", 10)
    font_badge = get_font("bold", 10)
    font_item_title = get_font("bold", 11)
    font_item_sub = get_font("regular", 10)

    # 1. Section Header: "AGENDA" + Red Pill Accent + Weather
    header_y = y0 + 1
    # Small red vertical pill
    canvas.draw_rounded_rectangle(
        (x0, header_y + 1, x0 + 4, header_y + 15), radius=2, fill="red"
    )
    canvas.draw_text((x0 + 9, header_y), "AGENDA", font=font_title, color="black")

    # Weather info on top-right of agenda header
    if weather:
        w_desc = sanitize_text(weather.description)
        w_text = f"{int(round(weather.temperature))}°C · {w_desc}"
        bbox_w = font_weather.getbbox(w_text)
        w_width = bbox_w[2] - bbox_w[0]
        if w_width < 140:
            canvas.draw_text(
                (x1 - w_width - 2, header_y + 2),
                w_text,
                font=font_weather,
                color="red",
            )

    # Divider line under agenda header
    divider_y = header_y + 19
    canvas.draw_line((x0, divider_y, x1, divider_y), color="black", width=1)

    # 2. Filter upcoming events (today and future)
    upcoming: List[CalendarEvent] = [
        ev for ev in events if ev.end.date() >= current_date
    ]
    upcoming.sort(key=lambda ev: ev.start)
    display_events = upcoming[:max_events]

    # 3. Render event items
    start_y = divider_y + 5
    avail_height = (y1 - 4) - start_y

    if not display_events:
        # Empty state message
        empty_y = start_y + 40
        font_empty = get_font("regular", 11)
        font_empty_bold = get_font("bold", 12)
        canvas.draw_text(
            (x0 + 10, empty_y),
            "Nenhum compromisso agendado",
            font=font_empty_bold,
            color="black",
        )
        canvas.draw_text(
            (x0 + 10, empty_y + 18),
            "Aproveite o seu dia livre!",
            font=font_empty,
            color="red",
        )
        return

    n_events = len(display_events)
    item_h = min(avail_height // n_events, 52)

    for idx, ev in enumerate(display_events):
        item_y = start_y + idx * item_h

        is_today = ev.is_today(current_date)
        is_tomorrow = ev.is_tomorrow(current_date)

        # Format Badge
        if ev.is_birthday:
            badge_text = "ANIVERSÁRIO"
            badge_color = "red"
            badge_bg = True
        elif is_today:
            time_str = ev.start.strftime("%H:%M") if not ev.all_day else "DIA TODO"
            badge_text = f"HOJE · {time_str}"
            badge_color = "red"
            badge_bg = True
        elif is_tomorrow:
            time_str = ev.start.strftime("%H:%M") if not ev.all_day else "DIA TODO"
            badge_text = f"AMANHÃ · {time_str}"
            badge_color = "black"
            badge_bg = False
        else:
            wd_short = WEEKDAYS_SHORT_PT[ev.start.weekday()]
            time_str = ev.start.strftime("%H:%M") if not ev.all_day else "DIA TODO"
            badge_text = f"{wd_short} {ev.start.day:02d}/{ev.start.month:02d} · {time_str}"
            badge_color = "black"
            badge_bg = False

        current_y = item_y
        if badge_bg:
            bbox_b = font_badge.getbbox(badge_text)
            bw = (bbox_b[2] - bbox_b[0]) + 10
            bh = 14
            badge_rect = (x0, current_y, x0 + bw, current_y + bh)
            canvas.draw_rounded_rectangle(badge_rect, radius=3, fill=badge_color)
            canvas.draw_text(
                (x0 + 5, current_y + 1), badge_text, font=font_badge, color="white"
            )
            current_y += bh + 3
        else:
            canvas.draw_text(
                (x0, current_y), badge_text, font=font_badge, color=badge_color
            )
            current_y += 14

        # Title (clean emoji and truncate)
        clean_title = sanitize_text(ev.summary)
        max_chars = 26
        if len(clean_title) > max_chars:
            clean_title = clean_title[: max_chars - 1].rstrip() + "…"

        canvas.draw_text(
            (x0, current_y), clean_title, font=font_item_title, color="black"
        )

        # Location if present and fits
        if ev.location and item_h >= 46:
            loc = sanitize_text(ev.location)
            if len(loc) > 30:
                loc = loc[:28].rstrip() + "…"
            canvas.draw_text(
                (x0, current_y + 13), loc, font=font_item_sub, color="black"
            )

        # Separator line between items (except last item)
        if idx < n_events - 1:
            sep_y = item_y + item_h - 2
            canvas.draw_line((x0, sep_y, x1, sep_y), color="black", width=1)
