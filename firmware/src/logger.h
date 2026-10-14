#pragma once
#include <Arduino.h>
#include <vector>

class AppLog {
public:
    static void init();
    static void log(const String& message);
    static void logf(const char* format, ...);
    static String getLogsAsText();
    static std::vector<String> getRecentLogs();
    static void clear();

private:
    static const size_t MAX_LOG_LINES = 60;
    static std::vector<String> _logBuffer;
};
