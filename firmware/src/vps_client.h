#pragma once
#include <Arduino.h>

struct VpsCheckinResult {
    bool success = false;
    bool hasFirmwareUpdate = false;
    String firmwareUrl = "";
    String firmwareVersion = "";
    bool hasConfigUpdate = false;
    String action = ""; // e.g., "reboot", "refresh"
};

class VpsClient {
public:
    static VpsCheckinResult checkin(
        const String& host,
        const String& apiKey,
        const String& currentVersion,
        int curYear, int curMonth, int curDay,
        int eventsCount,
        bool googleOk,
        const String& lastLog
    );

    static bool downloadAndApplyOta(const String& firmwareUrl);
};
