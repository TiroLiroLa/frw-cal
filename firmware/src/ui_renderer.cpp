#include "ui_renderer.h"
#include <algorithm>

static const char* WEEKDAYS_PT[] = {
    "DOMINGO",
    "SEGUNDA-FEIRA",
    "TERÇA-FEIRA",
    "QUARTA-FEIRA",
    "QUINTA-FEIRA",
    "SEXTA-FEIRA",
    "SÁBADO"
};

static const char* WEEKDAYS_SHORT_PT[] = {
    "DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"
};

static const char* MONTHS_PT[] = {
    "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
    "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"
};

static const char* DAY_NAMES_PT[] = {
    "D", "S", "T", "Q", "Q", "S", "S"
};

UIRenderer::UIRenderer(Canvas& c) : canvas(c) {}

int UIRenderer::getDaysInMonth(int year, int month) {
    if (month == 2) {
        bool leap = (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0);
        return leap ? 29 : 28;
    }
    if (month == 4 || month == 6 || month == 9 || month == 11) {
        return 30;
    }
    return 31;
}

int UIRenderer::getDayOfWeek(int year, int month, int day) {
    struct tm t = {0};
    t.tm_year = year - 1900;
    t.tm_mon = month - 1;
    t.tm_mday = day;
    mktime(&t);
    return t.tm_wday; // 0 = Sunday, 1 = Monday, ..., 6 = Saturday
}

void UIRenderer::renderHeader(int year, int month, int day, int weekday) {
    const int x0 = 8, y0 = 6, x1 = 178, y1 = 86;

    // 1. Day of week badge (Capsule in RED with white bold text)
    const char* weekday_str = WEEKDAYS_PT[weekday % 7];
    int badge_h = 24;
    canvas.fillRoundRect(x0, y0, x1, y0 + badge_h, 5, COLOR_RED);

    int text_w = getTextWidth(weekday_str, Font_LiberationSans_Bold_14);
    int badge_w = x1 - x0;
    int text_x = x0 + (badge_w - text_w) / 2;
    canvas.drawText(text_x, y0 + 5, weekday_str, Font_LiberationSans_Bold_14, COLOR_WHITE);

    // 2. Large Day number
    char day_str[8];
    snprintf(day_str, sizeof(day_str), "%02d", day);
    int day_y = y0 + badge_h + 3;
    canvas.drawText(x0 + 2, day_y, day_str, Font_LiberationSans_Bold_44, COLOR_BLACK);

    // 3. Month and Year beside day number
    const char* month_str = MONTHS_PT[(month - 1) % 12];
    char year_str[8];
    snprintf(year_str, sizeof(year_str), "%04d", year);

    int month_x = x0 + 64;
    canvas.drawText(month_x, day_y + 4, month_str, Font_LiberationSans_Bold_16, COLOR_BLACK);
    canvas.drawText(month_x, day_y + 26, year_str, Font_LiberationSans_Bold_16, COLOR_RED);

    // 4. Divider line underneath header
    int divider_y = y1 - 2;
    canvas.drawLine(x0, divider_y, x1, divider_y, COLOR_BLACK, 1);
}

