#!/usr/bin/env bash
# ==============================================================================
# Gravação OTA via mDNS (frw-cal.local)
# Descobre o ESP32 automaticamente na rede local sem precisar saber o IP!
# ==============================================================================
set -e

HOSTNAME="frw-cal.local"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================================="
echo "  Atualização OTA via mDNS ($HOSTNAME)"
echo "=========================================================="

echo "-> Compilando e enviando firmware para $HOSTNAME..."
cd "$PROJECT_DIR/firmware"
pio run -t upload --upload-port "$HOSTNAME"

echo ""
echo "=========================================================="
echo "  [SUCESSO] Firmware atualizado via mDNS!"
echo "=========================================================="
