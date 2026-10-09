#include "calendar_service.h"
#include "config.h"

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <algorithm>

static Preferences prefs;

bool CalendarEvent::isOnDate(int y, int m, int d) const {
    int checkVal = y * 10000 + m * 100 + d;
    int startVal = startYear * 10000 + startMonth * 100 + startDay;
    int endVal = endYear * 10000 + endMonth * 100 + endDay;
    return (checkVal >= startVal && checkVal <= endVal);
}

bool CalendarEvent::isToday(int curY, int curM, int curD) const {
    return isOnDate(curY, curM, curD);
}

bool CalendarEvent::isTomorrow(int curY, int curM, int curD) const {
    // Tomorrow: calculate next day
    int nextD = curD + 1;
    int nextM = curM;
    int nextY = curY;
    // Simple month end check
    int maxDays = 31;
    if (curM == 2) maxDays = ((curY % 4 == 0 && curY % 100 != 0) || (curY % 400 == 0)) ? 29 : 28;
    else if (curM == 4 || curM == 6 || curM == 9 || curM == 11) maxDays = 30;

    if (nextD > maxDays) {
        nextD = 1;
        nextM++;
        if (nextM > 12) {
            nextM = 1;
            nextY++;
        }
    }
    return isOnDate(nextY, nextM, nextD);
}

CalendarService::CalendarService() {}

String CalendarService::urlEncode(const String& str) {
    String encoded = "";
    char c;
    char code0;
    char code1;
    for (size_t i = 0; i < str.length(); i++) {
        c = str.charAt(i);
        if (isalnum(c) || c == '-' || c == '_' || c == '.' || c == '~') {
            encoded += c;
        } else {
            code0 = "0123456789ABCDEF"[((c >> 4) & 0xF)];
            code1 = "0123456789ABCDEF"[(c & 0xF)];
            encoded += '%';
            encoded += code0;
            encoded += code1;
        }
    }
    return encoded;
}

bool CalendarService::parseIsoTime(const String& isoStr, time_t& outTime, int& y, int& m, int& d, int& h, int& min, bool& allDay) {
    if (isoStr.length() < 10) return false;

    y = isoStr.substring(0, 4).toInt();
    m = isoStr.substring(5, 7).toInt();
    d = isoStr.substring(8, 10).toInt();

    struct tm tm_val = {0};
    tm_val.tm_year = y - 1900;
    tm_val.tm_mon = m - 1;
    tm_val.tm_mday = d;

    if (isoStr.length() >= 16 && (isoStr.charAt(10) == 'T' || isoStr.charAt(10) == ' ')) {
        allDay = false;
        h = isoStr.substring(11, 13).toInt();
        min = isoStr.substring(14, 16).toInt();
        tm_val.tm_hour = h;
        tm_val.tm_min = min;
    } else {
        allDay = true;
        h = 0;
        min = 0;
        tm_val.tm_hour = 0;
        tm_val.tm_min = 0;
    }
    outTime = mktime(&tm_val);
    return true;
}

String CalendarService::refreshGoogleAccessToken(const String& clientId, const String& clientSecret, const String& refreshToken) {
    Serial.println("[GoogleAPI] Refreshing OAuth2 access token...");

    WiFiClientSecure client;
    client.setInsecure();

    HTTPClient http;
    http.begin(client, "https://oauth2.googleapis.com/token");
    http.addHeader("Content-Type", "application/x-www-form-urlencoded");

    String body = "grant_type=refresh_token&client_id=" + urlEncode(clientId) +
                  "&client_secret=" + urlEncode(clientSecret) +
                  "&refresh_token=" + urlEncode(refreshToken);

    int httpCode = http.POST(body);
    String accessToken = "";

    if (httpCode == HTTP_CODE_OK) {
        String payload = http.getString();
        JsonDocument doc;
        DeserializationError err = deserializeJson(doc, payload);
        if (!err) {
            accessToken = doc["access_token"].as<String>();
            Serial.println("[GoogleAPI] Access token obtained successfully.");
        } else {
            Serial.printf("[GoogleAPI] JSON deserialize error: %s\n", err.c_str());
            Serial.printf("[GoogleAPI] Raw payload: %s\n", payload.substring(0, 200).c_str());
        }
    } else {
        Serial.printf("[GoogleAPI] Token refresh HTTP failed with code %d\n", httpCode);
        if (httpCode > 0) {
            Serial.println(http.getString());
        }
    }
    http.end();
    return accessToken;
}

