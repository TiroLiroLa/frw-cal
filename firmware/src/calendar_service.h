#pragma once

#include <Arduino.h>
#include <vector>
#include <time.h>

struct CalendarEvent {
    String summary;
    time_t startTime;
    time_t endTime;
    int startYear;
    int startMonth;  // 1-12
    int startDay;    // 1-31
    int startHour;   // 0-23
    int startMinute; // 0-59
    int endYear;
    int endMonth;
    int endDay;
    int endHour;
    int endMinute;
    bool allDay;
    bool isBirthday;
    bool isHoliday;
    String calendarName;
    String location;

    bool isOnDate(int y, int m, int d) const;
    bool isToday(int curY, int curM, int curD) const;
    bool isTomorrow(int curY, int curM, int curD) const;
};

class CalendarService {
public:
    CalendarService();

    bool fetchEvents(int currentYear, int currentMonth, int currentDay, int lookaheadDays, std::vector<CalendarEvent>& outEvents);

    String refreshGoogleAccessToken(const String& clientId, const String& clientSecret, const String& refreshToken);

private:
    bool fetchGoogleEvents(const String& accessToken, const String& calendarId, const String& timeMinIso, const String& timeMaxIso, std::vector<CalendarEvent>& outEvents);
    bool getUserCalendars(const String& accessToken, std::vector<String>& outCalendarIds);
    bool fetchIcalEvents(const String& url, std::vector<CalendarEvent>& outEvents);
    void loadMockEvents(int y, int m, int d, std::vector<CalendarEvent>& outEvents);

    void saveCache(const std::vector<CalendarEvent>& events);
    bool loadCache(std::vector<CalendarEvent>& events);

    static bool parseIsoTime(const String& isoStr, time_t& outTime, int& y, int& m, int& d, int& h, int& min, bool& allDay);
    static String urlEncode(const String& str);
    static void deduplicateEvents(std::vector<CalendarEvent>& events);
};
