#!/usr/bin/env bash
# Установка systemd + nginx для HTTP MCP. Запускать на DWH от root:
#   cd /opt/ask-pbi && ./deploy/install_linux.sh
# .env должен уже лежать в /opt/ask-pbi/.env (секреты не из git).
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
SERVICE_SRC="$PROJECT_DIR/deploy/ask-pbi.service"
NGINX_SRC="$PROJECT_DIR/deploy/nginx-pbi.hemonc.ru.conf"
NGINX_SITE="/etc/nginx/sites-available/pbi.hemonc.ru"

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

if [[ ! -f /etc/letsencrypt/live/pbi.hemonc.ru/fullchain.pem ]]; then
  echo "Нет TLS-сертификата для pbi.hemonc.ru."
  echo "Сначала: DNS A → этот сервер, затем:"
  echo "  certbot certonly --webroot -w /var/www/html -d pbi.hemonc.ru"
  exit 1
fi

cp "$NGINX_SRC" "$NGINX_SITE"
ln -sfn "$NGINX_SITE" /etc/nginx/sites-enabled/pbi.hemonc.ru

nginx -t
systemctl reload nginx

echo "ask-pbi: $(systemctl is-active ask-pbi)"
echo "health:  curl -sS http://127.0.0.1:8100/health"
echo "mcp:     https://pbi.hemonc.ru/mcp"
