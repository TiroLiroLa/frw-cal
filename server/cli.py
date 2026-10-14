#!/usr/bin/env python3
"""
frw-cal Terminal - Aplicação ASCII / TUI para visualização e gerenciamento do Smart Calendar ESP32.
Roda nativamente no terminal da VPS ou via SSH.
"""

import argparse
import os
import re
import select
import sqlite3
import sys
import termios
import time
import tty
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Cores ANSI & Formatação
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


def make_box_line(content, inner_width=75, border_color="\033[94m"):
    clean_len = len(strip_ansi(content))
    pad = max(0, inner_width - clean_len)
    return f"  {border_color}│{RESET} {content}{' ' * pad} {border_color}│{RESET}"


# Cores de Primeiro Plano
BLACK = "\033[30m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

# Cores Brilhantes
B_RED = "\033[91m"
B_GREEN = "\033[92m"
B_YELLOW = "\033[93m"
B_BLUE = "\033[94m"
B_MAGENTA = "\033[95m"
B_CYAN = "\033[96m"
B_WHITE = "\033[97m"

# Cores de Fundo
BG_DARK = "\033[48;5;235m"
BG_BLUE = "\033[48;5;24m"
BG_GREEN = "\033[48;5;22m"
BG_RED = "\033[48;5;52m"

# Diretórios padrão
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_FILE = DATA_DIR / "hub.db"
FIRMWARE_DIR = BASE_DIR / "firmware_storage"


