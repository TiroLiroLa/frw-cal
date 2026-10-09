#pragma once

// ==============================================================================
// Configuração do Smart Calendar ESP32 (NodeMCU-32S)
// Display: WeAct Studio 4.2" E-Paper (Preto, Branco, Vermelho - SSD1683)
// ==============================================================================

// 1. Rede Wi-Fi
#define WIFI_SSID       "SUA_REDE_WIFI"
#define WIFI_PASSWORD   "SUA_SENHA_WIFI"
#define WIFI_TIMEOUT_MS 20000

// 2. Fuso Horário e NTP
#define NTP_SERVER      "pool.ntp.org"
// Horário de Brasília (UTC-3 sem horário de verão)
#define TIMEZONE_POSIX  "<-03>3"

// 3. Pinos do Display WeAct Studio 4.2" BWR (SSD1683) no NodeMCU-32S
// Pinout SPI (VSPI padrão):
#define EPD_PIN_MOSI    23  // DIN / SDI
#define EPD_PIN_SCK     18  // CLK / SCK
#define EPD_PIN_CS       5  // CS
#define EPD_PIN_DC      17  // DC
#define EPD_PIN_RST     16  // RST / RES
#define EPD_PIN_BUSY     4  // BUSY

// 4. Modos de Calendário
#define CALENDAR_MODE_GOOGLE_API 1
#define CALENDAR_MODE_ICAL       2
#define CALENDAR_MODE_MOCK       3
#define CALENDAR_MODE CALENDAR_MODE_GOOGLE_API

// 5. Credenciais do Google Calendar API (OAuth 2.0)
// Use 'python3 tools/sync_esp32_config.py' para sincronizar automaticamente com token.json
#define GOOGLE_CLIENT_ID     "SEU_CLIENT_ID.apps.googleusercontent.com"
#define GOOGLE_CLIENT_SECRET "SEU_CLIENT_SECRET"
#define GOOGLE_REFRESH_TOKEN "SEU_REFRESH_TOKEN"

// Calendários consultados na conta Google
#define MAX_CALENDARS 4
static const char* GOOGLE_CALENDARS[MAX_CALENDARS] = {
    "primary",
    "addressbook#contacts@group.v.calendar.google.com",
    "pt-br.brazilian#holiday@group.v.calendar.google.com",
    ""
};

// 6. Modo iCal (se CALENDAR_MODE == CALENDAR_MODE_ICAL)
#define ICAL_URL ""

// 7. Configurações de exibição
#define MAX_UPCOMING_EVENTS 4
#define LOOKAHEAD_DAYS      14
#define DISPLAY_ROTATION    0    // 0 ou 180 (caso montado de ponta cabeça)

// 8. Modo de Atualização e Economia de Bateria (Deep Sleep)
#define REFRESH_MODE_DAILY    1
#define REFRESH_MODE_INTERVAL 2
#define REFRESH_MODE REFRESH_MODE_DAILY

#define DAILY_REFRESH_HOUR   0
#define DAILY_REFRESH_MINUTE 0
#define INTERVAL_MINUTES     30

// 9. Previsão do tempo (Open-Meteo)
#define WEATHER_ENABLED   false
#define WEATHER_LATITUDE  "-23.5505"
#define WEATHER_LONGITUDE "-46.6333"

// 10. Iluminação da Tela (Frontlight com Botão de Leitura Sob Demanda)
#define LIGHT_ENABLED         true
#define LIGHT_PIN_LED         25   // Pino GPIO conectado ao transistor que aciona os LEDs
#define LIGHT_PIN_BUTTON      33   // Pino GPIO do botão tátil (ligado ao GND, acorda via EXT0)
#define LIGHT_TIMEOUT_SECONDS 15   // Duração que a tela fica iluminada (em segundos)