void UIRenderer::renderMonthGrid(int year, int month, int day, const std::vector<CalendarEvent>& events) {
    const int x0 = 8, y0 = 90, x1 = 178, y1 = 268;
    float grid_w = x1 - x0;
    float col_w = grid_w / 7.0f;

    // 1. Day headers (D S T Q Q S S)
    int header_y = y0 + 1;
    for (int col_idx = 0; col_idx < 7; col_idx++) {
        int col_cx = x0 + (int)(col_idx * col_w + col_w / 2.0f);
        Color color = (col_idx == 0) ? COLOR_RED : COLOR_BLACK;
        int tw = getTextWidth(DAY_NAMES_PT[col_idx], Font_LiberationSans_Bold_14);
        canvas.drawText(col_cx - tw / 2, header_y, DAY_NAMES_PT[col_idx], Font_LiberationSans_Bold_14, color);
    }

    // Thin line under day names
    int line_y = header_y + 17;
    canvas.drawLine(x0, line_y, x1, line_y, COLOR_BLACK, 1);

    // 2. Calendar weeks
    int firstWday = getDayOfWeek(year, month, 1); // 0 (Sun) to 6 (Sat)
    int totalDays = getDaysInMonth(year, month);
    int numWeeks = (firstWday + totalDays + 6) / 7;

    int avail_h = y1 - (line_y + 4);
    float row_h = (float)avail_h / (float)numWeeks;
    int start_row_y = line_y + 4;

    for (int row_idx = 0; row_idx < numWeeks; row_idx++) {
        int row_y = start_row_y + (int)(row_idx * row_h);
        int cell_cy = (int)(row_y + row_h / 2.0f);

        for (int col_idx = 0; col_idx < 7; col_idx++) {
            int day_num = row_idx * 7 + col_idx - firstWday + 1;
            if (day_num < 1 || day_num > totalDays) continue;

            int col_cx = x0 + (int)(col_idx * col_w + col_w / 2.0f);
            bool is_today = (day_num == day);
            bool is_sunday = (col_idx == 0);

            // Check if day has events
            bool has_regular_event = false;
            bool is_birthday = false;
            bool is_holiday = false;

            for (const auto& ev : events) {
                if (ev.isOnDate(year, month, day_num)) {
                    if (ev.isHoliday) {
                        is_holiday = true;
                    } else {
                        has_regular_event = true;
                        if (ev.isBirthday) is_birthday = true;
                    }
                }
            }

            char day_text[8];
            snprintf(day_text, sizeof(day_text), "%d", day_num);
            int tw = getTextWidth(day_text, Font_LiberationSans_Bold_14);
            int th = Font_LiberationSans_Bold_14.size;

            int box_half = 11;
            int bx0 = col_cx - box_half;
            int by0 = cell_cy - box_half;
            int bx1 = col_cx + box_half;
            int by1 = cell_cy + box_half;

            int text_x = col_cx - tw / 2;
            int text_y = cell_cy - th / 2;

            if (is_today) {
                // 1. TODAY: Solid RED rounded box with white text
                canvas.fillRoundRect(bx0, by0, bx1, by1, 4, COLOR_RED);
                canvas.drawText(text_x, text_y, day_text, Font_LiberationSans_Bold_14, COLOR_WHITE);
            } else if (has_regular_event) {
                // 2. REGULAR EVENT DAY: All events outlined in RED with RED number
                canvas.drawRoundRect(bx0, by0, bx1, by1, 4, COLOR_RED, 2);
                canvas.drawText(text_x, text_y, day_text, Font_LiberationSans_Bold_14, COLOR_RED);
            } else {
                // 3. NORMAL DAY or HOLIDAY ONLY: Clean bold number (Red for Sunday, Black otherwise)
                Color text_color = is_sunday ? COLOR_RED : COLOR_BLACK;
                canvas.drawText(text_x, text_y, day_text, Font_LiberationSans_Bold_14, text_color);
            }

            // Black dot at top-right corner of the day block for holidays
            if (is_holiday && !is_today) {
                int dot_x = text_x + tw;
                int dot_y = text_y - 3;
                canvas.fillCircle(dot_x, dot_y, 3, COLOR_BLACK);
            }
        }
    }
}

void UIRenderer::renderStatusBar(int hour, int minute) {
    const int x0 = 8, y0 = 274, x1 = 178;

    // Top thin line
    canvas.drawLine(x0, y0, x1, y0, COLOR_BLACK, 1);

    char time_str[32];
    snprintf(time_str, sizeof(time_str), "Sincronizado: %02d:%02d", hour, minute);
    canvas.drawText(x0 + 2, y0 + 3, time_str, Font_LiberationSans_Bold_12, COLOR_BLACK);
}

