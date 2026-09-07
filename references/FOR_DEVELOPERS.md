# Техническая документация (dev)

Репозиторий [`ask-pbi`](https://github.com/hemonc-team/ask-pbi) — marketing-контур.
Как пользоваться — [`README.md`](../README.md).
Как устроен сервис целиком — [`ARCHITECTURE.md`](ARCHITECTURE.md).
Dev (патч `.pbix`, publish) — [`pbi-patch-factory`](https://github.com/hemonc-team/pbi-patch-factory).

## Архитектура (кратко)

Подробности и схема слоёв — в [`ARCHITECTURE.md`](ARCHITECTURE.md).

HTTP MCP на DWH (`https://pbi.hemonc.ru/mcp`). Claude Desktop ходит туда по
OAuth (custom connector): discovery → DCR → `/authorize` → страница логина
с общим паролем → `/token`. На DWH — Service Principal в Power BI.

Статический Bearer (`ASKPBI_MCP_TOKEN`) оставлен для Claude Code.

LLM никогда не пишет DAX: только `get_available_metrics` / `get_metric_value` /
`get_breakdown` / `analyze_trend` / `list_model_measures`. Python сам собирает
запрос по шаблону. `get_breakdown` — топ по категории (страницы, источники);
scalar-метрики через `get_metric_value`. `list_model_measures` — справочник
имён мер модели (без формул и без цифр): чтобы честно сказать «мера есть,
но не в каталоге», а не подставить соседнюю или сочинить DAX.

Локальный stdio (`python3 -m mcp_server.server`) — только для разработки,
с delegated Device Code. Маркетологам его не раздавать.

## Структура

| Путь | Назначение |
|---|---|
| `mcp_server/server.py` | Точка входа, `@mcp.tool()` |
| `mcp_server/registry.py` | Реестр подтверждённых метрик — источник правды на рантайме |
| `mcp_server/model_catalog.py` | Справочник имён мер (`list_model_measures`), без Expression |
| `mcp_server/dax_templates.py` | Сборка DAX (снепшот / период) |
| `mcp_server/critic.py` | Гейт критика для `analyze_trend` |
| `mcp_server/http_auth.py` | AuthSettings + OAuth для HTTP |
| `mcp_server/oauth_provider.py` | DCR, login, PKCE, refresh, persist |
| `mcp_server/oauth_selftest.py` | Проверка OAuth без PBI |
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

- **Прод, Claude Desktop:** MCP сам выступает OAuth AS. Owner добавляет
  custom connector `https://pbi.hemonc.ru/mcp` (без Client ID/Secret).
  Маркетолог жмёт Connect и вводит `ASKPBI_OAUTH_PASSWORD`. Redirect URI
  только Claude (`claude.ai` / `claude.com`) и localhost.
- **Прод, Claude Code:** тот же HTTP, заголовок `Authorization: Bearer`
  из `ASKPBI_MCP_TOKEN`.
- **Секреты** (`PBI_CLIENT_SECRET`, оба ключа MCP) только в `/opt/ask-pbi/.env`.
- Клиенты и выданные токены — `/opt/ask-pbi/var/oauth-store.json` (`chmod 600`).
- **Локально:** Device Code → `~/.pbi/tokens.json`, tenant/client из
  `config/pbi_config.example.json`.
- Не ставить `mcp` в `/opt/clinic-dwh/venv`.

Проверка OAuth без PBI: `python3 -m mcp_server.oauth_selftest`.

## Известные ограничения модели

- `[Fresh_Contact_Conversion_Rate_%]` отвечает на одном календарном месяце и
  пустой на диапазоне шире месяца → в реестре `multi_period_aggregatable: false`.
- `KPI team admin view` и `KPI medicine view` почти не разобраны; подтверждены
  те же три меры, что и на marketing view, плюс посетители сайта только на
  marketing view. См. `metrics-registry.md`.

## Развёртывание на DWH

Каталог `/opt/ask-pbi`, отдельно от `/opt/clinic-dwh`. Секреты только в
`.env` (`chmod 600`), шаблон — `.env.example`. Ключ для маркетологов —
`ASKPBI_MCP_TOKEN` (Claude Code) и `ASKPBI_OAUTH_PASSWORD` (страница Connect)
раздаются вручную, не в git.

Первый раз:

```bash
rsync -az --exclude '.git/' --exclude 'venv/' --exclude '.env' --exclude 'var/' \
  ./ root@62.113.60.133:/opt/ask-pbi/
ssh root@62.113.60.133 'chmod 600 /opt/ask-pbi/.env; cd /opt/ask-pbi && ./deploy/install_linux.sh'
```

Сертификат для `pbi.hemonc.ru` (после DNS A на IP сервера):

```bash
certbot certonly --nginx -d pbi.hemonc.ru
```

Обновление кода:

```bash
rsync -az --exclude '.git/' --exclude 'venv/' --exclude '.env' --exclude 'var/' \
  ./ root@62.113.60.133:/opt/ask-pbi/
ssh root@62.113.60.133 'cd /opt/ask-pbi && ./venv/bin/pip install -q -r requirements.txt && cp deploy/nginx-pbi.hemonc.ru.conf /etc/nginx/sites-available/pbi.hemonc.ru && nginx -t && systemctl reload nginx && systemctl restart ask-pbi'
```

Проверка: `curl http://127.0.0.1:8100/health`, `python3 -m mcp_server.oauth_selftest`,
`python3 -m mcp_server.smoke_test`.
Снаружи `/mcp` без ключа → 401, затем OAuth discovery.

```bash
curl -sS https://pbi.hemonc.ru/.well-known/oauth-authorization-server
curl -sS https://pbi.hemonc.ru/.well-known/oauth-protected-resource/mcp
```

После смены домена на проде обновить в `.env`: `ASKPBI_PUBLIC_URL=https://pbi.hemonc.ru/mcp`
и перезапустить `ask-pbi`. Маркетологам Desktop — заново Connect, если сменился URL.
