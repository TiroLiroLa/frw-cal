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
    font_badge = get_font("bold", 13)
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

    # 3. Render event items
    start_y = divider_y + 4
    max_y = y1 - 2

    if not upcoming:
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

    # Pass 1: Measure each event's natural required height and find all that fit on screen
    sep_gap = 4
    curr_calc_y = start_y
    items_to_render = []

    for ev in upcoming:
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
        bh = 17

        # Title: wrapped into up to 2 lines
        title_lines = wrap_text_to_width(
            ev.summary, font_item_title, max_width_px=width - 4, max_lines=2
        )
        line_spacing = 15
        title_h = len(title_lines) * line_spacing

        # Location if present
        loc_str = truncate_to_width(ev.location, font_item_sub, max_width_px=width - 4) if ev.location else ""
        loc_h = 13 if loc_str else 0

        bottom_pad = 2
        item_h = bh + 2 + title_h + (loc_h + 2 if loc_h else 0) + bottom_pad

        if curr_calc_y + item_h > max_y:
            break

        items_to_render.append({
            "badge_text": badge_text,
            "bw": bw,
            "bh": bh,
            "title_lines": title_lines,
            "line_spacing": line_spacing,
            "loc_str": loc_str,
            "item_h": item_h,
        })
        curr_calc_y += item_h + sep_gap

    # Pass 2: Render all events that fit cleanly
    draw_y = start_y
    n_render = len(items_to_render)

    for idx, item in enumerate(items_to_render):
        # 1. Badge (Solid RED pill)
        badge_rect = (x0, draw_y, x0 + item["bw"], draw_y + item["bh"])
        canvas.draw_rounded_rectangle(badge_rect, radius=3, fill="red")
        canvas.draw_text(
            (x0 + 5, draw_y + 1), item["badge_text"], font=font_badge, color="white"
        )

        # 2. Title lines
        text_y = draw_y + item["bh"] + 2
        for line in item["title_lines"]:
            canvas.draw_text((x0, text_y), line, font=font_item_title, color="black")
            text_y += item["line_spacing"]

        # 3. Location if present
        if item["loc_str"]:
            text_y += 2
            canvas.draw_text((x0, text_y), item["loc_str"], font=font_item_sub, color="black")

        # 4. Separator line between items (except after the last item)
        if idx < n_render - 1:
            sep_y = draw_y + item["item_h"]
            canvas.draw_line((x0, sep_y, x1, sep_y), color="black", width=1)
            draw_y = sep_y + sep_gap
