#!/usr/bin/env python3
"""
frw-cal Hub - Central de Controle e Auto-Update na VPS para o Smart Calendar ESP32.
Executa sem nenhuma dependência externa (apenas biblioteca padrão do Python).
"""

import http.server
import json
import os
import re
import socketserver
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PORT = int(os.environ.get("PORT", 8000))
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
FIRMWARE_DIR = BASE_DIR / "firmware_storage"
DB_FILE = DATA_DIR / "hub.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)
FIRMWARE_DIR.mkdir(parents=True, exist_ok=True)


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            device_id TEXT,
            mac TEXT,
            ip TEXT,
            rssi INTEGER,
            firmware_version TEXT,
            free_heap INTEGER,
            date TEXT,
            events_count INTEGER,
            google_api_ok INTEGER,
            last_log TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS firmware_info (
            id INTEGER PRIMARY KEY,
            version TEXT,
            filename TEXT,
            upload_time DATETIME,
            is_active INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()


init_db()


class HubHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Format clean console logs
        sys.stdout.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {args[0]} {args[1]} {args[2]}\n")
        sys.stdout.flush()

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
        elif path.startswith("/api/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
        else:
            self.send_response(200)
            self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self.handle_dashboard()
        elif path == "/api/status":
            self.handle_api_status()
        elif path == "/api/logs":
            self.handle_api_logs()
        elif path.startswith("/firmware/"):
            self.handle_download_firmware(path)
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/checkin":
            self.handle_checkin()
        elif path == "/api/firmware/upload":
            self.handle_upload_firmware()
        elif path == "/api/firmware/toggle":
            self.handle_toggle_firmware()
        else:
            self.send_error(404, "Not Found")

    def handle_checkin(self):
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len == 0:
            self.send_json({"error": "Empty body"}, 400)
            return

        raw_data = self.rfile.read(content_len)
        try:
            data = json.loads(raw_data.decode("utf-8"))
        except Exception as e:
            self.send_json({"error": f"Invalid JSON: {e}"}, 400)
            return

        device_id = data.get("device_id", "unknown")
        mac = data.get("mac", "")
        ip = data.get("ip", "")
        rssi = data.get("rssi", 0)
        fw_ver = data.get("firmware_version", "1.0.0")
        free_heap = data.get("free_heap", 0)
        current_date = data.get("date", "")
        events_count = data.get("events_count", 0)
        google_ok = 1 if data.get("google_api_ok", False) else 0
        last_log = data.get("last_log") or data.get("logs") or ""

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
            INSERT INTO checkins (device_id, mac, ip, rssi, firmware_version, free_heap, date, events_count, google_api_ok, last_log)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (device_id, mac, ip, rssi, fw_ver, free_heap, current_date, events_count, google_ok, last_log))
        conn.commit()

        # Check for active firmware update
        c.execute("SELECT version, filename, is_active FROM firmware_info WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
        fw_row = c.fetchone()
        conn.close()

        has_update = False
        target_fw_url = ""
        target_fw_ver = ""

        if fw_row:
            active_version, filename, is_active = fw_row
            if is_active and active_version != fw_ver:
                has_update = True
                target_fw_ver = active_version
                host_header = self.headers.get("Host", f"163.176.44.220:{PORT}")
                target_fw_url = f"http://{host_header}/firmware/{filename}"

        response = {
            "status": "ok",
            "has_firmware_update": has_update,
            "firmware_version": target_fw_ver,
            "firmware_url": target_fw_url,
            "action": "none"
        }
        self.send_json(response)

    def handle_download_firmware(self, path):
        filename = os.path.basename(path)
        filepath = FIRMWARE_DIR / filename
        if not filepath.exists():
            self.send_error(404, "Firmware binary not found")
            return

        size = filepath.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(size))
        self.end_headers()

        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                self.wfile.write(chunk)

    def handle_upload_firmware(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self.send_json({"error": "Content-Type must be multipart/form-data"}, 400)
            return

        boundary = content_type.split("boundary=")[1].encode()
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)

        parts = body.split(b"--" + boundary)
        uploaded_file = None
        new_version = f"1.{int(time.time()) % 1000}"

        for part in parts:
            if b'filename="' in part:
                headers_part, file_data = part.split(b"\r\n\r\n", 1)
                file_data = file_data.rstrip(b"\r\n")
                uploaded_file = file_data
            elif b'name="version"' in part:
                _, val = part.split(b"\r\n\r\n", 1)
                v_str = val.rstrip(b"\r\n").decode("utf-8").strip()
                if v_str:
                    new_version = v_str

        if not uploaded_file:
            self.send_json({"error": "No file uploaded"}, 400)
            return

        filename = f"firmware_{new_version}.bin"
        target_path = FIRMWARE_DIR / filename
        with open(target_path, "wb") as f:
            f.write(uploaded_file)

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE firmware_info SET is_active = 0")
        c.execute("""
            INSERT INTO firmware_info (version, filename, upload_time, is_active)
            VALUES (?, ?, ?, 1)
        """, (new_version, filename, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()

        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def handle_toggle_firmware(self):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT is_active FROM firmware_info ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        if row:
            new_state = 0 if row[0] == 1 else 1
            c.execute("UPDATE firmware_info SET is_active = ? WHERE id = (SELECT id FROM firmware_info ORDER BY id DESC LIMIT 1)", (new_state,))
            conn.commit()
        conn.close()

        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def handle_api_status(self):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT timestamp, device_id, mac, ip, rssi, firmware_version, free_heap, date, events_count, google_api_ok, last_log FROM checkins ORDER BY id DESC LIMIT 1")
        last_checkin = c.fetchone()

        c.execute("SELECT version, filename, upload_time, is_active FROM firmware_info WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
        active_fw = c.fetchone()
        conn.close()

        resp = {
            "last_checkin": None,
            "active_firmware": None
        }
        if last_checkin:
            resp["last_checkin"] = {
                "timestamp": last_checkin[0],
                "device_id": last_checkin[1],
                "mac": last_checkin[2],
                "ip": last_checkin[3],
                "rssi": last_checkin[4],
                "firmware_version": last_checkin[5],
                "free_heap": last_checkin[6],
                "date": last_checkin[7],
                "events_count": last_checkin[8],
                "google_api_ok": bool(last_checkin[9]),
                "last_log": last_checkin[10]
            }
        if active_fw:
            resp["active_firmware"] = {
                "version": active_fw[0],
                "filename": active_fw[1],
                "upload_time": active_fw[2],
                "is_active": bool(active_fw[3])
            }
        self.send_json(resp)

    def handle_api_logs(self):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT timestamp, ip, events_count, google_api_ok, last_log FROM checkins ORDER BY id DESC LIMIT 25")
        rows = c.fetchall()
        conn.close()

        logs = []
        for r in rows:
            logs.append({
                "timestamp": r[0],
                "ip": r[1],
                "events_count": r[2],
                "google_api_ok": bool(r[3]),
                "last_log": r[4]
            })
        self.send_json(logs)

    def handle_dashboard(self):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT timestamp, device_id, mac, ip, rssi, firmware_version, free_heap, date, events_count, google_api_ok, last_log FROM checkins ORDER BY id DESC LIMIT 1")
        last_checkin = c.fetchone()

        c.execute("SELECT version, filename, upload_time, is_active FROM firmware_info ORDER BY id DESC LIMIT 1")
        fw_row = c.fetchone()

        c.execute("SELECT timestamp, ip, firmware_version, events_count, google_api_ok, last_log FROM checkins ORDER BY id DESC LIMIT 15")
        history = c.fetchall()
        conn.close()

        # Format stats
        last_seen = "Nunca"
        ip_addr = "Desconhecido"
        rssi_str = "--"
        fw_installed = "--"
        events_str = "--"
        google_badge = '<span class="badge badge-gray">Sem dados</span>'

        if last_checkin:
            last_seen = last_checkin[0]
            ip_addr = last_checkin[3]
            rssi = last_checkin[4]
            rssi_str = f"{rssi} dBm"
            fw_installed = last_checkin[5]
            events_str = f"{last_checkin[8]} eventos"
            google_badge = '<span class="badge badge-green">Conectado</span>' if last_checkin[9] else '<span class="badge badge-red">Erro</span>'

        active_fw_ver = "Nenhum"
        fw_status = "Inativo"
        fw_btn_text = "Ativar Auto-Update"
        fw_btn_class = "btn-green"

        if fw_row:
            active_fw_ver = fw_row[0]
            if fw_row[3] == 1:
                fw_status = "🟢 Pronto para Envio"
                fw_btn_text = "Pausar Atualização"
                fw_btn_class = "btn-red"
            else:
                fw_status = "⚪ Pausado"

        history_rows = ""
        for h in history:
            g_badge = '<span class="badge badge-green">OK</span>' if h[4] else '<span class="badge badge-red">FALHA</span>'
            history_rows += f"""
            <tr>
              <td>{h[0]}</td>
              <td><code>{h[1]}</code></td>
              <td>v{h[2]}</td>
              <td>{h[3]}</td>
              <td>{g_badge}</td>
              <td style="color:#a8a8b3;font-size:0.8rem;">{h[5]}</td>
            </tr>
            """

        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>frw-cal Hub · Central VPS</title>
<style>
  :root {{
    --bg: #0f0f11;
    --card: #18181b;
    --border: #27272a;
    --text: #f4f4f5;
    --muted: #a1a1aa;
    --green: #10b981;
    --red: #ef4444;
    --purple: #8b5cf6;
    --blue: #3b82f6;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    padding: 24px;
    display: flex;
    justify-content: center;
  }}
  .container {{ max-width: 900px; width: 100%; display: flex; flex-direction: column; gap: 20px; }}
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
  }}
  .header h1 {{ font-size: 1.25rem; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 8px; }}
  .badge {{ padding: 4px 10px; border-radius: 16px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; }}
  .badge-green {{ background: #064e3b; color: #34d399; border: 1px solid #059669; }}
  .badge-red {{ background: #7f1d1d; color: #f87171; border: 1px solid #dc2626; }}
  .badge-gray {{ background: #27272a; color: #a1a1aa; }}
  .card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }}
  .card-title {{ font-size: 0.9rem; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }}
  .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
  .stat-box {{ background: #121215; padding: 12px 16px; border-radius: 8px; border: 1px solid var(--border); }}
  .stat-label {{ font-size: 0.75rem; color: var(--muted); }}
  .stat-val {{ font-size: 1.15rem; font-weight: 700; color: #fff; margin-top: 4px; }}
  button, .btn {{
    background: #27272a;
    color: #fff;
    border: 1px solid var(--border);
    padding: 10px 16px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.85rem;
    cursor: pointer;
    transition: 0.15s ease;
  }}
  button:hover, .btn:hover {{ background: #3f3f46; }}
  .btn-green {{ background: var(--green); border-color: var(--green); color: #fff; }}
  .btn-green:hover {{ background: #059669; }}
  .btn-red {{ background: var(--red); border-color: var(--red); color: #fff; }}
  .btn-red:hover {{ background: #dc2626; }}
  .upload-box {{
    border: 2px dashed var(--border);
    border-radius: 8px;
    padding: 24px;
    text-align: center;
    background: #121215;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
  }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--muted); font-size: 0.75rem; text-transform: uppercase; font-weight: 600; }}
  tr:hover {{ background: #1f1f23; }}
  code {{ font-family: monospace; background: #27272a; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <h1>🗓️ Smart Calendar Hub</h1>
      <span style="font-size:0.8rem; color:var(--muted)">Painel Central na Nuvem (Oracle VPS)</span>
    </div>
    <span class="badge badge-green">GATEWAY ATIVO</span>
  </div>

  <div class="card">
    <div class="card-title">Dispositivo: NodeMCU-32S (E-Paper)</div>
    <div class="stats-grid">
      <div class="stat-box">
        <div class="stat-label">Último Check-in</div>
        <div class="stat-val" style="font-size:1rem;">{last_seen}</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">IP na Rede Local</div>
        <div class="stat-val"><a href="http://{ip_addr}" target="_blank" style="color:var(--blue);text-decoration:none;">{ip_addr}</a></div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Firmware em Execução</div>
        <div class="stat-val">v{fw_installed}</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Wi-Fi (RSSI)</div>
        <div class="stat-val">{rssi_str}</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Eventos Sincronizados</div>
        <div class="stat-val">{events_str}</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Status Google Agenda</div>
        <div class="stat-val" style="font-size:0.9rem;">{google_badge}</div>
      </div>
    </div>
  </div>

  <div class="card">
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <div class="card-title">Deploy Remoto de Firmware (Auto-OTA)</div>
      <span style="font-size:0.8rem; color:var(--muted)">Status do Hub: <strong>{fw_status}</strong> (v{active_fw_ver})</span>
    </div>
    <p style="font-size:0.82rem; color:var(--muted)">
      Faça upload do arquivo <code>firmware.bin</code> compilado. Quando o ESP32 acordar no próximo ciclo diário, ele baixará automaticamente e atualizará seu código sem tocar no hardware!
    </p>

    <form class="upload-box" method="POST" action="/api/firmware/upload" enctype="multipart/form-data">
      <input type="text" name="version" placeholder="Versão (ex: 1.2.0)" style="max-width:200px; padding:8px 12px; background:#18181b; border:1px solid var(--border); border-radius:6px; color:#fff;" required>
      <input type="file" name="firmware" accept=".bin" required style="color:#fff;">
      <button type="submit" class="btn-green">Enviar Novo Firmware para a VPS</button>
    </form>

    <form method="POST" action="/api/firmware/toggle" style="align-self:flex-start;">
      <button type="submit" class="{fw_btn_class}">{fw_btn_text}</button>
    </form>
  </div>

  <div class="card">
    <div class="card-title">Histórico de Conexões e Ciclos Diários</div>
    <div style="overflow-x:auto;">
      <table>
        <thead>
          <tr>
            <th>Data / Hora</th>
            <th>IP</th>
            <th>Versão</th>
            <th>Eventos</th>
            <th>Google API</th>
            <th>Log</th>
          </tr>
        </thead>
        <tbody>
          {history_rows if history_rows else '<tr><td colspan="6" style="text-align:center;color:var(--muted)">Nenhum ciclo registrado ainda. Aguardando check-in do ESP32...</td></tr>'}
        </tbody>
      </table>
    </div>
  </div>
</div>
</body>
</html>"""
        self.send_html(html)


def run_server():
    print(f"==================================================")
    print(f"  frw-cal Hub (Central VPS) iniciando na porta {PORT}")
    print(f"==================================================")
    with socketserver.TCPServer(("", PORT), HubHandler) as httpd:
        httpd.allow_reuse_address = True
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor encerrado.")


if __name__ == "__main__":
    run_server()
