#pragma once
#include <Arduino.h>
#include <WebServer.h>
#include <ArduinoOTA.h>
#include <WireGuard-ESP32.h>

class MaintenanceService {
public:
    static void start();
    static void handle();
    static bool isRunning();
    static void stop();

private:
    static WebServer _server;
    static WireGuard _wg;
    static bool _running;
    static unsigned long _lastActivityMs;
    static const unsigned long TIMEOUT_MS = 300000; // 5 minutos

    static void setupRoutes();
    static void handleRoot();
    static void handleLogs();
    static void handleConfig();
    static void handleSaveConfig();
    static void handleActionSync();
    static void handleActionSleep();
    static void handleActionReboot();
    static void handleActionVpsCheck();
    static void handleUpdatePage();
    static void handleUpdateUpload();

    static String buildDashboardHtml();
};