bool CalendarService::fetchGoogleEvents(const String& accessToken, const String& calendarId,
                                        const String& timeMinIso, const String& timeMaxIso,
                                        std::vector<CalendarEvent>& outEvents) {
    WiFiClientSecure client;
    client.setInsecure();

    HTTPClient http;
    String baseEndpoint = "https://www.googleapis.com/calendar/v3/calendars/" + urlEncode(calendarId) + "/events";

    // First attempt with orderBy=startTime
    String url = baseEndpoint + "?timeMin=" + timeMinIso + "&timeMax=" + timeMaxIso +
                 "&singleEvents=true&orderBy=startTime&maxResults=50";

    http.begin(client, url);
    http.addHeader("Authorization", "Bearer " + accessToken);

    int httpCode = http.GET();
    if (httpCode != HTTP_CODE_OK) {
        http.end();
        // Fallback without orderBy=startTime (e.g., contacts/birthdays)
        url = baseEndpoint + "?timeMin=" + timeMinIso + "&timeMax=" + timeMaxIso +
              "&singleEvents=true&maxResults=50";
        http.begin(client, url);
        http.addHeader("Authorization", "Bearer " + accessToken);
        httpCode = http.GET();
    }

    if (httpCode != HTTP_CODE_OK) {
        Serial.printf("[GoogleAPI] Error fetching calendar '%s': HTTP %d\n", calendarId.c_str(), httpCode);
        http.end();
        return false;
    }

    // Filter to parse only required fields and save RAM
    JsonDocument filter;
    filter["items"][0]["summary"] = true;
    filter["items"][0]["start"]["date"] = true;
    filter["items"][0]["start"]["dateTime"] = true;
    filter["items"][0]["end"]["date"] = true;
    filter["items"][0]["end"]["dateTime"] = true;
    filter["items"][0]["location"] = true;
    filter["items"][0]["eventType"] = true;

    String payload = http.getString();
    http.end();

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, payload, DeserializationOption::Filter(filter));

    if (err) {
        Serial.printf("[GoogleAPI] JSON parse error: %s\n", err.c_str());
        return false;
    }

    JsonArray items = doc["items"].as<JsonArray>();
    Serial.printf("[GoogleAPI] Retrieved %u events from '%s'\n", (unsigned int)items.size(), calendarId.c_str());

    for (JsonObject item : items) {
        CalendarEvent ev;
        const char* sum_cstr = item["summary"];
        ev.summary = sum_cstr ? String(sum_cstr) : "Sem título";

        const char* loc_cstr = item["location"];
        ev.location = loc_cstr ? String(loc_cstr) : "";
        ev.calendarName = calendarId;

        const char* start_dt = item["start"]["dateTime"];
        const char* start_d = item["start"]["date"];
        bool isAllDay = false;
        String startStr = "";
        if (start_dt && strlen(start_dt) > 0) {
            startStr = start_dt;
            isAllDay = false;
        } else if (start_d && strlen(start_d) > 0) {
            startStr = start_d;
            isAllDay = true;
        }

        const char* end_dt = item["end"]["dateTime"];
        const char* end_d = item["end"]["date"];
        String endStr = "";
        if (end_dt && strlen(end_dt) > 0) {
            endStr = end_dt;
        } else if (end_d && strlen(end_d) > 0) {
            endStr = end_d;
        }

        if (startStr.length() == 0) continue;

        parseIsoTime(startStr, ev.startTime, ev.startYear, ev.startMonth, ev.startDay, ev.startHour, ev.startMinute, isAllDay);
        ev.allDay = isAllDay;

        if (endStr.length() > 0) {
            bool dummy;
            parseIsoTime(endStr, ev.endTime, ev.endYear, ev.endMonth, ev.endDay, ev.endHour, ev.endMinute, dummy);
            // In RFC 5545, all-day end date is exclusive (+1 day). Normalize:
            if (isAllDay && ev.endTime > ev.startTime) {
                struct tm t_end = {0};
                t_end.tm_year = ev.endYear - 1900;
                t_end.tm_mon = ev.endMonth - 1;
                t_end.tm_mday = ev.endDay - 1;
                t_end.tm_hour = 23;
                t_end.tm_min = 59;
                ev.endTime = mktime(&t_end);
                ev.endYear = t_end.tm_year + 1900;
                ev.endMonth = t_end.tm_mon + 1;
                ev.endDay = t_end.tm_mday;
                ev.endHour = 23;
                ev.endMinute = 59;
            }
        } else {
            ev.endTime = ev.startTime;
            ev.endYear = ev.startYear;
            ev.endMonth = ev.startMonth;
            ev.endDay = ev.startDay;
            ev.endHour = isAllDay ? 23 : ev.startHour;
            ev.endMinute = isAllDay ? 59 : ev.startMinute;
        }

        // Detect birthday and holiday tags
        String sumLower = ev.summary;
        sumLower.toLowerCase();
        const char* evTypeCstr = item["eventType"];
        String eventType = evTypeCstr ? String(evTypeCstr) : "";

        ev.isBirthday = (eventType == "birthday" ||
                         calendarId.indexOf("contacts") >= 0 ||
                         sumLower.indexOf("anivers") >= 0 ||
                         sumLower.indexOf("birthday") >= 0 ||
                         sumLower.indexOf("bday") >= 0);

        ev.isHoliday = (calendarId.indexOf("holiday") >= 0 ||
                        sumLower.indexOf("feriado") >= 0 ||
                        sumLower.indexOf("holiday") >= 0);

        outEvents.push_back(ev);
    }

    return true;
}

