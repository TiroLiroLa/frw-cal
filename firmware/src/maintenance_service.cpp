#include "maintenance_service.h"
#include "logger.h"
#include "config.h"
#include "vps_client.h"

#include <WiFi.h>
#include <Update.h>
#include <Preferences.h>
#include <esp_sleep.h>
#include <driver/rtc_io.h>


WebServer MaintenanceService::_server(80);
WireGuard MaintenanceService::_wg;
bool MaintenanceService::_running = false;
unsigned long MaintenanceService::_lastActivityMs = 0;
static Preferences prefs;

void MaintenanceService::start() {
    _running = true;
    _lastActivityMs = millis();

    AppLog::log("\n==============================================");
    AppLog::log("  [Manutenção] Iniciando Modo de Manutenção");
    AppLog::log("==============================================");

    // Visual feedback: blink reading light 3 times quickly
    pinMode(LIGHT_PIN_LED, OUTPUT);
    for (int i = 0; i < 3; i++) {
        digitalWrite(LIGHT_PIN_LED, HIGH);
        delay(120);
        digitalWrite(LIGHT_PIN_LED, LOW);
        delay(120);
    }

    // Ensure Wi-Fi is active
    if (WiFi.status() != WL_CONNECTED) {
        WiFi.mode(WIFI_STA);
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
        unsigned long startMs = millis();
        while (WiFi.status() != WL_CONNECTED && (millis() - startMs) < 15000) {
            delay(200);
            Serial.print(".");
        }
        Serial.println();
    }

    if (WiFi.status() == WL_CONNECTED) {
        AppLog::logf("[Manutenção] Conectado ao Wi-Fi! IP Local: %s", WiFi.localIP().toString().c_str());

#if WIREGUARD_ENABLED
        AppLog::log("[VPN] Conectando ao túnel WireGuard (Oracle VPN)...");
        if (_wg.begin(WIREGUARD_LOCAL_IP, WIREGUARD_PRIVATE_KEY, WIREGUARD_ENDPOINT_ADDRESS, WIREGUARD_SERVER_PUBKEY, WIREGUARD_ENDPOINT_PORT)) {
            AppLog::logf("[VPN] Conectado com sucesso! IP Fixo na VPN: %s", WIREGUARD_LOCAL_IP.toString().c_str());
            AppLog::logf("[VPN] Painel Web via VPN: http://%s/", WIREGUARD_LOCAL_IP.toString().c_str());
            AppLog::logf("[VPN] Comando OTA Fixo: pio run -d firmware -t upload --upload-port %s", WIREGUARD_LOCAL_IP.toString().c_str());
        } else {
            AppLog::log("[VPN] Falha ao iniciar WireGuard.");
        }
#endif
    } else {
        AppLog::log("[Manutenção] Aviso: Wi-Fi offline. Verifique credenciais.");
    }

    // 1. Setup ArduinoOTA
    ArduinoOTA.setHostname("frw-cal");
    ArduinoOTA.onStart([]() {
        String type = (ArduinoOTA.getCommand() == U_FLASH) ? "firmware" : "filesystem";
        AppLog::logf("[ArduinoOTA] Iniciando atualização de %s...", type.c_str());
    });
    ArduinoOTA.onEnd([]() {
        AppLog::log("\n[ArduinoOTA] Atualização concluída com sucesso! Reiniciando...");
    });
    ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
        // Log sparingly
        if ((progress / (total / 10)) != ((progress - 1) / (total / 10))) {
            Serial.printf("[ArduinoOTA] Progresso: %u%%\r", (progress / (total / 100)));
        }
    });
    ArduinoOTA.onError([](ota_error_t error) {
        AppLog::logf("[ArduinoOTA] Erro [%u]", error);
    });
    ArduinoOTA.begin();

    // 2. Setup Web Server routes
    setupRoutes();
    _server.begin();
    AppLog::log("[Manutenção] Servidor Web ativo na porta 80.");
    AppLog::log("[Manutenção] O sistema permanecerá ativo por 5 minutos.");
}

bool MaintenanceService::isRunning() {
    return _running;
}

