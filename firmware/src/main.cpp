#include <Arduino.h>
#include <WiFi.h>
#include <time.h>
#include <esp_sleep.h>
#include <driver/rtc_io.h>

#include "config.h"
#include "canvas.h"
#include "epd_ssd1683.h"
#include "fonts.h"
#include "calendar_service.h"
#include "weather_service.h"
#include "ui_renderer.h"
#include "logger.h"
#include "maintenance_service.h"
#include "vps_client.h"
#include <Preferences.h>


static Canvas canvas;
static EPD_SSD1683 display(EPD_PIN_CS, EPD_PIN_DC, EPD_PIN_RST, EPD_PIN_BUSY, EPD_PIN_SCK, EPD_PIN_MOSI);

bool connectWiFi() {
    if (strlen(WIFI_SSID) == 0 || strcmp(WIFI_SSID, "SUA_REDE_WIFI") == 0) {
        Serial.println("[WiFi] Rede Wi-Fi não configurada em include/config.h!");
        return false;
    }

    Serial.printf("[WiFi] Conectando a '%s'...\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - start) < WIFI_TIMEOUT_MS) {
        delay(300);
        Serial.print(".");
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("[WiFi] Conectado com sucesso! IP: %s\n", WiFi.localIP().toString().c_str());
        return true;
    } else {
        Serial.println("[WiFi] Falha ao conectar dentro do tempo limite.");
        return false;
    }
}

#include <esp_sntp.h>

bool syncTime() {
    Serial.println("[NTP] Sincronizando horário...");
    if (sntp_enabled()) {
        sntp_stop();
    }
    sntp_setoperatingmode(SNTP_OPMODE_POLL);
    sntp_setservername(0, const_cast<char*>(NTP_SERVER));
    sntp_init();

    setenv("TZ", TIMEZONE_POSIX, 1);
    tzset();

    unsigned long start = millis();
    while (sntp_get_sync_status() != SNTP_SYNC_STATUS_COMPLETED && (millis() - start) < 10000) {
        delay(100);
    }

    time_t now = time(nullptr);
    if (sntp_get_sync_status() == SNTP_SYNC_STATUS_COMPLETED || now >= 1700000000) {
        struct tm tm_val;
        localtime_r(&now, &tm_val);
        Serial.printf("[NTP] Horário sincronizado: %04d-%02d-%02d %02d:%02d:%02d\n",
                      tm_val.tm_year + 1900, tm_val.tm_mon + 1, tm_val.tm_mday,
                      tm_val.tm_hour, tm_val.tm_min, tm_val.tm_sec);
        return true;
    } else {
        Serial.println("[NTP] Falha ao sincronizar com servidor NTP.");
        return false;
    }
}

uint64_t calculateSleepSeconds(const struct tm& current_tm) {
#if REFRESH_MODE == REFRESH_MODE_DAILY
    // Daily mode: Sleep until DAILY_REFRESH_HOUR:DAILY_REFRESH_MINUTE:30 (e.g. 00:00:30)
    struct tm target_tm = current_tm;
    target_tm.tm_hour = DAILY_REFRESH_HOUR;
    target_tm.tm_min = DAILY_REFRESH_MINUTE;
    target_tm.tm_sec = 30; // 30 seconds buffer past midnight to ensure clock is firmly into the next day

    time_t cur_sec = mktime(const_cast<struct tm*>(&current_tm));
    time_t target_sec = mktime(&target_tm);

    if (target_sec <= cur_sec) {
        // Target time has already passed today -> schedule for tomorrow
        target_sec += 86400;
    }
    uint64_t diff = target_sec - cur_sec;
    // Safety minimum sleep (10s) to prevent zero or negative sleep timers
    if (diff < 10) diff = 10;
    return diff;
#else
    // Interval mode
    return (uint64_t)INTERVAL_MINUTES * 60ULL;
#endif
}

#if LIGHT_ENABLED
static void blinkLed(int count, int onMs, int offMs) {
    pinMode(LIGHT_PIN_LED, OUTPUT);
    for (int i = 0; i < count; i++) {
        digitalWrite(LIGHT_PIN_LED, HIGH);
        delay(onMs);
        digitalWrite(LIGHT_PIN_LED, LOW);
        if (i < count - 1) delay(offMs);
    }
}

