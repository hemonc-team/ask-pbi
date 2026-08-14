#!/usr/bin/env bash
# Онбординг marketing skill: clone ask-pbi + config + pip hint.
set -euo pipefail

REPO_URL="${PBI_SKILL_REPO_URL:-https://github.com/hemonc-team/ask-pbi.git}"
CLONE_DIR="${PBI_SKILL_HOME:-$HOME/ask-pbi}"

echo "==> Clone into $CLONE_DIR"
if [[ -d "$CLONE_DIR/.git" ]]; then
  echo "    уже есть — git pull"
  git -C "$CLONE_DIR" pull
else
  git clone "$REPO_URL" "$CLONE_DIR"
fi

chmod +x "$CLONE_DIR/scripts/pbi_run.sh"

echo "==> config/pbi_config.json"
if [[ ! -f "$CLONE_DIR/config/pbi_config.json" ]]; then
  cp "$CLONE_DIR/config/pbi_config.example.json" "$CLONE_DIR/config/pbi_config.json"
  echo "    создан из example — проверь tokens_path"
fi

echo "==> requests"
if ! python3 -c "import requests" 2>/dev/null; then
  pip3 install requests --user || pip3 install requests --break-system-packages
fi

echo ""
echo "Готово. Дальше:"
echo "  1) Device Code: $CLONE_DIR/scripts/pbi_run.sh device-code-start"
echo "  2) Upload bootstrap zip в Claude (см. references/SETUP_MARKETER.md)"
echo "  3) Smoke: «Сколько лидов за месяц в leads_marketing?»"