bool CalendarService::getUserCalendars(const String& accessToken, std::vector<String>& outCalendarIds) {
    WiFiClientSecure client;
    client.setInsecure();

    HTTPClient http;
    http.begin(client, "https://www.googleapis.com/calendar/v3/users/me/calendarList");
    http.addHeader("Authorization", "Bearer " + accessToken);

    int httpCode = http.GET();
    if (httpCode != HTTP_CODE_OK) {
        Serial.printf("[GoogleAPI] calendarList failed with HTTP %d\n", httpCode);
        http.end();
        return false;
    }

    String payload = http.getString();
    http.end();

    JsonDocument filter;
    filter["items"][0]["id"] = true;
    filter["items"][0]["summary"] = true;

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, payload, DeserializationOption::Filter(filter));
    if (err) {
        Serial.printf("[GoogleAPI] calendarList JSON parse error: %s\n", err.c_str());
        return false;
    }

    JsonArray items = doc["items"].as<JsonArray>();
    for (JsonObject it : items) {
        const char* cid = it["id"];
        const char* csum = it["summary"];
        if (cid && strlen(cid) > 0) {
            outCalendarIds.push_back(String(cid));
            Serial.printf("[GoogleAPI] Encontrada agenda: '%s' [%s]\n", csum ? csum : "", cid);
        }
    }
    return !outCalendarIds.empty();
}

