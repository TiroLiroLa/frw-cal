#include "logger.h"
#include <cstdarg>

std::vector<String> AppLog::_logBuffer;

void AppLog::init() {
    _logBuffer.reserve(MAX_LOG_LINES);
}

void AppLog::log(const String& message) {
    Serial.println(message);
    if (_logBuffer.size() >= MAX_LOG_LINES) {
        _logBuffer.erase(_logBuffer.begin());
    }
    _logBuffer.push_back(message);
}

void AppLog::logf(const char* format, ...) {
    char buf[256];
    va_list args;
    va_start(args, format);
    vsnprintf(buf, sizeof(buf), format, args);
    va_end(args);
    log(String(buf));
}

String AppLog::getLogsAsText() {
    String out = "";
    for (const auto& line : _logBuffer) {
        out += line;
        out += "\n";
    }
    return out;
}

std::vector<String> AppLog::getRecentLogs() {
    return _logBuffer;
}

void AppLog::clear() {
    _logBuffer.clear();
}
