#!/usr/bin/env python3
"""Synchronizes Google OAuth2 credentials and settings from frw-cal into ESP32 firmware config.h."""

import json
import re
import sys
from pathlib import Path
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_YAML = PROJECT_ROOT / "config" / "config.yaml"
TOKEN_JSON = PROJECT_ROOT / "config" / "token.json"
CREDS_JSON = PROJECT_ROOT / "config" / "credentials.json"
TARGET_CONFIG_H = PROJECT_ROOT / "firmware" / "include" / "config.h"

def get_existing_wifi():
    wifi_ssid = "SUA_REDE_WIFI"
    wifi_pass = "SUA_SENHA_WIFI"
    if TARGET_CONFIG_H.exists():
        content = TARGET_CONFIG_H.read_text(encoding="utf-8")
        m_ssid = re.search(r'#define\s+WIFI_SSID\s+"([^"]*)"', content)
        m_pass = re.search(r'#define\s+WIFI_PASSWORD\s+"([^"]*)"', content)
        if m_ssid and m_ssid.group(1) != "SUA_REDE_WIFI":
            wifi_ssid = m_ssid.group(1)
        if m_pass and m_pass.group(1) != "SUA_SENHA_WIFI":
            wifi_pass = m_pass.group(1)
    return wifi_ssid, wifi_pass