void UIRenderer::renderEventList(int year, int month, int day, const std::vector<CalendarEvent>& events, int maxEvents) {
    const int x0 = 192, y0 = 6, x1 = 394, y1 = 294;
    int width = x1 - x0;

    // 1. Section Header: "AGENDA" + Red Pill Accent
    int header_y = y0 + 1;
    canvas.fillRoundRect(x0, header_y, x0 + 4, header_y + 18, 2, COLOR_RED);
    canvas.drawText(x0 + 10, header_y, "AGENDA", Font_LiberationSans_Bold_18, COLOR_BLACK);

    // Divider line under agenda header
    int divider_y = header_y + 20;
    canvas.drawLine(x0, divider_y, x1, divider_y, COLOR_BLACK, 1);

    // 2. Filter upcoming events (today and future, excluding holidays)
    int todayCode = year * 10000 + month * 100 + day;
    std::vector<CalendarEvent> upcoming;
    for (const auto& ev : events) {
        if (ev.isHoliday) continue;
        int endCode = ev.endYear * 10000 + ev.endMonth * 100 + ev.endDay;
        if (endCode >= todayCode) {
            upcoming.push_back(ev);
        }
    }

    std::sort(upcoming.begin(), upcoming.end(), [](const CalendarEvent& a, const CalendarEvent& b) {
        return a.startTime < b.startTime;
    });

    if (maxEvents > 0 && upcoming.size() > (size_t)maxEvents) {
        upcoming.resize(maxEvents);
    }

    // 3. Render event items
    int start_y = divider_y + 4;
    int max_y = y1 - 2;

    if (upcoming.empty()) {
        int empty_y = start_y + 40;
        canvas.drawText(x0 + 10, empty_y, "Nenhum compromisso agendado", Font_LiberationSans_Bold_14, COLOR_BLACK);
        canvas.drawText(x0 + 10, empty_y + 24, "Aproveite o seu dia livre!", Font_LiberationSans_Bold_14, COLOR_RED);
        return;
    }

    struct RenderedItem {
        String badge_text;
        int bw;
        int bh;
        std::vector<String> title_lines;
        String loc_str;
        int item_h;
    };

    std::vector<RenderedItem> items_to_render;
    const int sep_gap = 4;
    int curr_calc_y = start_y;

    for (const auto& ev : upcoming) {
        bool is_today = ev.isToday(year, month, day);
        bool is_tomorrow = ev.isTomorrow(year, month, day);

        // Format Badge: Day + Time + Category
        String day_str = "";
        if (is_today) {
            day_str = "HOJE";
        } else if (is_tomorrow) {
            day_str = "AMANHÃ";
        } else {
            int wday = getDayOfWeek(ev.startYear, ev.startMonth, ev.startDay);
            char dBuf[16];
            snprintf(dBuf, sizeof(dBuf), "%s %02d/%02d", WEEKDAYS_SHORT_PT[wday % 7], ev.startDay, ev.startMonth);
            day_str = dBuf;
        }

        String cat_str = "";
        if (ev.isBirthday) {
            cat_str = "ANIVERSÁRIO";
        } else if (ev.isHoliday) {
            cat_str = "FERIADO";
        }

        String time_str = "";
        if (!ev.allDay) {
            char tBuf[16];
            snprintf(tBuf, sizeof(tBuf), "%02d:%02d", ev.startHour, ev.startMinute);
            time_str = tBuf;
        }

        String badge_text = day_str;
        if (time_str.length() > 0) {
            badge_text += " · ";
            badge_text += time_str;
        }
        if (cat_str.length() > 0) {
            badge_text += " · ";
            badge_text += cat_str;
        } else if (ev.allDay) {
            badge_text += " · DIA TODO";
        }

        int max_badge_w = width - 12;
        badge_text = canvas.truncateToWidth(badge_text.c_str(), Font_LiberationSans_Bold_14, max_badge_w);

        int text_w = getTextWidth(badge_text.c_str(), Font_LiberationSans_Bold_14);
        int bw = text_w + 10;
        int bh = 17;

        std::vector<String> title_lines;
        canvas.wrapText(ev.summary.c_str(), Font_LiberationSans_Bold_14, width - 4, 2, title_lines);
        int title_h = title_lines.size() * 15;

        String loc_str = "";
        if (ev.location.length() > 0) {
            loc_str = canvas.truncateToWidth(ev.location.c_str(), Font_LiberationSans_Bold_12, width - 4);
        }
        int loc_h = (loc_str.length() > 0) ? 13 : 0;

        int bottom_pad = 2;
        int item_h = bh + 2 + title_h + (loc_h > 0 ? (loc_h + 2) : 0) + bottom_pad;

        if (curr_calc_y + item_h > max_y) {
            break;
        }

        items_to_render.push_back({badge_text, bw, bh, title_lines, loc_str, item_h});
        curr_calc_y += item_h + sep_gap;
    }

    // Pass 2: Render items
    int draw_y = start_y;
    int n_render = items_to_render.size();

    for (int idx = 0; idx < n_render; idx++) {
        const auto& item = items_to_render[idx];

        // 1. Badge (Solid RED pill)
        canvas.fillRoundRect(x0, draw_y, x0 + item.bw, draw_y + item.bh, 3, COLOR_RED);
        canvas.drawText(x0 + 5, draw_y + 1, item.badge_text.c_str(), Font_LiberationSans_Bold_14, COLOR_WHITE);

        // 2. Title lines
        int text_y = draw_y + item.bh + 2;
        for (const auto& line : item.title_lines) {
            canvas.drawText(x0, text_y, line.c_str(), Font_LiberationSans_Bold_14, COLOR_BLACK);
            text_y += 15;
        }

        // 3. Location if present
        if (item.loc_str.length() > 0) {
            text_y += 2;
            canvas.drawText(x0, text_y, item.loc_str.c_str(), Font_LiberationSans_Bold_12, COLOR_BLACK);
        }

        // 4. Separator line between items (except after the last item)
        if (idx < n_render - 1) {
            int sep_y = draw_y + item.item_h;
            canvas.drawLine(x0, sep_y, x1, sep_y, COLOR_BLACK, 1);
            draw_y = sep_y + sep_gap;
        }
    }
}

void UIRenderer::render(int year, int month, int day, int hour, int minute,
                        const std::vector<CalendarEvent>& events,
                        const WeatherData* weather) {
    canvas.clear(COLOR_WHITE);

    // Center vertical divider
    canvas.drawLine(184, 8, 184, 292, COLOR_BLACK, 1);

    int weekday = getDayOfWeek(year, month, day);

    // 1. Left column
    Serial.println("[UI] Desenhando cabeçalho...");
    renderHeader(year, month, day, weekday);
    Serial.println("[UI] Desenhando grade mensal...");
    renderMonthGrid(year, month, day, events);
    Serial.println("[UI] Desenhando barra de status...");
    renderStatusBar(hour, minute);

    // 2. Right column
    Serial.println("[UI] Desenhando lista de eventos...");
    renderEventList(year, month, day, events);
    Serial.println("[UI] Renderização finalizada!");
}
