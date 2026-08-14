# Известные воркспейсы и отчёты (getcure.co.site)

Обновляет разработчик после `list-workspaces` / `list-datasets`. ID воркспейсов не секрет.

| Workspace (UI) | group_id | Основной датасет / отчёт |
|---|---|---|
| Входящий трафик (звонки, лиды, конверсия) | `4b92027c-cc1d-460f-b48b-2b56f731408a` | `leads_marketing` |
| KPI Team | `8f13bfda-3032-42d9-ab87-5410016e5047` | `KPI marketing view` |
| Admin monitoring | `dbdd21cd-aca6-4214-98ac-75d7402a3310` | служебный |

## Как найти dataset_id

Если пользователь назвал отчёт, а dataset_id неизвестен:

```bash
SKILL_ROOT=~/ask-pbi
"$SKILL_ROOT/scripts/pbi_run.sh" list-datasets --group <group_id>
"$SKILL_ROOT/scripts/pbi_run.sh" list-reports --group <group_id>
```

Имя датасета часто совпадает с именем semantic model (`leads_marketing`, `KPI marketing view`).

## Синонимы от пользователя

| Фраза пользователя | Workspace | Датасет |
|---|---|---|
| leads, лиды, воронка, маркетинг leads | Входящий трафик | leads_marketing |
| KPI, KPI marketing, командный KPI | KPI Team | KPI marketing view |