void handleButtonInteraction() {
    Serial.println("\n[Button] Acordado por interação no botão...");

    // 1. Acende o LED imediatamente ao primeiro toque (feedback instantâneo)
    digitalWrite(LIGHT_PIN_LED, HIGH);

    unsigned long pressStart = millis();
    bool signaledSync = false;
    bool signaledMaint = false;
    int holdAction = 0; // 0 = clique rápido, 1 = sync, 2 = manutenção

    // Monitora duração caso o usuário segure o botão continuamente
    while (digitalRead(LIGHT_PIN_BUTTON) == LOW) {
        unsigned long duration = millis() - pressStart;

        // Se segurar por 3.5 segundos: Feedback visual de Modo Manutenção (4 piscadas rápidas)
        if (duration >= 3500 && !signaledMaint) {
            signaledMaint = true;
            holdAction = 2;
            for (int i = 0; i < 4; i++) {
                digitalWrite(LIGHT_PIN_LED, LOW); delay(60);
                digitalWrite(LIGHT_PIN_LED, HIGH); delay(60);
            }
        }
        // Se segurar por 1.5 segundos: Feedback visual de Sincronização (2 piscadas claras)
        else if (duration >= 1500 && !signaledSync && !signaledMaint) {
            signaledSync = true;
            holdAction = 1;
            digitalWrite(LIGHT_PIN_LED, LOW); delay(120);
            digitalWrite(LIGHT_PIN_LED, HIGH); delay(180);
            digitalWrite(LIGHT_PIN_LED, LOW); delay(120);
            digitalWrite(LIGHT_PIN_LED, HIGH);
        }
        delay(15);
    }

    // Botão foi liberado!
    // Se o usuário soltou após atingir um dos feedbacks visuais ao segurar:
    if (holdAction == 2) {
        Serial.println("\n[Button] >>> AÇÃO: MODO MANUTENÇÃO (via botão segurado >=3.5s) <<<");
        blinkLed(3, 100, 100);
        MaintenanceService::start();
        while (MaintenanceService::isRunning()) {
            MaintenanceService::handle();
            delay(10);
        }
        return;
    }

    if (holdAction == 1) {
        Serial.println("\n[Button] >>> AÇÃO: FORÇAR SINCRONIZAÇÃO (via botão segurado >=1.5s) <<<");
        blinkLed(2, 220, 150);
        return; // Retorna para setup() executar o ciclo completo
    }

    // Se soltou rapidamente (<1.5s), detecta possíveis cliques adicionais (duplo ou triplo clique)
    int clickCount = 1;
    unsigned long releaseTime = millis();

    while ((millis() - releaseTime) < 450) {
        if (digitalRead(LIGHT_PIN_BUTTON) == LOW) {
            // Clique #2 detectado!
            delay(30); // debounce
            while (digitalRead(LIGHT_PIN_BUTTON) == LOW) {
                delay(10);
                if (millis() - releaseTime > 2000) break;
            }
            clickCount = 2;
            releaseTime = millis();

            // Aguarda até 400ms por um possível clique #3
            while ((millis() - releaseTime) < 400) {
                if (digitalRead(LIGHT_PIN_BUTTON) == LOW) {
                    delay(30); // debounce
                    while (digitalRead(LIGHT_PIN_BUTTON) == LOW) {
                        delay(10);
                        if (millis() - releaseTime > 2000) break;
                    }
                    clickCount = 3;
                    break;
                }
                delay(10);
            }
            break;
        }
        delay(10);
    }

    // -------------------------------------------------------------
    // Executa a ação do comando por múltiplos cliques
    // -------------------------------------------------------------
    if (clickCount == 3) {
        // 3 cliques: MODO MANUTENÇÃO
        Serial.println("\n[Button] >>> AÇÃO: 3 CLIQUES DETECTADOS -> MODO MANUTENÇÃO <<<");
        blinkLed(3, 100, 100);
        MaintenanceService::start();
        while (MaintenanceService::isRunning()) {
            MaintenanceService::handle();
            delay(10);
        }
        return;
    }

    if (clickCount == 2) {
        // 2 cliques: FORÇAR SINCRONIZAÇÃO
        Serial.println("\n[Button] >>> AÇÃO: 2 CLIQUES DETECTADOS -> FORÇAR SINCRONIZAÇÃO <<<");
        blinkLed(2, 200, 150);
        return; // Continua para setup()
    }

    // 1 clique: LUZ DE LEITURA
    Serial.println("\n[Button] >>> AÇÃO: 1 CLIQUE -> LUZ DE LEITURA (15s) <<<");
    unsigned long startMs = millis();
    unsigned long durationMs = (unsigned long)LIGHT_TIMEOUT_SECONDS * 1000UL;

    while ((millis() - startMs) < durationMs) {
        delay(40);
        if (digitalRead(LIGHT_PIN_BUTTON) == LOW) {
            Serial.println("[Light] Botão pressionado novamente. Desligando antecipadamente.");
            delay(200); // debounce
            while (digitalRead(LIGHT_PIN_BUTTON) == LOW) delay(20);
            break;
        }
    }

    // Apaga os LEDs
    digitalWrite(LIGHT_PIN_LED, LOW);
    Serial.println("[Light] LEDs apagados. Retornando ao Deep Sleep.");

    // Configura e retorna ao Deep Sleep
    setenv("TZ", TIMEZONE_POSIX, 1);
    tzset();

    time_t now = time(nullptr);
    struct tm timeinfo = {0};
    uint64_t sleepSec = 3600;
    if (now >= 1700000000) {
        localtime_r(&now, &timeinfo);
        sleepSec = calculateSleepSeconds(timeinfo);
    }

    Serial.printf("[Power] Retornando ao Deep Sleep por %llu segundos...\n", sleepSec);
    Serial.flush();

    esp_sleep_pd_config(ESP_PD_DOMAIN_RTC_PERIPH, ESP_PD_OPTION_ON);
    pinMode(LIGHT_PIN_BUTTON, INPUT_PULLUP);
    rtc_gpio_pullup_en((gpio_num_t)LIGHT_PIN_BUTTON);
    rtc_gpio_pulldown_dis((gpio_num_t)LIGHT_PIN_BUTTON);
    rtc_gpio_hold_en((gpio_num_t)LIGHT_PIN_BUTTON);
    esp_sleep_enable_ext0_wakeup((gpio_num_t)LIGHT_PIN_BUTTON, 0);
    esp_sleep_enable_timer_wakeup(sleepSec * 1000000ULL);
    esp_deep_sleep_start();
}
#endif

