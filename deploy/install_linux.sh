#!/usr/bin/env bash
# Установка systemd + nginx для HTTP MCP. Запускать на DWH от root:
#   cd /opt/ask-pbi && ./deploy/install_linux.sh
# .env должен уже лежать в /opt/ask-pbi/.env (секреты не из git).
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
SERVICE_SRC="$PROJECT_DIR/deploy/ask-pbi.service"
NGINX_SRC="$PROJECT_DIR/deploy/nginx-n8n.hemonc.ru.conf"
NGINX_SITE="/etc/nginx/sites-available/n8n.hemonc.ru"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Нет $ENV_FILE — сначала положи секреты (см. .env.example)."
  exit 1
fi
if ! grep -q '^ASKPBI_MCP_TOKEN=.\+' "$ENV_FILE"; then
  echo "В $ENV_FILE пустой ASKPBI_MCP_TOKEN"
  exit 1
fi

mkdir -p "$PROJECT_DIR/var"
chmod 700 "$PROJECT_DIR/var"
chmod 600 "$ENV_FILE"

if [[ ! -x "$PROJECT_DIR/venv/bin/python" ]]; then
  python3 -m venv "$PROJECT_DIR/venv"
fi
"$PROJECT_DIR/venv/bin/pip" install -q --upgrade pip
"$PROJECT_DIR/venv/bin/pip" install -q -r "$PROJECT_DIR/requirements.txt"

cp "$SERVICE_SRC" /etc/systemd/system/ask-pbi.service
systemctl daemon-reload
systemctl enable --now ask-pbi
systemctl restart ask-pbi

cp "$NGINX_SRC" "$NGINX_SITE"
ln -sfn "$NGINX_SITE" /etc/nginx/sites-enabled/n8n.hemonc.ru
rm -f /etc/nginx/sites-enabled/dwh-monitor /etc/nginx/sites-enabled/default
rm -f /etc/nginx/sites-available/dwh-monitor
rm -f /etc/nginx/sites-available/dwh-monitor.bak.20260724190438

nginx -t
systemctl reload nginx

echo "ask-pbi: $(systemctl is-active ask-pbi)"
echo "health:  curl -sS http://127.0.0.1:8100/health"
echo "mcp:     https://n8n.hemonc.ru/mcp"
