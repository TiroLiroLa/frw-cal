#!/usr/bin/env bash
# ==============================================================================
# Script de Instalação Automatizada - frw-cal
# Raspberry Pi Zero 2W + WeAct Studio 4.2" E-Paper BWR
# ==============================================================================

set -e

echo "=========================================================="
echo "  Instalação do Smart Calendar (frw-cal) no Raspberry Pi  "
echo "=========================================================="

# 1. Verificar permissões e pacotes do sistema
echo "[1/5] Instalando dependências do sistema..."
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-pil \
    python3-numpy \
    python3-spidev \
    python3-gpiozero \
    python3-rpi.gpio \
    fonts-liberation \
    git \
    libopenjp2-7 \
    libtiff5 || true

# 2. Habilitar SPI no Raspberry Pi
echo "[2/5] Habilitando interface SPI no Raspberry Pi..."
if command -v raspi-config >/dev/null 2>&1; then
    sudo raspi-config nonint do_spi 0
    echo "  -> SPI habilitado via raspi-config."
else
    echo "  -> raspi-config não encontrado. Certifique-se de habilitar SPI manualmente."
fi

# 3. Criar ambiente virtual Python
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[3/5] Configurando ambiente virtual Python (.venv)..."
if [ ! -d ".venv" ]; then
    python3 -m venv --system-site-packages .venv
fi

# 4. Instalar dependências Python
echo "[4/5] Instalando pacotes Python..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install gpiozero spidev || true

# 5. Criar arquivo de configuração inicial se não existir
echo "[5/5] Verificando arquivo de configuração..."
if [ ! -f "config/config.yaml" ]; then
    cp config/config.example.yaml config/config.yaml
    echo "  -> config/config.yaml criado a partir do exemplo."
fi

echo ""
echo "=========================================================="
echo "  Instalação concluída com sucesso!                      "
echo "=========================================================="
echo ""
echo "Próximos passos:"
echo "1. Configure o modo de calendário em config/config.yaml:"
echo "   - Para Google Calendar API: execute '.venv/bin/python3 src/auth.py'"
echo "   - Para iCal: adicione a URL em config/config.yaml"
echo "2. Para testar o display físico:"
echo "   Edite config/config.yaml e altere display.type para 'epaper'"
echo "   Execute: .venv/bin/python3 -m src.main --once"
echo "3. Para habilitar inicialização automática no boot (systemd):"
echo "   sudo cp systemd/frw-cal.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable --now frw-cal.service"
echo ""
