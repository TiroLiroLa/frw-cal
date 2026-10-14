#!/usr/bin/env bash
# Atalho para abrir o painel ASCII / TUI do Calendário na VPS
SSH_KEY="/home/scs/Projects/Oracle-VPN/ssh-key-2026-10-07.key"
exec ssh -t -i "$SSH_KEY" -o StrictHostKeyChecking=no ubuntu@163.176.44.220 "calendario $@"
