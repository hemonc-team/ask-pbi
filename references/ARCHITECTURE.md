# Как устроен ask-pbi

Коротко: маркетолог спрашивает Claude обычным языком → Claude вызывает
HTTP MCP `https://pbi.hemonc.ru/mcp` → Python на DWH сам собирает DAX из
шаблонов и читает Power BI. LLM **никогда не пишет DAX** и **ничего не
меняет** в моделях.

Раньше это был локальный Claude skill `pbi-marketing-qa` (`SKILL.md` +
`pbi_run.sh` на ноутбуке). С 2026-08-19 — сервер на DWH; skill-файла в
репо больше нет, контракт для агента — описания MCP-tools.

---

## Слои

```
Claude Desktop / Claude Code
        │  MCP tools (OAuth или Bearer)
        ▼
nginx → pbi.hemonc.ru/mcp
        │
        ▼
ask-pbi (FastMCP, /opt/ask-pbi, порт 8100)
  ├─ registry.py      — какие metric_id можно считать
  ├─ dax_templates.py — единственное место, где появляется DAX
  ├─ critic.py        — гейт для трендов (в коде, не «на усмотрение LLM»)
  ├─ model_catalog.py — имена мер модели (без формул/цифр)
  └─ pbi_service_client.py — REST Power BI (Service Principal)
        │
        ▼
Power BI Service · workspace KPI Team
  · KPI marketing view
  · KPI medicine view
  · KPI team admin view
```

Локальный stdio (`python3 -m mcp_server.server`) — только для разработки
(delegated Device Code). Маркетологам не раздавать.

Патч `.pbix` / publish — другой репозиторий:
[`pbi-patch-factory`](https://github.com/hemonc-team/pbi-patch-factory).

---

## Контракт агента (5 tools)

| Tool | Зачем |
|------|--------|
| `get_available_metrics` | Каталог подтверждённых `metric_id`. Единственный источник «что можно посчитать». |
| `get_metric_value` | Одно число: снепшот или период. Scalar only. |
| `get_breakdown` | Топ по категории (`kind=ranking`): страницы, источники, регионы… |
| `analyze_trend` | Сравнение двух периодов + critic-gate. Не собирать тренд руками из двух `get_metric_value`. |
| `list_model_measures` | Справочник имён мер модели. Цифр не даёт. Если меры нет в реестре — честно «есть в PBI, не подключено». |

Правила, зашитые в tools:

1. Неизвестный `metric_id` → отказ, не «ближайшая» мера.
2. `kind=ranking` → только `get_breakdown`; scalar → не через breakdown.
3. `multi_period_aggregatable=false` → один календарный месяц; шире — отказ.
4. Датасет вне allowlist → отказ (`RESTRICTED_DATASET_NAMES` в клиенте).
5. В ответах наружу нет сырого DAX / `measure_dax_name` (чтобы LLM не копировала).

Типичный поток ответа:

1. `get_available_metrics` (или уже известный `metric_id`).
2. Вопрос «сколько» → `get_metric_value`; «топ» → `get_breakdown`; «динамика» → `analyze_trend`.
3. Вопроса нет в каталоге → `list_model_measures` → «есть / нет в модели, считать нельзя».

---

## Реестр метрик

Источник правды на рантайме — `mcp_server/registry.py` (`Metric` dataclass).
Человекочитаемое зеркало — `references/metrics-registry.md` (при расхождении
главнее код).

Поля, которые определяют поведение tools:

| Поле | Смысл |
|------|--------|
| `status` | `confirmed` / `broken` / `unverified` |
| `kind` | `scalar` \| `ranking` |
| `date_aware` | реагирует ли на фильтр дат |
| `date_table` / `date_granularity` | какая таблица дат и шаг (`month` / `day`) |
| `multi_period_aggregatable` | можно ли диапазон >1 периода |
| `measure_dax_name` | внутреннее; LLM не видит |
| `category_column` | для ranking |

Добавление метрики — алгоритм в `metrics-registry.md`:
`discover-schema` → живой `execute-dax` на 2+ периодах → `known-fields.md` →
зеркало → `Metric(...)` → `smoke_test`.

Не в периметре: пациенты, ФИО, телефоны, модели гендиректора
(`leads_marketing`, `clinic_ops`), `KPI team_embed`.

---

## DAX и critic

`dax_templates.py` — единственное место сборки запроса:

- снепшот → `ROW("value", <мера>)`
- месяц → `CALCULATE` по `date_dim_month[YearMonth]`
- день → `CALCULATE` по дневной колонке дат
- топ → `TOPN` + `SUMMARIZECOLUMNS` (cap 20)

`critic.py` раньше был отдельным skill-сценарием, который LLM могла забыть.
Теперь вызывается из `analyze_trend` всегда: сопоставимость периодов,
single-month refusal, low-confidence, нормализация по дням.
`explanation` всегда `null` — причину роста/падения инструмент не сочиняет.

---

## Auth

| Клиент | Как |
|--------|-----|
| Claude Desktop | Custom connector → OAuth AS внутри ask-pbi (DCR, login page с `ASKPBI_OAUTH_PASSWORD`) |
| Claude Code | `Authorization: Bearer` = `ASKPBI_MCP_TOKEN` |
| Power BI (прод) | Service Principal (`PBI_*` в `/opt/ask-pbi/.env`) |
| Dev локально | Device Code → `~/.pbi/tokens.json` |

Секреты только в `.env` / vault. OAuth-store: `var/oauth-store.json` (`chmod 600`).
Redirect URI — только Claude и localhost.

---

## Файлы

| Путь | Роль |
|------|------|
| `mcp_server/server.py` | Точка входа, tools, `/health`, OAuth login routes |
| `mcp_server/registry.py` | Реестр метрик |
| `mcp_server/dax_templates.py` | Шаблоны DAX |
| `mcp_server/critic.py` | Гейт трендов |
| `mcp_server/model_catalog.py` | Allowlist датасетов + разбор схемы мер |
| `mcp_server/http_auth.py` / `oauth_provider.py` | HTTP auth + OAuth |
| `mcp_server/smoke_test.py` / `oauth_selftest.py` | Проверки без / с PBI |
| `scripts/pbi_service_client.py` | REST клиент (resolve, schema, execute-dax) |
| `scripts/pbi_run.sh` | CLI для разработки схемы/DAX |
| `deploy/` | systemd + nginx → `/opt/ask-pbi` |
| `references/workspaces.md` | Workspace + allowlist |
| `references/metrics-registry.md` | Зеркало реестра |
| `references/known-fields.md` | Журнал находок (append-only) |
| `references/FOR_DEVELOPERS.md` | Деплой, auth, как добавить метрику |

---

## Эволюция (зачем так)

| Было (skill) | Стало (MCP) |
|--------------|-------------|
| `SKILL.md` + агент пишет/гоняет DAX через shell | Tools с жёстким контрактом; DAX только в Python |
| Device Code на каждом ноутбуке | Один SP на DWH + OAuth/Bearer для людей |
| Critic-gate как yaml-сценарий «на усмотрение» | Код внутри `analyze_trend` |
| Маркетолог ставит Python/git | Connect в Claude Desktop |

Имя в разговоре «скилл» часто остаётся — по сути сейчас это **MCP-сервер
с каталогом метрик**, а не Cursor/Claude `SKILL.md`.
