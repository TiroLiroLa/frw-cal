#include "vps_client.h"
#include "logger.h"
#include "config.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <HTTPUpdate.h>
#include <ArduinoJson.h>

#if WIREGUARD_ENABLED
#include <WireGuard-ESP32.h>
#endif

VpsCheckinResult VpsClient::checkin(
    const String& host,
    const String& apiKey,
    const String& currentVersion,
    int curYear, int curMonth, int curDay,
    int eventsCount,
    bool googleOk,
    const String& lastLog
) {
    VpsCheckinResult result;
    if (host.length() == 0 || host == "http://" || host == "https://") {
        return result;
    }

    if (WiFi.status() != WL_CONNECTED) {
        AppLog::log("[VPS] Wi-Fi não conectado. Check-in cancelado.");
        return result;
    }

    String endpoint = host;
#if WIREGUARD_ENABLED
    WireGuard wg;
    bool wgActive = false;
    AppLog::log("[VPS] Iniciando túnel WireGuard (Oracle VPN)...");
    wgActive = wg.begin(WIREGUARD_LOCAL_IP, WIREGUARD_PRIVATE_KEY, WIREGUARD_ENDPOINT_ADDRESS, WIREGUARD_SERVER_PUBKEY, WIREGUARD_ENDPOINT_PORT);
    if (wgActive) {
        AppLog::logf("[VPS] WireGuard conectado com IP %s!", WIREGUARD_LOCAL_IP.toString().c_str());
        endpoint = "http://10.8.0.1:8000/api/checkin";
    } else {
        AppLog::log("[VPS] Falha ao conectar WireGuard, tentando endpoint padrão...");
        if (!endpoint.endsWith("/")) endpoint += "/";
        endpoint += "api/checkin";
    }
    delay(200);
#else
    if (!endpoint.endsWith("/")) endpoint += "/";
    endpoint += "api/checkin";
#endif

    AppLog::logf("[VPS] Enviando check-in para %s...", endpoint.c_str());

    HTTPClient http;
    WiFiClient client;
    WiFiClientSecure secureClient;
    bool isHttps = endpoint.startsWith("https://");

    if (isHttps) {
        secureClient.setInsecure();
        http.begin(secureClient, endpoint);
    } else {
        http.begin(client, endpoint);
    }

    http.setTimeout(5000); // 5s timeout max
    http.addHeader("Content-Type", "application/json");
    if (apiKey.length() > 0) {
        http.addHeader("X-API-Key", apiKey);
    }

    JsonDocument doc;
    doc["device_id"] = "frw-cal-nodemcu";
    doc["mac"] = WiFi.macAddress();
    doc["ip"] = WiFi.localIP().toString();
    doc["rssi"] = WiFi.RSSI();
    doc["firmware_version"] = currentVersion;
    doc["free_heap"] = ESP.getFreeHeap();
    
    char dateBuf[16];
    snprintf(dateBuf, sizeof(dateBuf), "%04d-%02d-%02d", curYear, curMonth, curDay);
    doc["date"] = dateBuf;
    doc["events_count"] = eventsCount;
    doc["google_api_ok"] = googleOk;
    doc["last_log"] = lastLog;

    String requestBody;
    serializeJson(doc, requestBody);

    int httpCode = http.POST(requestBody);

    if (httpCode == HTTP_CODE_OK || httpCode == HTTP_CODE_CREATED) {
        String payload = http.getString();
        AppLog::logf("[VPS] Resposta recebida (%d bytes)", payload.length());

        JsonDocument respDoc;
        DeserializationError err = deserializeJson(respDoc, payload);
        if (!err) {
            result.success = true;
            result.hasFirmwareUpdate = respDoc["has_firmware_update"] | false;
            result.firmwareUrl = respDoc["firmware_url"] | "";
            result.firmwareVersion = respDoc["firmware_version"] | "";
            result.action = respDoc["action"] | "";

            if (result.hasFirmwareUpdate && result.firmwareUrl.length() > 0) {
                AppLog::logf("[VPS] Nova versão de firmware disponível: '%s' em %s",
                             result.firmwareVersion.c_str(), result.firmwareUrl.c_str());
            } else {
                AppLog::log("[VPS] Firmware atualizado. Nenhuma ação pendente.");
            }
        } else {
            AppLog::logf("[VPS] Erro ao decodificar JSON da VPS: %s", err.c_str());
        }
    } else {
        AppLog::logf("[VPS] Falha no check-in (HTTP %d)", httpCode);
    }

    http.end();

#if WIREGUARD_ENABLED
    if (wgActive) {
        wg.end();
    }
#endif

    return result;
}

bool VpsClient::downloadAndApplyOta(const String& firmwareUrl) {
    if (firmwareUrl.length() == 0) return false;

    String url = firmwareUrl;
#if WIREGUARD_ENABLED
    WireGuard wg;
    bool wgActive = false;
    AppLog::log("[VPS OTA] Iniciando túnel WireGuard para download do firmware...");
    wgActive = wg.begin(WIREGUARD_LOCAL_IP, WIREGUARD_PRIVATE_KEY, WIREGUARD_ENDPOINT_ADDRESS, WIREGUARD_SERVER_PUBKEY, WIREGUARD_ENDPOINT_PORT);
    if (wgActive) {
        url.replace("163.176.44.220:8000", "10.8.0.1:8000");
    }
    delay(200);
#endif

    AppLog::logf("[VPS OTA] Iniciando download e gravação de %s...", url.c_str());

    httpUpdate.setLedPin(-1);
    httpUpdate.rebootOnUpdate(false); // We control reboot explicitly

    t_httpUpdate_return ret;
    if (url.startsWith("https://")) {
        WiFiClientSecure secureClient;
        secureClient.setInsecure();
        ret = httpUpdate.update(secureClient, url);
    } else {
        WiFiClient client;
        ret = httpUpdate.update(client, url);
    }

#if WIREGUARD_ENABLED
    if (wgActive) {
        wg.end();
    }
#endif

    switch (ret) {
        case HTTP_UPDATE_FAILED:
            AppLog::logf("[VPS OTA] Erro na atualização: (%d): %s",
                         httpUpdate.getLastError(), httpUpdate.getLastErrorString().c_str());
            return false;
        case HTTP_UPDATE_NO_UPDATES:
            AppLog::log("[VPS OTA] Nenhum arquivo para atualizar.");
            return false;
        case HTTP_UPDATE_OK:
            AppLog::log("[VPS OTA] Atualização concluída com sucesso! Reiniciando ESP32 em 2 segundos...");
            delay(2000);
            ESP.restart();
            return true;
    }
    return false;
}
