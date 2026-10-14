#!/usr/bin/env bash
# ==============================================================================
# Gravação OTA via Oracle VPN (IP Fixo 10.8.0.7)
# Não depende do IP local do roteador!
# ==============================================================================
set -e

TARGET_IP="10.8.0.7"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================================="
echo "  Atualização OTA via Oracle WireGuard VPN"
echo "  Destino: $TARGET_IP:3232 (Smart-Calendar)"
echo "=========================================================="

# 1. Verifica se este PC está conectado à VPN
if ! ping -c 1 -W 2 10.8.0.1 >/dev/null 2>&1; then
    echo "[AVISO] A VPN Oracle não está ativa. Conectando agora..."
    /home/scs/Projects/Oracle-VPN/vpn.sh on || true
    sleep 2
fi

echo "-> Compilando e enviando firmware para $TARGET_IP..."
cd "$PROJECT_DIR/firmware"
pio run -t upload --upload-port "$TARGET_IP"

echo ""
echo "=========================================================="
echo "  [SUCESSO] Firmware atualizado via Oracle VPN!"
echo "=========================================================="
