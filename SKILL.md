---
name: pbi-marketing-qa
description: >-
  Метрики Power BI клиники (лиды, KPI, конверсия, fresh contact, воронка,
  посетители) через DAX. Триггер: дашборд, leads_marketing, KPI, KPI Team,
  «сколько лидов», конверсия, fresh contact, визуал, график. Это Power BI —
  НЕ Bitrix24/CRM (conversion-analysis, lead-analysis): если в вопросе есть
  Power BI/KPI Team/leads_marketing/дашборд — используй этот скилл.
dependencies: python>=3.10, requests
---

# pbi-marketing-qa

Read-only. Цифры из Power BI через `{SKILL}/scripts/pbi_run.sh`. `{SKILL}` = `~/ask-pbi/`.

**Cowork** + папка `~/ask-pbi` на компьютере. Не Chat, не cloud/`device_bash`. Ошибки → `references/TROUBLESHOOTING.md`.

**Область (workspace `KPI Team`, `8f13bfda-3032-42d9-ab87-5410016e5047`):** в скоуп входят
ТОЛЬКО `KPI team admin view`, `KPI medicine view`, `KPI marketing view`. Остальные
датасеты этого workspace (`KPI team_embed`, `clinic_ops`, дубль `leads_marketing` —
если видны в `list-datasets`) — вне скоупа этого скилла, не резолвить и не запрашивать
по ним данные, даже если `resolve-dataset` их находит.

## Быстрый путь (минимум команд)

1. Прочитай `references/workspaces.md` + `references/measures-cheatsheet.md` + `references/known-fields.md`.
2. Один раз за вопрос (или за сессию) — `resolve-dataset` по имени модели.
3. `execute-dax` по рецепту из шпаргалки.
4. `discover-schema` — **только** если меры нет в шпаргалке (кэш на диске, без колонок).
5. Нашёл неочевидную ловушку/join (пустое поле, ID не там где ожидалось, таблица в
   другом датасете)? Допиши находку в `references/known-fields.md`, не держи в контексте одной сессии.

```bash
SKILL=~/ask-pbi
"$SKILL/scripts/pbi_run.sh" resolve-dataset --dataset "KPI marketing view" --workspace "KPI Team"
"$SKILL/scripts/pbi_run.sh" execute-dax --group <group_id> --dataset <dataset_id> --query '<DAX>'
"$SKILL/scripts/pbi_run.sh" discover-schema --group <group_id> --dataset <dataset_id>
```

`resolve-dataset` ищет модель по имени во всех доступных workspace (ID датасета не храним в git — меняется при publish).

## Алгоритм

1. Модель из вопроса или `workspaces.md` (синонимы).
2. `resolve-dataset` → `group_id`, `dataset_id`.
3. DAX из `measures-cheatsheet.md` или `discover-schema` (таблицы+меры, локальный кэш `~/.pbi/schema-cache/`).
4. Ответ простым языком: число + период. Без сырого JSON/DAX.
5. **Гейт критика** (обязателен при сравнении периодов, %, тренде или причинно-следственной формулировке; необязателен для простого lookup одного числа): перед выдачей ответа вызови скилл `critic-gate` со сценарием `references/critic_gate_scenario.yaml` (скопируй, заполни `result_ref` черновиком ответа, добавь специфичные под этот вопрос критерии). **Обязательно добавь хотя бы один recall/позитивный-контроль критерий** (известное заранее число/факт, которое ответ ОБЯЗАН воспроизвести) — без него `critic-gate` по своим же правилам должен отказаться запускаться, а «пустой» или ошибочный ответ пройдёт AC1–AC5 вакуумно. `NEEDS-FIX` → исправь указанное, не показывай черновик до ACCEPT.

## Запрещено

`publish`, `export-pbix`, `refresh`, правки модели, другие skills/MCP (`marketing-analysis`, XMLA). Только этот skill.

## Обновление

«Обнови скилл» → `git -C ~/ask-pbi pull`.