void MaintenanceService::handle() {
    if (!_running) return;

    ArduinoOTA.handle();
    _server.handleClient();

#if LIGHT_ENABLED
    // Feedback visual suave de batimento cardíaco (Heartbeat) a cada 3 segundos
    static unsigned long lastHeartbeat = 0;
    static bool heartbeatActive = false;
    unsigned long now = millis();
    if (now - lastHeartbeat >= 3000) {
        lastHeartbeat = now;
        digitalWrite(LIGHT_PIN_LED, HIGH);
        heartbeatActive = true;
    } else if (heartbeatActive && (now - lastHeartbeat >= 60)) {
        digitalWrite(LIGHT_PIN_LED, LOW);
        heartbeatActive = false;
    }

    // Clique no botão para sair antecipadamente do Modo Manutenção
    if (digitalRead(LIGHT_PIN_BUTTON) == LOW) {
        delay(40);
        if (digitalRead(LIGHT_PIN_BUTTON) == LOW) {
            AppLog::log("[Manutenção] Botão pressionado. Encerrando modo manutenção...");
            digitalWrite(LIGHT_PIN_LED, HIGH);
            delay(400);
            digitalWrite(LIGHT_PIN_LED, LOW);
            while (digitalRead(LIGHT_PIN_BUTTON) == LOW) delay(20);
            stop();
            return;
        }
    }
#endif

    // Check 5-minute inactivity timeout
    if (millis() - _lastActivityMs >= TIMEOUT_MS) {
        AppLog::log("[Manutenção] Tempo limite de 5 minutos atingido por inatividade.");
        stop();
    }
}

void MaintenanceService::stop() {
    AppLog::log("[Manutenção] Encerrando modo de manutenção e entrando em Deep Sleep...");
    _running = false;
    _server.stop();
#if WIREGUARD_ENABLED
    _wg.end();
#endif
    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);
    delay(200);

    // Calcula tempo restante até a próxima sincronização (meia-noite)
    time_t now = time(nullptr);
    uint64_t sleepSec = 3600;
    if (now >= 1700000000) {
        struct tm timeinfo = {0};
        localtime_r(&now, &timeinfo);
        struct tm target_tm = timeinfo;
        target_tm.tm_hour = DAILY_REFRESH_HOUR;
        target_tm.tm_min = DAILY_REFRESH_MINUTE;
        target_tm.tm_sec = 30;
        time_t cur_sec = mktime(&timeinfo);
        time_t target_sec = mktime(&target_tm);
        if (target_sec <= cur_sec) target_sec += 86400;
        sleepSec = (uint64_t)(target_sec - cur_sec);
        if (sleepSec < 10) sleepSec = 10;
    }
    esp_sleep_enable_timer_wakeup(sleepSec * 1000000ULL);

#if LIGHT_ENABLED
    esp_sleep_pd_config(ESP_PD_DOMAIN_RTC_PERIPH, ESP_PD_OPTION_ON);
    pinMode(LIGHT_PIN_BUTTON, INPUT_PULLUP);
    rtc_gpio_pullup_en((gpio_num_t)LIGHT_PIN_BUTTON);
    rtc_gpio_pulldown_dis((gpio_num_t)LIGHT_PIN_BUTTON);
    rtc_gpio_hold_en((gpio_num_t)LIGHT_PIN_BUTTON);
    esp_sleep_enable_ext0_wakeup((gpio_num_t)LIGHT_PIN_BUTTON, 0);
#endif
    esp_deep_sleep_start();
}