def clear_screen():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def get_db_connection():
    if not DB_FILE.exists():
        return None
    try:
        conn = sqlite3.connect(DB_FILE, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        return None


def get_latest_checkin():
    conn = get_db_connection()
    if not conn:
        return None
    try:
        c = conn.cursor()
        c.execute("""
            SELECT * FROM checkins
            ORDER BY id DESC LIMIT 1
        """)
        row = c.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        if conn:
            conn.close()
        return None


def get_checkin_history(limit=8):
    conn = get_db_connection()
    if not conn:
        return []
    try:
        c = conn.cursor()
        c.execute("""
            SELECT id, timestamp, ip, rssi, firmware_version, free_heap, date, events_count, google_api_ok
            FROM checkins
            ORDER BY id DESC LIMIT ?
        """, (limit,))
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows
    except Exception:
        if conn:
            conn.close()
        return []


def get_active_firmware():
    conn = get_db_connection()
    if not conn:
        return None
    try:
        c = conn.cursor()
        c.execute("""
            SELECT * FROM firmware_info
            WHERE is_active = 1
            ORDER BY id DESC LIMIT 1
        """)
        row = c.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        if conn:
            conn.close()
        return None


def get_available_firmwares():
    FIRMWARE_DIR.mkdir(parents=True, exist_ok=True)
    bins = list(FIRMWARE_DIR.glob("*.bin"))
    result = []
    for f in sorted(bins, key=lambda x: x.stat().st_mtime, reverse=True):
        sz_kb = f.stat().st_size / 1024
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
        result.append({
            "name": f.name,
            "path": str(f),
            "size_kb": f"{sz_kb:.1f} KB",
            "modified": mtime
        })
    return result


def set_active_firmware(version, filename):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        c = conn.cursor()
        c.execute("UPDATE firmware_info SET is_active = 0")
        c.execute("""
            INSERT INTO firmware_info (version, filename, upload_time, is_active)
            VALUES (?, ?, datetime('now'), 1)
        """, (version, filename))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        if conn:
            conn.close()
        return False


def format_relative_time(dt_str):
    if not dt_str:
        return "Nunca"
    try:
        dt_str = dt_str.replace("T", " ")
        if "." in dt_str:
            dt_str = dt_str.split(".")[0]
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        diff = now - dt

        seconds = int(diff.total_seconds())
        if seconds < 0:
            return "Agora"
        if seconds < 60:
            return f"Há {seconds}s"
        minutes = seconds // 60
        if minutes < 60:
            return f"Há {minutes}m"
        hours = minutes // 60
        if hours < 24:
            return f"Há {hours}h {minutes % 60}m"
        days = hours // 24
        return f"Há {days}d ({dt.strftime('%d/%m %H:%M')})"
    except Exception:
        return dt_str


TZ_BR = timezone(timedelta(hours=-3))


def format_local_timestamp(utc_dt_str):
    if not utc_dt_str:
        return "-"
    try:
        clean_str = utc_dt_str.replace("T", " ").split(".")[0]
        dt_utc = datetime.strptime(clean_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        dt_local = dt_utc.astimezone(TZ_BR)
        return dt_local.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return utc_dt_str


def get_rssi_bar(rssi):
    if rssi is None:
        return f"{DIM}N/D{RESET}"
    if rssi >= -60:
        bar = f"{B_GREEN}█████{RESET}"
        quality = "Excelente"
    elif rssi >= -70:
        bar = f"{GREEN}████░{RESET}"
        quality = "Bom"
    elif rssi >= -80:
        bar = f"{YELLOW}███░░{RESET}"
        quality = "Médio"
    elif rssi >= -90:
        bar = f"{RED}██░░░{RESET}"
        quality = "Fraco"
    else:
        bar = f"{B_RED}█░░░░{RESET}"
        quality = "Péssimo"
    return f"{bar} {rssi} dBm ({quality})"


def get_next_midnight_str():
    now_br = datetime.now(TZ_BR)
    tomorrow_br = now_br.date() + timedelta(days=1)
    next_wake_br = datetime(tomorrow_br.year, tomorrow_br.month, tomorrow_br.day, 0, 0, 30, tzinfo=TZ_BR)
    diff = next_wake_br - now_br
    hours, remainder = divmod(int(diff.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"00:00:30 (em {hours}h {minutes:02d}m {seconds:02d}s)"


def render_banner():
    banner = f"""{B_CYAN}{BOLD}
   ╔═══════════════════════════════════════════════════════════════════════════════╗
   ║   _____ ______          __        _____          _                          ║
   ║  |  ___|  _ \\ \\        / /       / ____|        | |                         ║
   ║  | |_  | |_) \\ \\  /\\  / / _____ | |     __ _  __| |                         ║
   ║  |  _| |  _ < \\ \\/  \\/ / |_____|| |    / _` |/ _` |                         ║
   ║  | |   | | \\ \\ \\  /\\  /         | |___| (_| | (_| |                         ║
   ║  |_|   |_|  \\_\\ \\/  \\/           \\_____\\__,_|\\__,_|  {B_YELLOW}[TERMINAL HUB v1.2]{B_CYAN}    ║
   ╚═══════════════════════════════════════════════════════════════════════════════╝{RESET}"""
    return banner


def render_dashboard():
    latest = get_latest_checkin()
    active_fw = get_active_firmware()
    history = get_checkin_history(limit=6)

    output = []
    output.append(render_banner())

    # Determinar status geral do dispositivo
    if not latest:
        status_badge = f"{B_YELLOW}[ AGUARDANDO PRIMEIRO CHECK-IN ]{RESET}"
        device_state = "Aguardando conexão do ESP32 via Wi-Fi"
    else:
        # Calcular tempo desde o último check-in
        try:
            ts_str = latest["timestamp"].replace("T", " ").split(".")[0]
            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            diff_min = (datetime.now(timezone.utc).replace(tzinfo=None) - dt).total_seconds() / 60
            if diff_min < 2:
                status_badge = f"{B_GREEN}{BOLD}[ 🟢 ONLINE - ATIVO AGORA ]{RESET}"
                device_state = "Processando ciclo / Atualizando"
            elif diff_min < 1440:  # menos de 24h
                status_badge = f"{B_CYAN}[ 💤 EM DEEP SLEEP (AGUARDANDO MEIA-NOITE) ]{RESET}"
                device_state = "Dormindo para economia de energia até 00:00:30"
            else:
                status_badge = f"{B_RED}[ 🔴 DESCONECTADO HÁ MAIS DE 24H ]{RESET}"
                device_state = "Dispositivo ausente no ciclo esperado"
        except Exception:
            status_badge = f"{B_GREEN}[ 🟢 OPERACIONAL ]{RESET}"
            device_state = "Ciclo registrado"

    output.append(f"\n  {BOLD}STATUS DO DISPOSITIVO:{RESET} {status_badge}")
    output.append(f"  {DIM}Modo Operacional:{RESET} {device_state}\n")

    # Caixa de Informações do Dispositivo
    box_w = 75
    output.append(f"  {B_BLUE}┌─ Resumo de Telemetria ──────────────────────────────────────────────────────┐{RESET}")
    if latest:
        fw_ver = latest.get("firmware_version") or "v1.0.0"
        fw_status = f"{B_GREEN}✔ Atualizado{RESET}" if (not active_fw or fw_ver == active_fw.get("version")) else f"{B_YELLOW}⬆ Atualização disponível ({active_fw.get('version')}){RESET}"
        heap_kb = (latest.get("free_heap") or 0) / 1024
        gapi_status = f"{B_GREEN}✔ OK (Tokens Válidos){RESET}" if latest.get("google_api_ok") else f"{B_RED}✖ Erro de Autenticação{RESET}"

        l1 = f"{BOLD}Dispositivo:{RESET} NodeMCU-32S ESP32      {BOLD}MAC:{RESET}         {latest.get('mac') or 'N/D'}"
        l2 = f"{BOLD}IP Local:{RESET}    {latest.get('ip') or 'N/D':<18} {BOLD}Sinal Wi-Fi:{RESET} {get_rssi_bar(latest.get('rssi'))}"
        l3 = f"{BOLD}Firmware:{RESET}    {fw_ver} ({fw_status})    {BOLD}Heap Livre:{RESET}  {heap_kb:.1f} KB"
        l4 = f"{BOLD}Display EPD:{RESET} Data: {latest.get('date') or 'N/D':<12} {BOLD}Eventos:{RESET}     {latest.get('events_count', 0)} carregados"
        l5 = f"{BOLD}Google API:{RESET}  {gapi_status}     {BOLD}Último Visto:{RESET} {format_relative_time(latest.get('timestamp'))}"
        l6 = f"{BOLD}Próximo Wake:{RESET} {get_next_midnight_str()}"

        output.append(make_box_line(l1, box_w, B_BLUE))
        output.append(make_box_line(l2, box_w, B_BLUE))
        output.append(make_box_line(l3, box_w, B_BLUE))
        output.append(make_box_line(l4, box_w, B_BLUE))
        output.append(make_box_line(l5, box_w, B_BLUE))
        output.append(make_box_line(l6, box_w, B_BLUE))
    else:
        output.append(make_box_line(f"{DIM}Nenhum dado recebido ainda do ESP32.{RESET}", box_w, B_BLUE))
        output.append(make_box_line(f"O ESP32 enviará telemetria automaticamente via túnel WireGuard (10.8.0.7):", box_w, B_BLUE))
        output.append(make_box_line(f"• Para forçar agora: segure o botão do ESP32 por {BOLD}3 segundos{RESET} (sincronizar).", box_w, B_BLUE))
        output.append(make_box_line(f"• Para modo manutenção: segure o botão por {BOLD}5 segundos{RESET} (OTA e Web UI).", box_w, B_BLUE))
    output.append(f"  {B_BLUE}└─────────────────────────────────────────────────────────────────────────────┘{RESET}")

    # Caixa de Firmware OTA Ativo
    output.append(f"\n  {B_MAGENTA}┌─ Auto-Update OTA (Firmware Disponível na VPS) ──────────────────────────────┐{RESET}")
    if active_fw:
        f1 = f"{BOLD}Versão Ativa:{RESET}  {B_GREEN}{active_fw.get('version')}{RESET} ({active_fw.get('filename')})"
        f2 = f"{BOLD}Configurado:{RESET}   {format_local_timestamp(active_fw.get('upload_time', ''))} | {DIM}ESP32 atualizará no próximo ciclo{RESET}"
        output.append(make_box_line(f1, box_w, B_MAGENTA))
        output.append(make_box_line(f2, box_w, B_MAGENTA))
    else:
        output.append(make_box_line(f"{DIM}Nenhuma atualização pendente (o ESP32 manterá a versão instalada atual){RESET}", box_w, B_MAGENTA))
    output.append(f"  {B_MAGENTA}└─────────────────────────────────────────────────────────────────────────────┘{RESET}")

    # Tabela de Histórico de Check-ins
    output.append(f"\n  {BOLD}HISTÓRICO RECENTE DE SINCRONIZAÇÃO:{RESET}")
    output.append(f"  {DIM}{'ID':<4} {'Horário':<19} {'Data Display':<13} {'Eventos':<9} {'Wi-Fi':<10} {'Heap':<9} {'Google API':<12} {'Versão':<8}{RESET}")
    output.append(f"  {DIM}{'─'*4} {'─'*19} {'─'*13} {'─'*9} {'─'*10} {'─'*9} {'─'*12} {'─'*8}{RESET}")

    if history:
        for r in history:
            ts = format_local_timestamp(r.get("timestamp", ""))
            dt_disp = r.get("date") or "-"
            evts = str(r.get("events_count", 0))
            rssi = f"{r.get('rssi')} dBm" if r.get('rssi') else "-"
            heap = f"{(r.get('free_heap') or 0)//1024} KB"
            g_ok = f"{B_GREEN}✔ OK{RESET}" if r.get("google_api_ok") else f"{B_RED}✖ Falha{RESET}"
            ver = r.get("firmware_version") or "-"
            output.append(f"  {r['id']:<4} {ts:<19} {dt_disp:<13} {evts:<9} {rssi:<10} {heap:<9} {g_ok:<20} {ver:<8}")
    else:
        output.append(f"  {DIM}(Nenhum registro de check-in histórico no banco de dados){RESET}")

    # Rodapé com Atalhos
    output.append(f"\n  {BG_DARK}{BOLD} ATALHOS: {RESET} {BOLD}[r]{RESET} Recarregar   {BOLD}[l]{RESET} Ver Logs do ESP32   {BOLD}[f]{RESET} Gerenciar OTA   {BOLD}[s]{RESET} Serviço Hub   {BOLD}[q]{RESET} Sair")
    output.append("")

    return "\n".join(output)


def view_logs_screen():
    clear_screen()
    latest = get_latest_checkin()
    print(f"{B_CYAN}{BOLD}=== LOGS DO ÚLTIMO CICLO DO ESP32 ==={RESET}\n")

    if not latest or not latest.get("last_log"):
        print(f"{YELLOW}Nenhum log armazenado para o último ciclo.{RESET}")
    else:
        raw_log = latest.get("last_log", "")
        for line in raw_log.split("\n"):
            line = line.strip()
            if not line:
                continue
            if "[GoogleAPI]" in line:
                print(f"{B_GREEN}{line}{RESET}")
            elif "[Calendar]" in line:
                print(f"{B_CYAN}{line}{RESET}")
            elif "[Display]" in line or "[EPD]" in line or "[UI]" in line:
                print(f"{B_YELLOW}{line}{RESET}")
            elif "[Error]" in line or "fail" in line.lower() or "error" in line.lower():
                print(f"{B_RED}{line}{RESET}")
            elif "[VPS]" in line:
                print(f"{B_MAGENTA}{line}{RESET}")
            else:
                print(f"{WHITE}{line}{RESET}")

    print(f"\n{DIM}Pressione qualquer tecla para voltar ao painel...{RESET}")
    wait_key()


def manage_firmware_screen():
    clear_screen()
    print(f"{B_MAGENTA}{BOLD}=== GERENCIADOR DE FIRMWARE OTA (AUTO-UPDATE) ==={RESET}\n")

    active = get_active_firmware()
    if active:
        print(f"  {BOLD}Versão Ativa para Distribuição:{RESET} {B_GREEN}{active.get('version')}{RESET} ({active.get('filename')})")
        print(f"  {DIM}Quando o ESP32 acordar, ele baixará automaticamente essa versão.{RESET}\n")
    else:
        print(f"  {YELLOW}Nenhum firmware ativo no momento.{RESET}\n")

    files = get_available_firmwares()
    print(f"  {BOLD}Arquivos .bin encontrados em {FIRMWARE_DIR}:{RESET}")
    print(f"  {DIM}{'#':<3} {'Arquivo':<35} {'Tamanho':<12} {'Modificado':<16}{RESET}")
    print(f"  {DIM}{'─'*3} {'─'*35} {'─'*12} {'─'*16}{RESET}")

    if not files:
        print(f"  {DIM}Nenhum arquivo .bin encontrado na pasta.{RESET}")
        print(f"  {DIM}Para adicionar um novo firmware, copie o arquivo .bin para:{RESET}")
        print(f"  {CYAN}{FIRMWARE_DIR}/{RESET}\n")
    else:
        for idx, f in enumerate(files, 1):
            print(f"  {idx:<3} {f['name']:<35} {f['size_kb']:<12} {f['modified']:<16}")
        print("")

    print(f"  {BOLD}[1-9]{RESET} Ativar arquivo correspondente para OTA")
    print(f"  {BOLD}[d]{RESET}   Desativar atualização pendente (remover OTA ativo)")
    print(f"  {BOLD}[v]{RESET}   Voltar ao painel principal")
    print("")

    choice = input("  Escolha uma opção: ").strip().lower()
    if choice == "v" or not choice:
        return
    elif choice == "d":
        conn = get_db_connection()
        if conn:
            conn.execute("UPDATE firmware_info SET is_active = 0")
            conn.commit()
            conn.close()
            print(f"  {GREEN}✔ Atualizações OTA desativadas.{RESET}")
            time.sleep(1.2)
    elif choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= len(files):
            chosen = files[idx - 1]
            ver = input(f"  Digite o identificador de versão (ex: v1.3.0) [{chosen['name']}]: ").strip()
            if not ver:
                ver = chosen["name"].replace(".bin", "")
            if set_active_firmware(ver, chosen["name"]):
                print(f"  {B_GREEN}✔ Firmware '{ver}' ({chosen['name']}) ativado para o próximo ciclo!{RESET}")
            else:
                print(f"  {B_RED}✖ Erro ao registrar firmware no banco.{RESET}")
            time.sleep(1.5)


def check_hub_service_screen():
    clear_screen()
    print(f"{B_BLUE}{BOLD}=== STATUS DO SERVIÇO DE FUNDO (SYSTEMD) ==={RESET}\n")
    os.system("systemctl status frw-cal-hub.service --no-pager")
    print(f"\n{DIM}Pressione qualquer tecla para voltar ao painel...{RESET}")
    wait_key()


def wait_key(timeout=None):
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        if timeout:
            rlist, _, _ = select.select([sys.stdin], [], [], timeout)
            if not rlist:
                return None
        ch = sys.stdin.read(1)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def run_interactive_loop():
    # Loop interativo
    while True:
        clear_screen()
        print(render_dashboard())

        # Esperar tecla com timeout de 5 segundos para auto-refresh
        key = wait_key(timeout=5.0)

        if not key:
            continue
        elif key.lower() == "q":
            clear_screen()
            print(f"{GREEN}Até logo!{RESET}\n")
            break
        elif key.lower() == "r":
            continue
        elif key.lower() == "l":
            view_logs_screen()
        elif key.lower() == "f":
            manage_firmware_screen()
        elif key.lower() == "s":
            check_hub_service_screen()


def main():
    parser = argparse.ArgumentParser(description="frw-cal Terminal Hub (ASCII / TUI)")
    parser.add_argument("-s", "--status", action="store_true", help="Exibe apenas o resumo em texto e sai imediatamente")
    parser.add_argument("-l", "--logs", action="store_true", help="Exibe os últimos logs do ESP32 e sai")
    parser.add_argument("-f", "--firmware", action="store_true", help="Abre o menu de gerenciamento de firmware")
    args = parser.parse_args()

    if args.status:
        print(render_dashboard())
        sys.exit(0)
    elif args.logs:
        latest = get_latest_checkin()
        if latest and latest.get("last_log"):
            print(latest["last_log"])
        else:
            print("Nenhum log registrado.")
        sys.exit(0)
    elif args.firmware:
        manage_firmware_screen()
        sys.exit(0)

    # Se a saída for um terminal interativo (TTY), entra no modo interativo TUI
    if sys.stdout.isatty():
        try:
            run_interactive_loop()
        except KeyboardInterrupt:
            clear_screen()
            print(f"\n{GREEN}Encerrado.{RESET}")
    else:
        # Se for pipe ou redirecionamento, imprime o dashboard estático
        print(render_dashboard())


if __name__ == "__main__":
    main()
