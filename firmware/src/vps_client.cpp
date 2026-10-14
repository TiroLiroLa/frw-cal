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
    wgActive = wg.begin(WIREGUARD_LOCAL_IP, WIREGUARD_SUBNET, WIREGUARD_GATEWAY, WIREGUARD_PRIVATE_KEY, WIREGUARD_ENDPOINT_ADDRESS, WIREGUARD_SERVER_PUBKEY, WIREGUARD_ENDPOINT_PORT);
    if (wgActive) {
        unsigned long wgStart = millis();
        while (!wg.is_connected() && (millis() - wgStart) < 3000) {
            delay(100);
        }
        if (wg.is_connected()) {
            AppLog::logf("[VPS] WireGuard conectado com sucesso! Handshake ativo no IP %s!", WIREGUARD_LOCAL_IP.toString().c_str());
        } else {
            AppLog::log("[VPS] Aviso: Handshake do WireGuard não respondeu em 3s, tentando conexão...");
        }
        endpoint = "http://10.8.0.1:8000/api/checkin";
    } else {
        AppLog::log("[VPS] Falha ao iniciar WireGuard, tentando endpoint padrão...");
        if (!endpoint.endsWith("/")) endpoint += "/";
        endpoint += "api/checkin";
    }
#else
    if (!endpoint.endsWith("/")) endpoint += "/";
    endpoint += "api/checkin";
#endif

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

    int httpCode = -1;
    String payload = "";

    for (int attempt = 1; attempt <= 3; attempt++) {
        AppLog::logf("[VPS] Enviando check-in (tentativa %d/3) para %s...", attempt, endpoint.c_str());

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

        http.setTimeout(8000);
        http.addHeader("Content-Type", "application/json");
        if (apiKey.length() > 0) {
            http.addHeader("X-API-Key", apiKey);
        }

        httpCode = http.POST(requestBody);

        if (httpCode == HTTP_CODE_OK || httpCode == HTTP_CODE_CREATED) {
            payload = http.getString();
            http.end();
            break;
        }

        AppLog::logf("[VPS] Tentativa %d falhou (HTTP %d)", attempt, httpCode);
        http.end();
        if (attempt < 3) delay(800);
    }

    if (httpCode == HTTP_CODE_OK || httpCode == HTTP_CODE_CREATED) {
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
        AppLog::logf("[VPS] Falha final no check-in após 3 tentativas (HTTP %d)", httpCode);
    }

#if WIREGUARD_ENABLED
    if (wgActive) {
        delay(100);
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
    wgActive = wg.begin(WIREGUARD_LOCAL_IP, WIREGUARD_SUBNET, WIREGUARD_GATEWAY, WIREGUARD_PRIVATE_KEY, WIREGUARD_ENDPOINT_ADDRESS, WIREGUARD_SERVER_PUBKEY, WIREGUARD_ENDPOINT_PORT);
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
