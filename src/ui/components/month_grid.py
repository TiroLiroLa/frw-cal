"""Monthly calendar grid component with day numbers, highlighted event boxes, and 'today' badge."""

import calendar
from datetime import date
from typing import Dict, List, Tuple
from ..canvas import EPaperCanvas
from ..fonts import get_font
from ...calendar_provider.base import CalendarEvent

# Sunday first: D S T Q Q S S
DAY_NAMES_PT = ["D", "S", "T", "Q", "Q", "S", "S"]


def render_month_grid(
    canvas: EPaperCanvas,
    current_date: date,
    events: List[CalendarEvent],
    rect: Tuple[int, int, int, int],
):
    """Renders the 7x5 or 7x6 month grid with outlined event boxes and solid today highlight."""
    x0, y0, x1, y1 = rect
    grid_w = x1 - x0
    col_w = grid_w / 7.0

    font_header = get_font("bold", 11)
    font_day_bold = get_font("bold", 12)

    # 1. Day headers (D S T Q Q S S)
    header_y = y0 + 1
    for col_idx, day_name in enumerate(DAY_NAMES_PT):
        col_cx = x0 + int(col_idx * col_w + col_w / 2.0)
        # Sunday is red, others are black
        color = "red" if col_idx == 0 else "black"
        bbox = font_header.getbbox(day_name)
        tw = bbox[2] - bbox[0]
        canvas.draw_text(
            (col_cx - tw // 2, header_y), day_name, font=font_header, color=color
        )

    # Thin line under day names
    line_y = header_y + 15
    canvas.draw_line((x0, line_y, x1, line_y), color="black", width=1)

    # 2. Prepare event map for current month
    # day_num -> {'has_event': bool, 'has_birthday': bool}
    month_events: Dict[int, Dict[str, bool]] = {}
    for ev in events:
        start_d = ev.start.date()
        end_d = ev.end.date()
        # Check all days in event range that fall in current month
        for d in range(1, 32):
            try:
                check_d = date(current_date.year, current_date.month, d)
                if start_d <= check_d <= end_d:
                    if d not in month_events:
                        month_events[d] = {"has_event": True, "has_birthday": False}
                    if ev.is_birthday:
                        month_events[d]["has_birthday"] = True
            except ValueError:
                break

    # 3. Calendar weeks (Sunday = 6 in python's calendar module)
    cal = calendar.Calendar(firstweekday=6)
    weeks = cal.monthdayscalendar(current_date.year, current_date.month)

    # Calculate row height to fit perfectly in allocated space
    num_weeks = len(weeks)
    avail_h = y1 - (line_y + 4)
    row_h = avail_h / float(num_weeks)

    start_row_y = line_y + 4

    for row_idx, week in enumerate(weeks):
        row_y = start_row_y + int(row_idx * row_h)
        cell_cy = int(row_y + row_h / 2.0)

        for col_idx, day_num in enumerate(week):
            if day_num == 0:
                continue

            col_cx = int(x0 + col_idx * col_w + col_w / 2.0)
            is_today = (day_num == current_date.day)
            is_sunday = (col_idx == 0)
            has_event = day_num in month_events
            is_birthday = has_event and month_events[day_num]["has_birthday"]

            day_text = str(day_num)
            bbox = font_day_bold.getbbox(day_text)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]

            # Box dimension: 20x20 px centered in cell
            box_half = 10
            box_rect = (
                col_cx - box_half,
                cell_cy - box_half - 1,
                col_cx + box_half,
                cell_cy + box_half - 1,
            )

            text_pos = (col_cx - tw // 2, cell_cy - th // 2 - 2)

            if is_today:
                # 1. TODAY: Solid RED rounded box with white text
                canvas.draw_rounded_rectangle(box_rect, radius=4, fill="red")
                canvas.draw_text(text_pos, day_text, font=font_day_bold, color="white")
            elif has_event:
                # 2. EVENT DAY: Outlined box around the number
                outline_color = "red" if (is_birthday or is_sunday) else "black"
                text_color = "red" if (is_birthday or is_sunday) else "black"
                canvas.draw_rounded_rectangle(
                    box_rect, radius=4, outline=outline_color, width=2
                )
                canvas.draw_text(text_pos, day_text, font=font_day_bold, color=text_color)
            else:
                # 3. NORMAL DAY: Clean bold number
                text_color = "red" if is_sunday else "black"
                canvas.draw_text(text_pos, day_text, font=font_day_bold, color=text_color)