void MaintenanceService::setupRoutes() {
    _server.on("/", HTTP_GET, handleRoot);
    _server.on("/api/logs", HTTP_GET, handleLogs);
    _server.on("/api/config", HTTP_GET, handleConfig);
    _server.on("/api/config", HTTP_POST, handleSaveConfig);
    _server.on("/action/sync", HTTP_POST, handleActionSync);
    _server.on("/action/sleep", HTTP_POST, handleActionSleep);
    _server.on("/action/reboot", HTTP_POST, handleActionReboot);
    _server.on("/action/vps-check", HTTP_POST, handleActionVpsCheck);

    // OTA upload handler
    _server.on("/update", HTTP_POST, []() {
        _lastActivityMs = millis();
        bool success = !Update.hasError();
        String html = success ? 
            "<html><body style='background:#121214;color:#00B37E;font-family:sans-serif;text-align:center;padding:50px;'>"
            "<h2>Atualização realizada com sucesso!</h2><p>O ESP32 está reiniciando...</p><a href='/' style='color:#fff;'>Voltar</a>"
            "<script>setTimeout(function(){ window.location.href='/'; }, 5000);</script></body></html>" :
            "<html><body style='background:#121214;color:#E51C44;font-family:sans-serif;text-align:center;padding:50px;'>"
            "<h2>Falha na atualização!</h2><p>Erro no arquivo enviado.</p><a href='/' style='color:#fff;'>Tentar novamente</a></body></html>";
        _server.send(success ? 200 : 500, "text/html", html);
        if (success) {
            delay(1000);
            ESP.restart();
        }
    }, []() {
        _lastActivityMs = millis();
        HTTPUpload& upload = _server.upload();
        if (upload.status == UPLOAD_FILE_START) {
            AppLog::logf("[Web OTA] Recebendo arquivo: %s", upload.filename.c_str());
            if (!Update.begin(UPDATE_SIZE_UNKNOWN)) {
                AppLog::logf("[Web OTA] Erro ao iniciar Update: %s", Update.errorString());
            }
        } else if (upload.status == UPLOAD_FILE_WRITE) {
            if (Update.write(upload.buf, upload.currentSize) != upload.currentSize) {
                AppLog::logf("[Web OTA] Erro de gravação: %s", Update.errorString());
            }
        } else if (upload.status == UPLOAD_FILE_END) {
            if (Update.end(true)) {
                AppLog::logf("[Web OTA] Gravação finalizada: %u bytes", upload.totalSize);
            } else {
                AppLog::logf("[Web OTA] Erro na finalização: %s", Update.errorString());
            }
        }
    });
}

void MaintenanceService::handleRoot() {
    _lastActivityMs = millis();
    _server.send(200, "text/html", buildDashboardHtml());
}

void MaintenanceService::handleLogs() {
    _lastActivityMs = millis();
    _server.send(200, "text/plain; charset=utf-8", AppLog::getLogsAsText());
}

void MaintenanceService::handleConfig() {
    _lastActivityMs = millis();
    prefs.begin("frw_cal", true);
    String vpsHost = prefs.getString("vps_host", VPS_HOST);
    String vpsKey = prefs.getString("vps_key", VPS_API_KEY);
    prefs.end();

    String json = "{\"vps_host\":\"" + vpsHost + "\",\"vps_key\":\"" + vpsKey + "\"}";
    _server.send(200, "application/json", json);
}

void MaintenanceService::handleSaveConfig() {
    _lastActivityMs = millis();
    if (_server.hasArg("vps_host")) {
        prefs.begin("frw_cal", false);
        prefs.putString("vps_host", _server.arg("vps_host"));
        if (_server.hasArg("vps_key")) {
            prefs.putString("vps_key", _server.arg("vps_key"));
        }
        prefs.end();
        AppLog::log("[Manutenção] Configurações de VPS salvas com sucesso!");
    }
    _server.sendHeader("Location", "/");
    _server.send(303);
}

void MaintenanceService::handleActionSync() {
    _lastActivityMs = millis();
    AppLog::log("[Manutenção] Solicitação de sincronização da agenda recebida...");
    _server.send(200, "application/json", "{\"status\":\"ok\",\"message\":\"Sincronização iniciada! O ESP32 reiniciará e atualizará a tela.\"}");
    delay(1000);
    ESP.restart();
}

void MaintenanceService::handleActionSleep() {
    _server.send(200, "application/json", "{\"status\":\"ok\",\"message\":\"Entrando em modo de economia profunda (Deep Sleep)...\"}");
    delay(500);
    stop();
}

void MaintenanceService::handleActionReboot() {
    _server.send(200, "application/json", "{\"status\":\"ok\",\"message\":\"Reiniciando ESP32...\"}");
    delay(1000);
    ESP.restart();
}

void MaintenanceService::handleActionVpsCheck() {
    _lastActivityMs = millis();
    AppLog::log("[Manutenção] Testando conexão com VPS...");
    
    prefs.begin("frw_cal", true);
    String host = prefs.getString("vps_host", VPS_HOST);
    String key = prefs.getString("vps_key", VPS_API_KEY);
    prefs.end();

    time_t now = time(nullptr);
    struct tm tm_val;
    localtime_r(&now, &tm_val);

    VpsCheckinResult res = VpsClient::checkin(
        host, key, "1.1.0",
        tm_val.tm_year + 1900, tm_val.tm_mon + 1, tm_val.tm_mday,
        0, true, "Teste manual via painel de manutenção"
    );

    if (res.success) {
        String msg = "{\"status\":\"ok\",\"message\":\"Conexão com a VPS bem-sucedida!\"}";
        _server.send(200, "application/json", msg);
    } else {
        String msg = "{\"status\":\"error\",\"message\":\"Falha ao conectar com a VPS. Verifique a URL e a rede.\"}";
        _server.send(500, "application/json", msg);
    }
}