void CalendarService::deduplicateEvents(std::vector<CalendarEvent>& events) {
    std::vector<CalendarEvent> uniqueEvents;
    for (const auto& ev : events) {
        bool found = false;
        for (auto& u : uniqueEvents) {
            if (u.summary.equalsIgnoreCase(ev.summary) &&
                u.startYear == ev.startYear &&
                u.startMonth == ev.startMonth &&
                u.startDay == ev.startDay) {
                found = true;
                if ((ev.isBirthday || ev.isHoliday) && !(u.isBirthday || u.isHoliday)) {
                    u = ev;
                }
                break;
            }
        }
        if (!found) {
            uniqueEvents.push_back(ev);
        }
    }
    events = uniqueEvents;
}

bool CalendarService::fetchEvents(int currentYear, int currentMonth, int currentDay, int lookaheadDays, std::vector<CalendarEvent>& outEvents) {
    outEvents.clear();

#if CALENDAR_MODE == CALENDAR_MODE_MOCK
    Serial.println("[Calendar] Running in MOCK mode.");
    loadMockEvents(currentYear, currentMonth, currentDay, outEvents);
    return true;
#endif

    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[Calendar] Wi-Fi not connected. Attempting to load offline cache...");
        if (loadCache(outEvents)) return true;
        loadMockEvents(currentYear, currentMonth, currentDay, outEvents);
        return false;
    }

#if CALENDAR_MODE == CALENDAR_MODE_GOOGLE_API
    String token = refreshGoogleAccessToken(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN);
    if (token.length() == 0) {
        Serial.println("[Calendar] Failed to obtain access token. Falling back to cache.");
        if (loadCache(outEvents)) return true;
        loadMockEvents(currentYear, currentMonth, currentDay, outEvents);
        return false;
    }

    // Calculate timeMin (1st day of current month) and timeMax (current date + lookahead)
    char timeMinBuf[32];
    snprintf(timeMinBuf, sizeof(timeMinBuf), "%04d-%02d-01T00:00:00Z", currentYear, currentMonth);

    struct tm t_max = {0};
    t_max.tm_year = currentYear - 1900;
    t_max.tm_mon = currentMonth - 1;
    t_max.tm_mday = currentDay + std::max(lookaheadDays, 31);
    mktime(&t_max);

    char timeMaxBuf[32];
    snprintf(timeMaxBuf, sizeof(timeMaxBuf), "%04d-%02d-%02dT23:59:59Z",
             t_max.tm_year + 1900, t_max.tm_mon + 1, t_max.tm_mday);

    // Auto-discover all calendars from user's account
    std::vector<String> targetCals;
    getUserCalendars(token, targetCals);

    // Fallback to config.h if discovery returned nothing
    if (targetCals.empty()) {
        for (int i = 0; i < MAX_CALENDARS; i++) {
            if (strlen(GOOGLE_CALENDARS[i]) > 0) {
                targetCals.push_back(String(GOOGLE_CALENDARS[i]));
            }
        }
    }

    bool anySuccess = false;
    for (const auto& calId : targetCals) {
        Serial.printf("[Calendar] Querying calendar: %s\n", calId.c_str());
        if (fetchGoogleEvents(token, calId, timeMinBuf, timeMaxBuf, outEvents)) {
            anySuccess = true;
        }
    }

    if (anySuccess && outEvents.size() > 0) {
        deduplicateEvents(outEvents);
        std::sort(outEvents.begin(), outEvents.end(), [](const CalendarEvent& a, const CalendarEvent& b) {
            return a.startTime < b.startTime;
        });
        saveCache(outEvents);
        Serial.printf("[Calendar] Total unique events loaded: %u\n", (unsigned int)outEvents.size());
        return true;
    } else {
        Serial.println("[Calendar] Failed to fetch live events. Loading cache...");
        if (loadCache(outEvents)) return true;
        loadMockEvents(currentYear, currentMonth, currentDay, outEvents);
        return false;
    }
#elif CALENDAR_MODE == CALENDAR_MODE_ICAL
    if (fetchIcalEvents(ICAL_URL, outEvents)) {
        deduplicateEvents(outEvents);
        std::sort(outEvents.begin(), outEvents.end(), [](const CalendarEvent& a, const CalendarEvent& b) {
            return a.startTime < b.startTime;
        });
        saveCache(outEvents);
        return true;
    } else {
        if (loadCache(outEvents)) return true;
        loadMockEvents(currentYear, currentMonth, currentDay, outEvents);
        return false;
    }
