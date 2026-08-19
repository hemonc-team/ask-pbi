# Техническая документация (dev)

Репозиторий [`ask-pbi`](https://github.com/hemonc-team/ask-pbi) — marketing-контур.
Как пользоваться и как выкатить на DWH — в [`README.md`](../README.md).
Dev (патч `.pbix`, publish) — [`pbi-patch-factory`](https://github.com/hemonc-team/pbi-patch-factory).

## Архитектура

HTTP MCP на DWH (`ASKPBI_TRANSPORT=http`, `https://n8n.hemonc.ru/mcp`).
Claude у маркетолога ходит туда по Bearer. На DWH — Service Principal в Power BI.

LLM никогда не пишет DAX: только `get_available_metrics` / `get_metric_value` /
`analyze_trend`. Python сам собирает запрос по шаблону.

Локальный stdio (`python3 -m mcp_server.server`) — только для разработки,
с delegated Device Code. Маркетологам его не раздавать.

## Структура

| Путь | Назначение |
|---|---|
| `mcp_server/server.py` | Точка входа, три `@mcp.tool()` |
| `mcp_server/registry.py` | Реестр подтверждённых метрик — источник правды на рантайме |
| `mcp_server/dax_templates.py` | Сборка DAX (снепшот / период) |
| `mcp_server/critic.py` | Гейт критика для `analyze_trend` |
| `mcp_server/http_auth.py` | Статический Bearer для HTTP |
| `mcp_server/smoke_test.py` | Живая проверка без MCP-транспорта |
| `deploy/` | systemd + nginx на DWH (`/opt/ask-pbi`) |
| `scripts/pbi_service_client.py` | Read-only REST (delegated или SP) |
| `scripts/pbi_run.sh` | CLI: `login` / `discover-schema` / `execute-dax` |
| `references/workspaces.md` | Workspace + allowlist (`RESTRICTED_DATASET_NAMES`) |
| `references/metrics-registry.md` | Человекочитаемое зеркало реестра |
| `references/known-fields.md` | Журнал находок (append-only) |

## Как добавить метрику

Полный алгоритм — `references/metrics-registry.md`. Кратко:

1. `discover-schema --scope full --refresh-cache` (через `INFO.VIEW.*`).
2. Найти меру и **активную** таблицу дат — не считать, что это всегда `Date_dim`.
3. Подтвердить живым запросом на 2+ периодах, включая квартал. Пусто на диапазоне
   → `multi_period_aggregatable: false`.
4. Запись в `known-fields.md`, `metrics-registry.md`, затем `Metric(...)` в
   `registry.py`.
5. `python3 -m mcp_server.smoke_test` + сценарий под новую метрику.

## Auth

- **Прод:** `PBI_AUTH_MODE=service_principal`, секрет и `ASKPBI_MCP_TOKEN` только
  в `/opt/ask-pbi/.env`.
- **Локально:** Device Code → `~/.pbi/tokens.json`, tenant/client из
  `config/pbi_config.example.json`.
- Не ставить `mcp` в `/opt/clinic-dwh/venv`.

## Известные ограничения модели

- `[Fresh_Contact_Conversion_Rate_%]` отвечает на одном календарном месяце и
  пустой на диапазоне шире месяца → в реестре `multi_period_aggregatable: false`.
- `KPI team admin view` и `KPI medicine view` почти не разобраны; подтверждены
  те же три меры, что и на marketing view, плюс посетители сайта только на
  marketing view. См. `metrics-registry.md`.
