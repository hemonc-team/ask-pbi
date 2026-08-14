#!/usr/bin/env bash
# Wrapper: читает config/pbi_config.json и вызывает read-only PBI client.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG="${PBI_CONFIG_PATH:-$SKILL_ROOT/config/pbi_config.json}"

if [[ ! -f "$CONFIG" ]]; then
  echo "ERROR: нет $CONFIG — скопируй config/pbi_config.example.json" >&2
  exit 2
fi

export PBI_TENANT_ID
export PBI_CLIENT_ID
export PBI_TOKENS_PATH
PBI_TENANT_ID="$(python3 -c "import json; print(json.load(open('$CONFIG'))['tenant_id'])")"
PBI_CLIENT_ID="$(python3 -c "import json; print(json.load(open('$CONFIG'))['client_id'])")"
PBI_TOKENS_PATH="$(python3 -c "import json; print(json.load(open('$CONFIG'))['tokens_path'])")"

exec python3 "$SCRIPT_DIR/pbi_service_client.py" "$@"
