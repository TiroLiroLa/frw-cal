#!/usr/bin/env bash
set -e

# ==============================================================================
# Script de Implantação do frw-cal Hub na VPS Oracle Cloud
# ==============================================================================

VPS_IP="163.176.44.220"
VPS_USER="ubuntu"
SSH_KEY="/home/scs/Projects/Oracle-VPN/ssh-key-2026-10-07.key"
REMOTE_DIR="/home/ubuntu/frw-cal-hub"

echo "=========================================================="
echo "  Implantando frw-cal Hub na VPS ($VPS_IP)..."
echo "=========================================================="

if [ ! -f "$SSH_KEY" ]; then
    echo "[ERRO] Chave SSH não encontrada em: $SSH_KEY"
    exit 1
fi

SSH_CMD="ssh -i $SSH_KEY -o StrictHostKeyChecking=no -o ConnectTimeout=8 $VPS_USER@$VPS_IP"
SCP_CMD="scp -i $SSH_KEY -o StrictHostKeyChecking=no"

# 1. Criar pasta remota
echo "-> Criando diretório na VPS: $REMOTE_DIR"
$SSH_CMD "mkdir -p $REMOTE_DIR/data $REMOTE_DIR/firmware_storage"

# 2. Copiar scripts da aplicação
echo "-> Enviando arquivos da aplicação..."
$SCP_CMD server/app.py "$VPS_USER@$VPS_IP:$REMOTE_DIR/app.py"
$SCP_CMD server/cli.py "$VPS_USER@$VPS_IP:$REMOTE_DIR/cli.py"
$SCP_CMD server/frw-cal-hub.service "$VPS_USER@$VPS_IP:/tmp/frw-cal-hub.service"
if [ -d "server/firmware_storage" ] && [ "$(ls -A server/firmware_storage)" ]; then
    echo "-> Enviando arquivos de firmware..."
    $SCP_CMD server/firmware_storage/*.bin "$VPS_USER@$VPS_IP:$REMOTE_DIR/firmware_storage/" 2>/dev/null || true
fi
$SSH_CMD "
    chmod +x $REMOTE_DIR/cli.py
    sudo ln -sf $REMOTE_DIR/cli.py /usr/local/bin/calendario
"

# 3. Configurar iptables na VPS (liberar porta 8000 se não estiver)
echo "-> Verificando regras de firewall (porta 8000)..."
$SSH_CMD "
    if ! sudo iptables -C INPUT -p tcp --dport 8000 -j ACCEPT 2>/dev/null; then
        echo 'Liberando porta 8000 no iptables da VPS...'
        sudo iptables -I INPUT 1 -p tcp --dport 8000 -j ACCEPT
        sudo netfilter-persistent save 2>/dev/null || true
    fi
    # Encaminhar porta 8000 dentro da rede WireGuard (wg-easy) para a VPS
    docker exec wg-easy iptables -t nat -C PREROUTING -p tcp --dport 8000 -j DNAT --to-destination 172.17.0.1:8000 2>/dev/null || \
    docker exec wg-easy iptables -t nat -I PREROUTING 1 -p tcp --dport 8000 -j DNAT --to-destination 172.17.0.1:8000 2>/dev/null || true

    docker exec wg-easy iptables -t nat -C POSTROUTING -p tcp -d 172.17.0.1 --dport 8000 -j MASQUERADE 2>/dev/null || \
    docker exec wg-easy iptables -t nat -I POSTROUTING 1 -p tcp -d 172.17.0.1 --dport 8000 -j MASQUERADE 2>/dev/null || true
"

# 4. Instalar e iniciar o serviço systemd
echo "-> Configurando serviço systemd 'frw-cal-hub'..."
$SSH_CMD "
    sudo cp /tmp/frw-cal-hub.service /etc/systemd/system/frw-cal-hub.service
    sudo systemctl daemon-reload
    sudo systemctl enable --now frw-cal-hub.service
    sudo systemctl restart frw-cal-hub.service
    sudo systemctl status frw-cal-hub.service --no-pager
"

echo ""
echo "=========================================================="
echo "  [SUCESSO] frw-cal Hub ativo na VPS!"
echo "  Painel de Controle disponível em:"
echo "  -> Via VPN:    http://10.8.0.1:8000/"
echo "  -> Via Direto: http://$VPS_IP:8000/"
echo "=========================================================="
