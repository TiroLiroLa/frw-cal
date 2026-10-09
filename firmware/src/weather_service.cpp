#include "weather_service.h"
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>

static Preferences weatherPrefs;

WeatherService::WeatherService() {}

String WeatherService::getWeatherDescription(int code) {
    switch (code) {
        case 0: return "Ensolarado";
        case 1: return "Predom. Ensolarado";
        case 2: return "Parcialm. Nublado";
        case 3: return "Nublado";
        case 45:
        case 48: return "Nevoeiro";
        case 51:
        case 53: return "Garoa";
        case 55: return "Garoa densa";
        case 61: return "Chuva leve";
        case 63: return "Chuva moderada";
        case 65: return "Chuva forte";
        case 71: return "Neve";
        case 80: return "Pancadas de chuva";
        case 81: return "Pancadas fortes";
        case 95: return "Trovoada";
        default: return "Tempo Estável";
    }
}

bool WeatherService::fetchWeather(const String& latitude, const String& longitude, WeatherData& outData) {
    outData.valid = false;
    if (WiFi.status() != WL_CONNECTED) {
        return loadCache(outData);
    }

    WiFiClientSecure client;
    client.setInsecure();
    HTTPClient http;

    String url = "https://api.open-meteo.com/v1/forecast?latitude=" + latitude +
                 "&longitude=" + longitude +
                 "&current=temperature_2m,weather_code&daily=temperature_2m_max,temperature_2m_min&timezone=auto";

    http.begin(client, url);
    int httpCode = http.GET();

    if (httpCode != HTTP_CODE_OK) {
        http.end();
        return loadCache(outData);
    }

    String payload = http.getString();
    http.end();

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, payload);

    if (err) {
        return loadCache(outData);
    }

    outData.temperature = doc["current"]["temperature_2m"].as<float>();
    outData.weatherCode = doc["current"]["weather_code"].as<int>();
    outData.tempMax = doc["daily"]["temperature_2m_max"][0].as<float>();
    outData.tempMin = doc["daily"]["temperature_2m_min"][0].as<float>();
    outData.description = getWeatherDescription(outData.weatherCode);
    outData.valid = true;

    saveCache(outData);
    return true;
}

void WeatherService::saveCache(const WeatherData& data) {
    weatherPrefs.begin("weather_cache", false);
    weatherPrefs.putFloat("temp", data.temperature);
    weatherPrefs.putFloat("tmin", data.tempMin);
    weatherPrefs.putFloat("tmax", data.tempMax);
    weatherPrefs.putInt("code", data.weatherCode);
    weatherPrefs.putString("desc", data.description);
    weatherPrefs.end();
}

bool WeatherService::loadCache(WeatherData& data) {
    weatherPrefs.begin("weather_cache", true);
    if (!weatherPrefs.isKey("temp")) {
        weatherPrefs.end();
        return false;
    }
    data.temperature = weatherPrefs.getFloat("temp", 0.0f);
    data.tempMin = weatherPrefs.getFloat("tmin", 0.0f);
    data.tempMax = weatherPrefs.getFloat("tmax", 0.0f);
    data.weatherCode = weatherPrefs.getInt("code", 0);
    data.description = weatherPrefs.getString("desc", "Tempo Estável");
    data.valid = true;
    weatherPrefs.end();
    return true;
}