#endif
    return false;
}

bool CalendarService::fetchIcalEvents(const String& url, std::vector<CalendarEvent>& outEvents) {
    if (url.length() == 0) return false;
    WiFiClientSecure client;
    client.setInsecure();
    HTTPClient http;
    http.begin(client, url);
    int httpCode = http.GET();
    if (httpCode != HTTP_CODE_OK) {
        http.end();
        return false;
    }

    WiFiClient* stream = http.getStreamPtr();
    CalendarEvent curEv;
    bool inEvent = false;

    while (http.connected() && stream->available()) {
        String line = stream->readStringUntil('\n');
        line.trim();

        if (line == "BEGIN:VEVENT") {
            inEvent = true;
            curEv = CalendarEvent();
        } else if (line == "END:VEVENT") {
            if (inEvent && curEv.summary.length() > 0) {
                outEvents.push_back(curEv);
            }
            inEvent = false;
        } else if (inEvent) {
            if (line.startsWith("SUMMARY:")) {
                curEv.summary = line.substring(8);
            } else if (line.startsWith("LOCATION:")) {
                curEv.location = line.substring(9);
            } else if (line.startsWith("DTSTART")) {
                int col = line.indexOf(':');
                if (col >= 0) {
                    String dtVal = line.substring(col + 1);
                    bool dummy;
                    parseIsoTime(dtVal, curEv.startTime, curEv.startYear, curEv.startMonth, curEv.startDay, curEv.startHour, curEv.startMinute, dummy);
                    curEv.allDay = (dtVal.length() <= 8);
                }
            } else if (line.startsWith("DTEND")) {
                int col = line.indexOf(':');
                if (col >= 0) {
                    String dtVal = line.substring(col + 1);
                    bool dummy;
                    parseIsoTime(dtVal, curEv.endTime, curEv.endYear, curEv.endMonth, curEv.endDay, curEv.endHour, curEv.endMinute, dummy);
                }
            }
        }
    }
    http.end();
    return outEvents.size() > 0;
}

void CalendarService::saveCache(const std::vector<CalendarEvent>& events) {
    prefs.begin("cal_cache", false);
    JsonDocument doc;
    JsonArray arr = doc.to<JsonArray>();

    size_t count = std::min((size_t)events.size(), (size_t)15);
    for (size_t i = 0; i < count; i++) {
        JsonObject obj = arr.add<JsonObject>();
        obj["s"] = events[i].summary;
        obj["st"] = (uint32_t)events[i].startTime;
        obj["et"] = (uint32_t)events[i].endTime;
        obj["sy"] = events[i].startYear;
        obj["sm"] = events[i].startMonth;
        obj["sd"] = events[i].startDay;
        obj["sh"] = events[i].startHour;
        obj["smin"] = events[i].startMinute;
        obj["ey"] = events[i].endYear;
        obj["em"] = events[i].endMonth;
        obj["ed"] = events[i].endDay;
        obj["eh"] = events[i].endHour;
        obj["emin"] = events[i].endMinute;
        obj["ad"] = events[i].allDay;
        obj["b"] = events[i].isBirthday;
        obj["h"] = events[i].isHoliday;
        obj["l"] = events[i].location;
    }

    String jsonStr;
    serializeJson(doc, jsonStr);
    prefs.putString("data", jsonStr);
    prefs.end();
}