def main():
    print("=== Sincronizador de Configurações para ESP32 (frw-cal) ===")
    
    # 1. Load config.yaml
    yaml_data = {}
    if CONFIG_YAML.exists():
        with open(CONFIG_YAML, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f) or {}
            print(f"[OK] Lido: {CONFIG_YAML.name}")
    else:
        print(f"[AVISO] {CONFIG_YAML.name} não encontrado, usando padrões.")

    # 2. Load token.json
    client_id = ""
    client_secret = ""
    refresh_token = ""

    if TOKEN_JSON.exists():
        try:
            with open(TOKEN_JSON, "r", encoding="utf-8") as f:
                t = json.load(f)
                client_id = t.get("client_id", "")
                client_secret = t.get("client_secret", "")
                refresh_token = t.get("refresh_token", "")
                print(f"[OK] Credenciais OAuth carregadas de: {TOKEN_JSON.name}")
        except Exception as e:
            print(f"[ERRO] Falha ao ler {TOKEN_JSON.name}: {e}")

    # Fallback to credentials.json if needed
    if (not client_id or not client_secret) and CREDS_JSON.exists():
        try:
            with open(CREDS_JSON, "r", encoding="utf-8") as f:
                c = json.load(f)
                installed = c.get("installed", c.get("web", {}))
                if not client_id:
                    client_id = installed.get("client_id", "")
                if not client_secret:
                    client_secret = installed.get("client_secret", "")
                print(f"[OK] Client ID/Secret complementados de: {CREDS_JSON.name}")
        except Exception as e:
            print(f"[ERRO] Falha ao ler {CREDS_JSON.name}: {e}")

    if not refresh_token:
        print("[ALERTA] refresh_token não encontrado em config/token.json.")
        print("         Execute primeiro: '.venv/bin/python3 src/auth.py' para autenticar no Google.")

    # 3. Calendar mode & IDs
    cal_mode_str = yaml_data.get("calendar", {}).get("mode", "google_api")
    if cal_mode_str == "google_api":
        cal_mode_def = "CALENDAR_MODE_GOOGLE_API"
    elif cal_mode_str == "ical":
        cal_mode_def = "CALENDAR_MODE_ICAL"
    else:
        cal_mode_def = "CALENDAR_MODE_MOCK"

    raw_cal_ids = yaml_data.get("calendar", {}).get("google_api", {}).get("calendar_ids", ["primary", "birthdays", "holidays"])
    resolved_ids = []
    for cid in raw_cal_ids:
        clower = cid.strip().lower()
        if clower == "primary":
            resolved_ids.append("primary")
        elif clower in ("birthdays", "aniversarios", "aniversários", "birthday"):
            resolved_ids.append("addressbook#contacts@group.v.calendar.google.com")
        elif clower in ("holidays", "feriados", "feriado"):
            resolved_ids.append("pt.brazilian#holiday@group.v.calendar.google.com")
        else:
            resolved_ids.append(cid.strip())

    # Ensure up to 4 calendar slots
    while len(resolved_ids) < 4:
        resolved_ids.append("")
    resolved_ids = resolved_ids[:4]

    # 4. Refresh & display settings
    rotation = yaml_data.get("display", {}).get("rotation", 0)
    max_events = yaml_data.get("calendar", {}).get("max_upcoming_events", 5)
    lookahead = yaml_data.get("calendar", {}).get("lookahead_days", 90)
    
    refresh_mode_str = yaml_data.get("refresh", {}).get("mode", "daily")
    refresh_mode_def = "REFRESH_MODE_DAILY" if refresh_mode_str == "daily" else "REFRESH_MODE_INTERVAL"
    
    daily_time_str = yaml_data.get("refresh", {}).get("daily_time", "00:00")
    try:
        daily_h, daily_m = [int(p) for p in daily_time_str.split(":")]
    except Exception:
        daily_h, daily_m = 0, 0
    interval_min = yaml_data.get("refresh", {}).get("interval_minutes", 30)

    # Weather
    weather_enabled = "true" if yaml_data.get("weather", {}).get("enabled", False) else "false"
    weather_lat = str(yaml_data.get("weather", {}).get("latitude", -23.5505))
    weather_lon = str(yaml_data.get("weather", {}).get("longitude", -46.6333))

    # Existing or default Wi-Fi
    wifi_ssid, wifi_pass = get_existing_wifi()

    # Generate config.h
    TARGET_CONFIG_H.parent.mkdir(parents=True, exist_ok=True)
    
    config_content = f"""#pragma once

// ==============================================================================
// Configuração do Smart Calendar ESP32 (NodeMCU-32S)
// Gerado automaticamente por tools/sync_esp32_config.py
// ==============================================================================

// 1. Rede Wi-Fi
#define WIFI_SSID       "{wifi_ssid}"
#define WIFI_PASSWORD   "{wifi_pass}"
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
#define CALENDAR_MODE {cal_mode_def}

// 5. Credenciais do Google Calendar API (OAuth 2.0)
#define GOOGLE_CLIENT_ID     "{client_id}"
#define GOOGLE_CLIENT_SECRET "{client_secret}"
#define GOOGLE_REFRESH_TOKEN "{refresh_token}"

// Calendários consultados na conta Google
#define MAX_CALENDARS 4
static const char* GOOGLE_CALENDARS[MAX_CALENDARS] = {{
    "{resolved_ids[0]}",
    "{resolved_ids[1]}",
    "{resolved_ids[2]}",
    "{resolved_ids[3]}"
}};

// 6. Modo iCal (se CALENDAR_MODE == CALENDAR_MODE_ICAL)
#define ICAL_URL ""

// 7. Configurações de exibição
#define MAX_UPCOMING_EVENTS {max_events}
#define LOOKAHEAD_DAYS      {lookahead}
#define DISPLAY_ROTATION    {rotation}    // 0 ou 180

// 8. Modo de Atualização e Economia de Bateria (Deep Sleep)
#define REFRESH_MODE_DAILY    1
#define REFRESH_MODE_INTERVAL 2
#define REFRESH_MODE {refresh_mode_def}

#define DAILY_REFRESH_HOUR   {daily_h}
#define DAILY_REFRESH_MINUTE {daily_m}
#define INTERVAL_MINUTES     {interval_min}

// 9. Previsão do tempo (Open-Meteo)
#define WEATHER_ENABLED   {weather_enabled}
#define WEATHER_LATITUDE  "{weather_lat}"
#define WEATHER_LONGITUDE "{weather_lon}"

// 10. Iluminação da Tela (Frontlight com Botão de Leitura Sob Demanda)
#define LIGHT_ENABLED         true
#define LIGHT_PIN_LED         25   // Pino GPIO conectado ao transistor que aciona os LEDs
#define LIGHT_PIN_BUTTON      33   // Pino GPIO do botão tátil (ligado ao GND, acorda via EXT0)
#define LIGHT_TIMEOUT_SECONDS 15   // Duração que a tela fica iluminada (em segundos)

// 11. Conexão com VPS (Telemetria, Logs e Auto-Update)
#define VPS_ENABLED          true
#define VPS_HOST             "http://10.8.0.1:8000"
#define VPS_API_KEY          "frw-cal-secret-token"
#define FIRMWARE_VERSION     "v1.2.1-vpn"

// 12. Rede Privada Oracle VPN (WireGuard)
#define WIREGUARD_ENABLED            true
#define WIREGUARD_LOCAL_IP          IPAddress(10, 8, 0, 7)
#define WIREGUARD_SUBNET            IPAddress(255, 255, 255, 0)
#define WIREGUARD_GATEWAY           IPAddress(10, 8, 0, 1)
#define WIREGUARD_PRIVATE_KEY       "cHAJFgXEq6ywQKmcD474CM4ioNfPUOdWRQNKAbSoz2w="
#define WIREGUARD_ENDPOINT_ADDRESS  "163.176.44.220"
#define WIREGUARD_ENDPOINT_PORT     51820
#define WIREGUARD_SERVER_PUBKEY     "w6O95bqe3MOLSuUis51zH4zj/4q17FAydaLWuCYGuW0="
"""

    with open(TARGET_CONFIG_H, "w", encoding="utf-8") as f:
        f.write(config_content)

    print(f"\n[SUCESSO] Configuração gerada com sucesso em: {TARGET_CONFIG_H}")
    if wifi_ssid == "SUA_REDE_WIFI":
        print("[LEMBRETE] Não esqueça de definir WIFI_SSID e WIFI_PASSWORD em firmware/include/config.h!")

if __name__ == "__main__":
    main()