String MaintenanceService::buildDashboardHtml() {
    unsigned long remainingSec = (TIMEOUT_MS - (millis() - _lastActivityMs)) / 1000;
    int rssi = WiFi.RSSI();
    String rssiQuality = (rssi > -60) ? "Excelente" : (rssi > -75 ? "Bom" : "Fraco");

    prefs.begin("frw_cal", true);
    String vpsHost = prefs.getString("vps_host", VPS_HOST);
    String vpsKey = prefs.getString("vps_key", VPS_API_KEY);
    prefs.end();

    String html = R"rawliteral(<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Smart Calendar · Modo Manutenção</title>
<style>
  :root {
    --bg: #121214;
    --card: #202024;
    --border: #29292e;
    --text: #e1e1e6;
    --text-muted: #a8a8b3;
    --primary: #00b37e;
    --danger: #e51c44;
    --accent: #8257e5;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    padding: 20px;
    display: flex;
    justify-content: center;
  }
  .container { max-width: 680px; width: 100%; display: flex; flex-direction: column; gap: 16px; }
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  .header h1 { font-size: 1.15rem; font-weight: 700; color: #fff; }
  .badge { background: var(--primary); color: #fff; padding: 3px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: bold; }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .card-title { font-size: 0.95rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
  .grid-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; }
  .stat-box { background: #1a1a1e; padding: 10px; border-radius: 6px; border: 1px solid var(--border); }
  .stat-label { font-size: 0.75rem; color: var(--text-muted); }
  .stat-val { font-size: 1.05rem; font-weight: bold; color: #fff; margin-top: 4px; word-break: break-all; }
  .btn-group { display: flex; flex-wrap: wrap; gap: 8px; }
  button, .btn {
    background: #2a2a30;
    color: #fff;
    border: 1px solid var(--border);
    padding: 10px 14px;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 600;
    font-size: 0.85rem;
    transition: 0.15s ease;
  }
  button:hover, .btn:hover { background: #35353d; }
  .btn-primary { background: var(--primary); border-color: var(--primary); }
  .btn-primary:hover { background: #00996c; }
  .btn-danger { background: var(--danger); border-color: var(--danger); }
  .btn-danger:hover { background: #c51438; }
  .btn-accent { background: var(--accent); border-color: var(--accent); }
  .btn-accent:hover { background: #7146d6; }
  pre#logs {
    background: #0d0d0f;
    padding: 12px;
    border-radius: 6px;
    font-family: monospace;
    font-size: 0.78rem;
    color: #00e676;
    max-height: 220px;
    overflow-y: auto;
    white-space: pre-wrap;
    border: 1px solid #1f1f23;
  }
  input[type="text"], input[type="file"] {
    width: 100%;
    padding: 8px 12px;
    background: #1a1a1e;
    border: 1px solid var(--border);
    border-radius: 6px;
    color: #fff;
    font-size: 0.85rem;
  }
  .progress-bar {
    width: 100%;
    height: 8px;
    background: #1a1a1e;
    border-radius: 4px;
    overflow: hidden;
    display: none;
    margin-top: 8px;
  }
  .progress-bar-fill { width: 0%; height: 100%; background: var(--primary); transition: width 0.1s ease; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <h1>🗓️ Smart Calendar (frw-cal)</h1>
      <span style="font-size:0.8rem; color:var(--text-muted)">Modo Manutenção & OTA Sem Fio</span>
    </div>
    <span class="badge">ONLINE</span>
  </div>

  <div class="card">
    <div class="card-title">Status do Dispositivo</div>
    <div class="grid-stats">
      <div class="stat-box">
        <div class="stat-label">Endereço IP</div>
        <div class="stat-val">)rawliteral" + WiFi.localIP().toString() + R"rawliteral(</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Sinal Wi-Fi (RSSI)</div>
        <div class="stat-val">)rawliteral" + String(rssi) + " dBm · " + rssiQuality + R"rawliteral(</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Memória Livre (Heap)</div>
        <div class="stat-val">)rawliteral" + String(ESP.getFreeHeap() / 1024) + R"rawliteral( KB</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Tempo Ativo Restante</div>
        <div class="stat-val">)rawliteral" + String(remainingSec / 60) + "m " + String(remainingSec % 60) + R"rawliteral(s</div>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Ações Rápidas</div>
    <div class="btn-group">
      <button class="btn-primary" onclick="callApi('/action/sync')">🔄 Atualizar Calendário Agora</button>
      <button class="btn-accent" onclick="callApi('/action/vps-check')">🌐 Testar Check-in VPS</button>
      <button onclick="callApi('/action/reboot')">🔁 Reiniciar ESP32</button>
      <button class="btn-danger" onclick="callApi('/action/sleep')">💤 Sair e Voltar a Dormir</button>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Atualização de Firmware Sem Fio (OTA)</div>
    <p style="font-size:0.8rem; color:var(--text-muted)">Selecione o arquivo compilado <code>firmware.bin</code> para atualizar o ESP32 pelo navegador:</p>
    <form id="uploadForm" method="POST" action="/update" enctype="multipart/form-data">
      <input type="file" name="update" id="fileInput" accept=".bin" required>
      <button type="submit" class="btn-primary" style="margin-top:8px;">Subir Novo Firmware (.bin)</button>
      <div class="progress-bar" id="progressBar"><div class="progress-bar-fill" id="progressFill"></div></div>
    </form>
    <p style="font-size:0.75rem; color:var(--text-muted); margin-top:4px;">Dica: você também pode enviar pelo terminal via <code>pio run -d firmware -t upload --upload-port )rawliteral" + WiFi.localIP().toString() + R"rawliteral(</code></p>
  </div>

  <div class="card">
    <div class="card-title">Configurações da VPS</div>
    <form method="POST" action="/api/config">
      <div style="display:flex; flex-direction:column; gap:8px;">
        <div>
          <label style="font-size:0.8rem; color:var(--text-muted)">URL / Host da VPS:</label>
          <input type="text" name="vps_host" value=")rawliteral" + vpsHost + R"rawliteral(" placeholder="http://163.176.44.220:8000">
        </div>
        <div>
          <label style="font-size:0.8rem; color:var(--text-muted)">Chave de API (opcional):</label>
          <input type="text" name="vps_key" value=")rawliteral" + vpsKey + R"rawliteral(" placeholder="sua-chave-secreta">
        </div>
        <button type="submit" style="align-self:flex-start;">Salvar Configurações</button>
      </div>
    </form>
  </div>

  <div class="card">
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <div class="card-title">Logs Recentes</div>
      <button onclick="loadLogs()" style="padding:4px 8px; font-size:0.75rem;">Recarregar Logs</button>
    </div>
    <pre id="logs">Carregando logs...</pre>
  </div>
</div>

<script>
function loadLogs() {
  fetch('/api/logs').then(r => r.text()).then(t => {
    const el = document.getElementById('logs');
    el.innerText = t;
    el.scrollTop = el.scrollHeight;
  });
}
function callApi(endpoint) {
  if (confirm('Deseja executar esta ação?')) {
    fetch(endpoint, { method: 'POST' }).then(r => r.json()).then(d => {
      alert(d.message);
      if (endpoint === '/action/sleep') window.close();
    });
  }
}
document.getElementById('uploadForm').onsubmit = function(e) {
  e.preventDefault();
  const fileInput = document.getElementById('fileInput');
  if (!fileInput.files.length) return;
  const pBar = document.getElementById('progressBar');
  const pFill = document.getElementById('progressFill');
  pBar.style.display = 'block';

  const formData = new FormData();
  formData.append('update', fileInput.files[0]);

  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/update', true);
  xhr.upload.onprogress = function(ev) {
    if (ev.lengthComputable) {
      const pct = (ev.loaded / ev.total) * 100;
      pFill.style.width = pct + '%';
    }
  };
  xhr.onload = function() {
    alert(xhr.status === 200 ? 'Firmware gravado com sucesso! O ESP32 está reiniciando.' : 'Erro na gravação.');
    setTimeout(() => { window.location.reload(); }, 4000);
  };
  xhr.send(formData);
};
loadLogs();
setInterval(loadLogs, 3000);
</script>
</body>
</html>)rawliteral";
    return html;
}
