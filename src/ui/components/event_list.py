"""Right column component: Agenda header, upcoming events, appointments, and birthdays."""

from datetime import date
from typing import List, Optional, Tuple
from ..canvas import EPaperCanvas
from ..fonts import get_font
from ..utils import sanitize_text, truncate_to_width, wrap_text_to_width
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
    """Renders the agenda and upcoming appointments list with large, bold typography."""
    x0, y0, x1, y1 = rect
    width = x1 - x0

    font_title = get_font("bold", 15)
    font_badge = get_font("bold", 12)
    font_item_title = get_font("bold", 15)
    font_item_sub = get_font("bold", 12)

    # 1. Section Header: "AGENDA" + Red Pill Accent
    header_y = y0 + 1
    # Red vertical accent bar
    canvas.draw_rounded_rectangle(
        (x0, header_y + 1, x0 + 4, header_y + 17), radius=2, fill="red"
    )
    canvas.draw_text((x0 + 10, header_y), "AGENDA", font=font_title, color="black")

    # Divider line under agenda header
    divider_y = header_y + 20
    canvas.draw_line((x0, divider_y, x1, divider_y), color="black", width=1)

    # 2. Filter upcoming events (today and future, excluding holidays)
    upcoming: List[CalendarEvent] = [
        ev for ev in events if ev.end.date() >= current_date and not ev.is_holiday
    ]
    upcoming.sort(key=lambda ev: ev.start)
    display_events = upcoming[:max_events]

    # 3. Render event items
    start_y = divider_y + 4
    avail_height = (y1 - 2) - start_y

    if not display_events:
        # Empty state message
        empty_y = start_y + 40
        font_empty = get_font("bold", 13)
        font_empty_sub = get_font("bold", 12)
        canvas.draw_text(
            (x0 + 10, empty_y),
            "Nenhum compromisso agendado",
            font=font_empty,
            color="black",
        )
        canvas.draw_text(
            (x0 + 10, empty_y + 20),
            "Aproveite o seu dia livre!",
            font=font_empty_sub,
            color="red",
        )
        return

    n_events = len(display_events)
    # Dynamic spacing: fits 1 to 5 events evenly
    item_h = min(avail_height // n_events, 85)

    for idx, ev in enumerate(display_events):
        item_y = start_y + idx * item_h

        is_today = ev.is_today(current_date)
        is_tomorrow = ev.is_tomorrow(current_date)

        # Format Badge: Day + Specific Time + Category
        # 1. Day component
        if is_today:
            day_str = "HOJE"
        elif is_tomorrow:
            day_str = "AMANHÃ"
        else:
            wd_short = WEEKDAYS_SHORT_PT[ev.start.weekday()]
            day_str = f"{wd_short} {ev.start.day:02d}/{ev.start.month:02d}"

        # 2. Category component
        cat_str = ""
        if ev.is_birthday:
            cat_str = "ANIVERSÁRIO"
        elif ev.is_holiday:
            cat_str = "FERIADO"
        elif ev.calendar_name and ev.calendar_name.lower() not in ["primary", "principal", "default"] and "@" not in ev.calendar_name:
            cat_str = ev.calendar_name.upper()

        # 3. Time component (if event has a specific time)
        time_str = ""
        if not ev.all_day:
            st = ev.start.strftime("%H:%M")
            et = ev.end.strftime("%H:%M")
            if et != st and et != "23:59" and (ev.end - ev.start).total_seconds() < 86400 and not cat_str:
                time_str = f"{st} - {et}"
            else:
                time_str = st

        # Combine components
        parts = [day_str]
        if time_str:
            parts.append(time_str)
        if cat_str:
            parts.append(cat_str)
        elif ev.all_day and not cat_str:
            parts.append("DIA TODO")

        badge_text = " · ".join(parts)

        # Ensure badge fits comfortably within width (width = x1 - x0)
        max_badge_w = width - 14
        bbox_b = font_badge.getbbox(badge_text)
        if (bbox_b[2] - bbox_b[0]) > max_badge_w:
            # Fallback 1: if time has range " - ", reduce to start time only
            if " - " in time_str:
                time_str = st
                parts = [day_str, time_str]
                if cat_str:
                    parts.append(cat_str)
                badge_text = " · ".join(parts)
                bbox_b = font_badge.getbbox(badge_text)

            # Fallback 2: remove weekday prefix if not today/tomorrow
            if (bbox_b[2] - bbox_b[0]) > max_badge_w and not (is_today or is_tomorrow):
                day_str = f"{ev.start.day:02d}/{ev.start.month:02d}"
                parts[0] = day_str
                badge_text = " · ".join(parts)
                bbox_b = font_badge.getbbox(badge_text)

            # Fallback 3: truncate if still overflowing
            badge_text = truncate_to_width(badge_text, font_badge, max_badge_w)
            bbox_b = font_badge.getbbox(badge_text)

        bw = (bbox_b[2] - bbox_b[0]) + 10
        bh = 16
        current_y = item_y
        badge_rect = (x0, current_y, x0 + bw, current_y + bh)

        # Style: Solid RED pill for all events as requested
        canvas.draw_rounded_rectangle(badge_rect, radius=3, fill="red")
        canvas.draw_text(
            (x0 + 5, current_y + 1), badge_text, font=font_badge, color="white"
        )

        current_y += bh + 2

        # Title: wrapped into up to 2 lines if needed
        max_title_lines = 2 if item_h >= 50 else 1
        title_lines = wrap_text_to_width(
            ev.summary, font_item_title, max_width_px=width - 4, max_lines=max_title_lines
        )
        line_spacing = 14 if item_h <= 55 else 16
        for line in title_lines:
            canvas.draw_text(
                (x0, current_y), line, font=font_item_title, color="black"
            )
            current_y += line_spacing

        # Location if present and fits without colliding with separator
        if ev.location and (current_y + 12 < item_y + item_h - 2):
            loc = truncate_to_width(ev.location, font_item_sub, max_width_px=width - 4)
            canvas.draw_text(
                (x0, current_y), loc, font=font_item_sub, color="black"
            )

        # Separator line between items (except last item)
        if idx < n_events - 1:
            sep_y = item_y + item_h - 2
            canvas.draw_line((x0, sep_y, x1, sep_y), color="black", width=1)
