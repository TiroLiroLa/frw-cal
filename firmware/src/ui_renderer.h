#pragma once

#include <Arduino.h>
#include <vector>
#include "canvas.h"
#include "calendar_service.h"
#include "weather_service.h"

class UIRenderer {
public:
    UIRenderer(Canvas& canvas);

    void render(int year, int month, int day, int hour, int minute,
                const std::vector<CalendarEvent>& events,
                const WeatherData* weather = nullptr);

private:
    Canvas& canvas;

    void renderHeader(int year, int month, int day, int weekday);
    void renderMonthGrid(int year, int month, int day, const std::vector<CalendarEvent>& events);
    void renderStatusBar(int hour, int minute);
    void renderEventList(int year, int month, int day, const std::vector<CalendarEvent>& events, int maxEvents);

    static int getDaysInMonth(int year, int month);
    static int getDayOfWeek(int year, int month, int day); // 0 = Sunday, 1 = Monday, ..., 6 = Saturday
};
