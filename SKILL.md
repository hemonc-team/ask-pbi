---
name: pbi-marketing-qa
description: >-
  Метрики Power BI клиники (лиды, KPI, конверсия) через DAX. Триггер: дашборд,
  leads_marketing, KPI marketing, «сколько лидов», визуал, график.
dependencies: python>=3.10, requests
---

# pbi-marketing-qa

Read-only. Только читает цифры из Power BI Service — не меняет модели, не публикует, не refresh.

Путь к skill на диске (после `install.sh`):

`~/ask-pbi/`

Обозначим `{SKILL}` = этот путь.

## Где выполнять команды (обязательно)

`pbi_run.sh` ходит в интернет (`api.powerbi.com`, `login.microsoftonline.com`) и читает локальный `~/.pbi/tokens.json`. Это работает **только на компьютере пользователя**.

**Запрещено** запускать скрипты в cloud container / `device_bash` / VM-песочнице: там нет сети до Power BI и часто нет токена.

**Запрещено** подменять этот skill: не `marketing-analysis`, не `powerbi-modeling-mcp` / XMLA, не другие репозитории (content-fabric и т.п.). Только `pbi_run.sh` из `~/ask-pbi`.

Режим **Chat** в Claude не видит диск и не запускает `pbi_run.sh`. Нужен **Cowork** (или Code) **на этом компьютере**. Если сейчас Chat / нет файла `~/ask-pbi/SKILL.md` / нет bash на хосте:

1. Остановись. Не выдумывай цифры.
2. Попроси открыть **Cowork**, режим **на этом компьютере**, доступ к папке `~/ask-pbi`.
3. Повтори тот же вопрос.

## Когда применять

Вопросы про метрики/цифры/тренды дашбордов: `leads_marketing`, `KPI marketing view`, `clinic_ops`, «лиды», «конверсия», «сколько за месяц» — даже без слова Power BI.

## Предпосылки

- `{SKILL}/config/pbi_config.json` (из `pbi_config.example.json`) — локальный `~/.pbi/tokens.json` после `pbi_run.sh login` под **своим** PBI Pro email.
- `pip install requests`
- Если конфиг/токен отсутствует → направь к `references/SETUP_MARKETER.md`, не угадывай секреты.

## Команды (только через pbi_run.sh)

```bash
SKILL_ROOT=~/ask-pbi
"$SKILL_ROOT/scripts/pbi_run.sh" list-workspaces
"$SKILL_ROOT/scripts/pbi_run.sh" list-datasets --group <ws_id>
"$SKILL_ROOT/scripts/pbi_run.sh" discover-schema --group <ws_id> --dataset <ds_id>
"$SKILL_ROOT/scripts/pbi_run.sh" execute-dax --group <ws_id> --dataset <ds_id> \
  --query 'EVALUATE ROW("Ответ", [Имя меры])'
```

Сначала смотри `{SKILL}/references/workspaces.md` и `measures-cheatsheet.md`. `discover-schema` — только если мера не найдена (не на каждый вопрос).

## Алгоритм ответа

1. Определи workspace/датасет (`references/workspaces.md` или один уточняющий вопрос).
2. Сформулируй DAX, выполни `execute-dax`.
3. Ответь простым языком с числом и периодом. Без сырого JSON/DAX, если не просили.

## Запрещено

Никогда не вызывай и не предлагай: `publish`, `export-pbix`, `refresh`, `set-user-role`, изменение мер/layout. Правки модели — только разработчик (репозиторий [`pbi-patch-factory`](https://github.com/hemonc-team/pbi-patch-factory)).

## Обновление skill из git

Пользователь: «обнови скилл» → `git -C ~/ask-pbi pull` → подтверди, что инструкции обновлены.

## Ошибки

- `invalid_grant` / нет `tokens.json` → `{SKILL}/scripts/pbi_run.sh login` (SETUP §4).
- HTTP 403 executeQueries → попроси разработчика включить tenant setting Semantic Model Execute Queries REST API.
- Нет доступа к workspace → проверь Pro и membership в app.powerbi.com.
- Нет сети до Power BI / `device_bash` / cloud container → новый чат «на этом компьютере», см. § «Где выполнять команды».
