# Воркспейсы и модели

ID workspace стабильны. **ID датасета не храним** — бери через `resolve-dataset` (меняется при publish).

| Workspace (UI) | group_id | Основная модель |
|---|---|---|
| Входящий трафик (звонки, лиды, конверсия) | `4b92027c-cc1d-460f-b48b-2b56f731408a` | `leads_marketing` |
| KPI Team | `8f13bfda-3032-42d9-ab87-5410016e5047` | `KPI marketing view` |
| Admin monitoring | `dbdd21cd-aca6-4214-98ac-75d7402a3310` | служебный |

## resolve-dataset (предпочтительно)

```bash
SKILL=~/ask-pbi
"$SKILL/scripts/pbi_run.sh" resolve-dataset --dataset leads_marketing --workspace "Входящий трафик"
"$SKILL/scripts/pbi_run.sh" resolve-dataset --dataset "KPI marketing view" --workspace "KPI Team"
```

Если модель есть в нескольких workspace — уточни workspace фразой пользователя или спроси один раз.

## Синонимы

| Фраза пользователя | Workspace (подсказка) | Модель |
|---|---|---|
| leads, лиды, воронка, свежие контакты | Входящий трафик | leads_marketing |
| KPI, KPI marketing, посетители, командный KPI | KPI Team | KPI marketing view |
