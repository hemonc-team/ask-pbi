---
name: pbi-marketing-qa
description: >-
  Метрики Power BI клиники (лиды, KPI, конверсия) через DAX. Триггер: дашборд,
  leads_marketing, KPI marketing, «сколько лидов», визуал, график.
dependencies: python>=3.10, requests
---

# pbi-marketing-qa

Read-only. Цифры из Power BI через `{SKILL}/scripts/pbi_run.sh`. `{SKILL}` = `~/ask-pbi/`.

**Cowork** + папка `~/ask-pbi` на компьютере. Не Chat, не cloud/`device_bash`. Ошибки → `references/TROUBLESHOOTING.md`.

## Быстрый путь (минимум команд)

1. Прочитай `references/workspaces.md` + `references/measures-cheatsheet.md`.
2. Один раз за вопрос (или за сессию) — `resolve-dataset` по имени модели.
3. `execute-dax` по рецепту из шпаргалки.
4. `discover-schema` — **только** если меры нет в шпаргалке (кэш на диске, без колонок).

```bash
SKILL=~/ask-pbi
"$SKILL/scripts/pbi_run.sh" resolve-dataset --dataset leads_marketing --workspace "Входящий трафик"
"$SKILL/scripts/pbi_run.sh" execute-dax --group <group_id> --dataset <dataset_id> --query '<DAX>'
"$SKILL/scripts/pbi_run.sh" discover-schema --group <group_id> --dataset <dataset_id>
```

`resolve-dataset` ищет модель по имени во всех доступных workspace (ID датасета не храним в git — меняется при publish).

## Алгоритм

1. Модель из вопроса или `workspaces.md` (синонимы).
2. `resolve-dataset` → `group_id`, `dataset_id`.
3. DAX из `measures-cheatsheet.md` или `discover-schema` (таблицы+меры, локальный кэш `~/.pbi/schema-cache/`).
4. Ответ простым языком: число + период. Без сырого JSON/DAX.
5. **Гейт критика** (обязателен при сравнении периодов, %, тренде или причинно-следственной формулировке; необязателен для простого lookup одного числа): перед выдачей ответа вызови скилл `critic-gate` со сценарием `references/critic_gate_scenario.yaml` (скопируй, заполни `result_ref` черновиком ответа, добавь специфичные под этот вопрос критерии). `NEEDS-FIX` → исправь указанное, не показывай черновик до ACCEPT.

## Запрещено

`publish`, `export-pbix`, `refresh`, правки модели, другие skills/MCP (`marketing-analysis`, XMLA). Только этот skill.

## Обновление

«Обнови скилл» → `git -C ~/ask-pbi pull`.
