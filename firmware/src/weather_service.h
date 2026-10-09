#pragma once

#include <Arduino.h>

struct WeatherData {
    float temperature;
    float tempMin;
    float tempMax;
    int weatherCode;
    String description;
    bool valid;
};

class WeatherService {
public:
    WeatherService();
    bool fetchWeather(const String& latitude, const String& longitude, WeatherData& outData);

private:
    static String getWeatherDescription(int code);
    void saveCache(const WeatherData& data);
    bool loadCache(WeatherData& data);
};