bool CalendarService::loadCache(std::vector<CalendarEvent>& events) {
    prefs.begin("cal_cache", true);
    String jsonStr = prefs.getString("data", "");
    prefs.end();

    if (jsonStr.length() == 0) return false;

    JsonDocument doc;
    if (deserializeJson(doc, jsonStr)) return false;

    events.clear();
    JsonArray arr = doc.as<JsonArray>();
    for (JsonObject obj : arr) {
        CalendarEvent ev;
        ev.summary = obj["s"].as<String>();
        ev.startTime = (time_t)obj["st"].as<uint32_t>();
        ev.endTime = (time_t)obj["et"].as<uint32_t>();
        ev.startYear = obj["sy"].as<int>();
        ev.startMonth = obj["sm"].as<int>();
        ev.startDay = obj["sd"].as<int>();
        ev.startHour = obj["sh"].as<int>();
        ev.startMinute = obj["smin"].as<int>();
        ev.endYear = obj["ey"].as<int>();
        ev.endMonth = obj["em"].as<int>();
        ev.endDay = obj["ed"].as<int>();
        ev.endHour = obj["eh"].as<int>();
        ev.endMinute = obj["emin"].as<int>();
        ev.allDay = obj["ad"].as<bool>();
        ev.isBirthday = obj["b"].as<bool>();
        ev.isHoliday = obj["h"].as<bool>();
        ev.location = obj["l"].as<String>();
        events.push_back(ev);
    }
    return events.size() > 0;
}

void CalendarService::loadMockEvents(int y, int m, int d, std::vector<CalendarEvent>& outEvents) {
    outEvents.clear();

    // 1. Today 10:00
    CalendarEvent e1;
    e1.summary = "Alinhamento de Projeto";
    e1.startYear = y; e1.startMonth = m; e1.startDay = d; e1.startHour = 10; e1.startMinute = 0;
    e1.endYear = y; e1.endMonth = m; e1.endDay = d; e1.endHour = 11; e1.endMinute = 0;
    e1.allDay = false; e1.isBirthday = false; e1.isHoliday = false;
    e1.location = "Google Meet";
    outEvents.push_back(e1);

    // 2. Tomorrow 14:30
    struct tm t2 = {0};
    t2.tm_year = y - 1900; t2.tm_mon = m - 1; t2.tm_mday = d + 1;
    mktime(&t2);
    CalendarEvent e2;
    e2.summary = "Consulta Médica";
    e2.startYear = t2.tm_year + 1900; e2.startMonth = t2.tm_mon + 1; e2.startDay = t2.tm_mday; e2.startHour = 14; e2.startMinute = 30;
    e2.endYear = e2.startYear; e2.endMonth = e2.startMonth; e2.endDay = e2.startDay; e2.endHour = 15; e2.endMinute = 30;
    e2.allDay = false; e2.isBirthday = false; e2.isHoliday = false;
    e2.location = "Clínica Saúde";
    outEvents.push_back(e2);

    // 3. Birthday
    struct tm t3 = {0};
    t3.tm_year = y - 1900; t3.tm_mon = m - 1; t3.tm_mday = d + 3;
    mktime(&t3);
    CalendarEvent e3;
    e3.summary = "Aniversário da Ana";
    e3.startYear = t3.tm_year + 1900; e3.startMonth = t3.tm_mon + 1; e3.startDay = t3.tm_mday;
    e3.endYear = e3.startYear; e3.endMonth = e3.startMonth; e3.endDay = e3.startDay;
    e3.allDay = true; e3.isBirthday = true; e3.isHoliday = false;
    outEvents.push_back(e3);

    // 4. Holiday
    struct tm t4 = {0};
    t4.tm_year = y - 1900; t4.tm_mon = m - 1; t4.tm_mday = d + 6;
    mktime(&t4);
    CalendarEvent e4;
    e4.summary = "Feriado Nacional";
    e4.startYear = t4.tm_year + 1900; e4.startMonth = t4.tm_mon + 1; e4.startDay = t4.tm_mday;
    e4.endYear = e4.startYear; e4.endMonth = e4.startMonth; e4.endDay = e4.startDay;
    e4.allDay = true; e4.isBirthday = false; e4.isHoliday = true;
    outEvents.push_back(e4);
}