void setup() {
    Serial.begin(115200);

    AppLog::init();
    setenv("TZ", TIMEZONE_POSIX, 1);
    tzset();

    esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();

#if LIGHT_ENABLED
    // Libera o hold do pino para uso em modo acordado
    rtc_gpio_hold_dis((gpio_num_t)LIGHT_PIN_BUTTON);
    pinMode(LIGHT_PIN_LED, OUTPUT);
    digitalWrite(LIGHT_PIN_LED, LOW);
    pinMode(LIGHT_PIN_BUTTON, INPUT_PULLUP);

    // Se acordou pelo botão (EXT0):
    if (wakeup_reason == ESP_SLEEP_WAKEUP_EXT0) {
        handleButtonInteraction();
        // Se a função retornou, é porque o comando foi FORÇAR SINCRONIZAÇÃO!
    }
#endif

    Serial.println("\n==============================================");
    Serial.println("  Smart Calendar (frw-cal) - NodeMCU-32S ESP32");
    Serial.println("==============================================");
    Serial.printf("[Power] Motivo de inicialização: %d\n", wakeup_reason);

    canvas.setRotation(DISPLAY_ROTATION);

    // 1. Conexão Wi-Fi
    bool wifiOk = connectWiFi();

    // 2. Sincronização de horário NTP
    if (wifiOk) {
        syncTime();
    }

    time_t now = time(nullptr);
    struct tm timeinfo = {0};
    if (now >= 1700000000) {
        localtime_r(&now, &timeinfo);
    } else {
        // Fallback default date if no internet and first boot
        timeinfo.tm_year = 2026 - 1900;
        timeinfo.tm_mon = 10 - 1; // Outubro
        timeinfo.tm_mday = 6;
        timeinfo.tm_hour = 12;
        timeinfo.tm_min = 0;
    }

    int curYear = timeinfo.tm_year + 1900;
    int curMonth = timeinfo.tm_mon + 1;
    int curDay = timeinfo.tm_mday;
    int curHour = timeinfo.tm_hour;
    int curMin = timeinfo.tm_min;

    // Proteção contra desvio do oscilador RTC: se acordou alguns minutos antes da meia-noite (ex: 23:55-23:59),
    // NÃO renderiza o dia anterior novamente! Dorme apenas os segundos restantes até passar da meia-noite.
#if REFRESH_MODE == REFRESH_MODE_DAILY
    if (curHour == 23 && curMin >= 55) {
        uint64_t sleepSec = calculateSleepSeconds(timeinfo);
        Serial.printf("[Power] Acordou antes da meia-noite (%02d:%02d). Voltando a dormir por %llu segundos...\n",
                      curHour, curMin, sleepSec);
        Serial.println("==============================================\n");
        Serial.flush();
#if LIGHT_ENABLED
        esp_sleep_pd_config(ESP_PD_DOMAIN_RTC_PERIPH, ESP_PD_OPTION_ON);
        pinMode(LIGHT_PIN_BUTTON, INPUT_PULLUP);
        rtc_gpio_pullup_en((gpio_num_t)LIGHT_PIN_BUTTON);
        rtc_gpio_pulldown_dis((gpio_num_t)LIGHT_PIN_BUTTON);
        rtc_gpio_hold_en((gpio_num_t)LIGHT_PIN_BUTTON);
        esp_sleep_enable_ext0_wakeup((gpio_num_t)LIGHT_PIN_BUTTON, 0);
#endif
        esp_sleep_enable_timer_wakeup(sleepSec * 1000000ULL);
        esp_deep_sleep_start();
    }
#endif

    // 3. Busca de compromissos
    CalendarService calendarService;
    std::vector<CalendarEvent> events;
    calendarService.fetchEvents(curYear, curMonth, curDay, LOOKAHEAD_DAYS, events);
    Serial.printf("[Calendar] Total carregado: %u eventos\n", (unsigned int)events.size());
    for (const auto& ev : events) {
        Serial.printf("  -> [%04d-%02d-%02d] '%s' (bday=%d, hol=%d, allDay=%d)\n",
                      ev.startYear, ev.startMonth, ev.startDay, ev.summary.c_str(),
                      ev.isBirthday, ev.isHoliday, ev.allDay);
    }

    // 4. Previsão do tempo (opcional)
    WeatherData weather;
    weather.valid = false;
#if WEATHER_ENABLED
    if (wifiOk) {
        WeatherService weatherService;
        weatherService.fetchWeather(WEATHER_LATITUDE, WEATHER_LONGITUDE, weather);
    }
#endif

    // 5. Renderização gráfica da interface
    Serial.printf("[UI] Renderizando calendário para %04d-%02d-%02d...\n", curYear, curMonth, curDay);
    UIRenderer renderer(canvas);
    renderer.render(curYear, curMonth, curDay, curHour, curMin, events, weather.valid ? &weather : nullptr);

    // 6. Atualização do Display E-Paper
    Serial.println("[Display] Inicializando tela WeAct 4.2\" (SSD1683)...");
    display.init();
    display.display(canvas.getBlackBuffer(), canvas.getRedBuffer());
    display.sleep();

    // 7. Check-in na VPS (Telemetria, Logs e Auto-Update)
#if VPS_ENABLED
    if (wifiOk) {
        Preferences vpsPrefs;
        vpsPrefs.begin("frw_cal", true);
        String vpsHost = vpsPrefs.getString("vps_host", VPS_HOST);
        String vpsKey = vpsPrefs.getString("vps_key", VPS_API_KEY);
        vpsPrefs.end();

        VpsCheckinResult vpsRes = VpsClient::checkin(
            vpsHost, vpsKey, FIRMWARE_VERSION,
            curYear, curMonth, curDay,
            (int)events.size(), true,
            "Ciclo diário executado com sucesso"
        );

        if (vpsRes.hasFirmwareUpdate && vpsRes.firmwareUrl.length() > 0) {
            AppLog::logf("[VPS] Atualização de firmware pendente: %s", vpsRes.firmwareUrl.c_str());
            VpsClient::downloadAndApplyOta(vpsRes.firmwareUrl);
        }
    }
#endif

    // 8. Desligamento do rádio Wi-Fi
    if (wifiOk) {
        WiFi.disconnect(true);
        WiFi.mode(WIFI_OFF);
    }

    // 9. Modo Deep Sleep ultra-econômico
    time_t sleepNow = time(nullptr);
    struct tm sleepTimeinfo = {0};
    if (sleepNow >= 1700000000) {
        localtime_r(&sleepNow, &sleepTimeinfo);
    } else {
        sleepTimeinfo = timeinfo;
    }
    uint64_t sleepSec = calculateSleepSeconds(sleepTimeinfo);
    uint32_t hours = sleepSec / 3600;
    uint32_t minutes = (sleepSec % 3600) / 60;
    uint32_t seconds = sleepSec % 60;

    Serial.printf("[Power] Entrando em Deep Sleep por %llu segundos (%02dh %02dm %02ds)...\n",
                  sleepSec, hours, minutes, seconds);
    Serial.println("==============================================\n");
    Serial.flush();

#if LIGHT_ENABLED
    // Mantém o domínio RTC_PERIPH ativo para manter o pull-up ligado em Deep Sleep
    esp_sleep_pd_config(ESP_PD_DOMAIN_RTC_PERIPH, ESP_PD_OPTION_ON);
    pinMode(LIGHT_PIN_BUTTON, INPUT_PULLUP);
    rtc_gpio_pullup_en((gpio_num_t)LIGHT_PIN_BUTTON);
    rtc_gpio_pulldown_dis((gpio_num_t)LIGHT_PIN_BUTTON);
    rtc_gpio_hold_en((gpio_num_t)LIGHT_PIN_BUTTON);
    esp_sleep_enable_ext0_wakeup((gpio_num_t)LIGHT_PIN_BUTTON, 0);
#endif

    esp_sleep_enable_timer_wakeup(sleepSec * 1000000ULL);
    esp_deep_sleep_start();
}

void loop() {
    if (MaintenanceService::isRunning()) {
        MaintenanceService::handle();
        delay(10);
    }
}

