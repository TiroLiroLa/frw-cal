#!/usr/bin/env bash
# ==============================================================================
# Script de Upload Rápido Sem Fio via HTTP (Web OTA)
# Funciona via VPN (10.8.0.7), mDNS (frw-cal.local) ou IP local (192.168.1.35)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BIN_FILE="$PROJECT_DIR/firmware/.pio/build/nodemcu-32s/firmware.bin"

echo "=========================================================="
echo "  Upload de Firmware Sem Fio (Web OTA HTTP)"
echo "=========================================================="

# 1. Compila o firmware mais recente se necessário
echo "-> Compilando firmware..."
cd "$PROJECT_DIR/firmware"
pio run

if [ ! -f "$BIN_FILE" ]; then
    echo "[ERRO] Arquivo de firmware não encontrado: $BIN_FILE"
    exit 1
fi

# 2. Descobre qual endereço está respondendo
TARGET=""
for host in "10.8.0.7" "frw-cal.local" "192.168.1.35"; do
    echo -n "-> Testando $host... "
    if curl -s -m 2 "http://$host/" >/dev/null 2>&1; then
        echo "🟢 ONLINE!"
        TARGET="$host"
        break
    else
        echo "⚪ Offline"
    fi
done

if [ -z "$TARGET" ]; then
    echo ""
    echo "[AVISO] O ESP32 não respondeu em nenhum endereço."
    echo "Lembre-se: segure o botão do ESP32 por 5 segundos até o LED piscar 3x para ativar o Modo Manutenção!"
    exit 1
fi

echo ""
echo "-> Enviando firmware para http://$TARGET/update..."
curl --progress-bar -F "update=@$BIN_FILE" "http://$TARGET/update"

echo ""
echo "=========================================================="
echo "  [SUCESSO] Firmware enviado e gravado com sucesso!"
echo "  O ESP32 está reiniciando agora."
echo "=========================================================="
