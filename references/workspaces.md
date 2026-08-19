# Воркспейсы и модели

ID workspace стабильны. **ID датасета не храним как единственный источник** — резолвить
через `resolve-dataset` каждый раз (меняется при publish); ID ниже — только последнее
подтверждённое значение для справки/диагностики (проверено 2026-08-19 живым `list-datasets`).

| Workspace (UI) | group_id | Модель | dataset_id (последний подтверждённый) | В скоупе? |
|---|---|---|---|---|
| Входящий трафик (звонки, лиды, конверсия) | `4b92027c-cc1d-460f-b48b-2b56f731408a` | `leads_marketing` | — | **нет, модель гендиректора** |
| KPI Team | `8f13bfda-3032-42d9-ab87-5410016e5047` | `KPI marketing view` | `e6606b8d-5bf8-4137-afe5-a41c673ee188` | да |
| KPI Team | `8f13bfda-3032-42d9-ab87-5410016e5047` | `KPI medicine view` | `30721258-3d98-4cbb-bdff-6ba7193f7006` | да |
| KPI Team | `8f13bfda-3032-42d9-ab87-5410016e5047` | `KPI team admin view` | `75e26980-cf1f-4718-85f1-c579c9c6e484` | да |
| KPI Team | `8f13bfda-3032-42d9-ab87-5410016e5047` | `KPI team_embed` | `d6d573fe-01a5-4b75-94db-4de18fd791f0` | **нет** |
| KPI Team | `8f13bfda-3032-42d9-ab87-5410016e5047` | `clinic_ops` | — | **нет, модель гендиректора** |
| Admin monitoring | `dbdd21cd-aca6-4214-98ac-75d7402a3310` | служебный | — | нет |

**Правило скоупа (проверено 2026-08-19, зафиксировано на уровне кода в
`RESTRICTED_DATASET_NAMES`):** единственный рабочий workspace — **KPI Team**,
единственные разрешённые модели в нём — ровно три: `KPI marketing view`,
`KPI medicine view`, `KPI team admin view`. Всё остальное — вне периметра,
включая `KPI team_embed` (служебная модель для встраиваемых отчётов, заблокирована
2026-08-19) и `leads_marketing`/`clinic_ops` в любом workspace/под любым
dataset_id (модели гендиректора, заблокированы 2026-08-18). Ограничение
enforced в коде (`_assert_dataset_allowed`), а не только в тексте — при попытке
обратиться к любой из них `resolve-dataset`/`execute-dax` упадут с ошибкой.
Не пытаться подставить синоним/похожую формулировку, чтобы обойти это.

## resolve-dataset (предпочтительно)

```bash
SKILL=~/ask-pbi
"$SKILL/scripts/pbi_run.sh" resolve-dataset --dataset "KPI marketing view" --workspace "KPI Team"
"$SKILL/scripts/pbi_run.sh" resolve-dataset --dataset "KPI medicine view" --workspace "KPI Team"
"$SKILL/scripts/pbi_run.sh" resolve-dataset --dataset "KPI team admin view" --workspace "KPI Team"
```

Если модель есть в нескольких workspace — уточни workspace фразой пользователя или спроси один раз.

## Синонимы

| Фраза пользователя | Workspace (подсказка) | Модель |
|---|---|---|
| KPI, KPI marketing, лиды, свежие контакты, fresh contact, конверсия fresh contact | KPI Team | KPI marketing view (пробуй первым — самая полная модель по лидам/контактам из allowed) |
| посетители сайта, трафик, KPI marketing | KPI Team | KPI marketing view |
| KPI по медицине, врачи, приёмы (командный KPI) | KPI Team | KPI medicine view |
| KPI team, административный KPI, командный KPI | KPI Team | KPI team admin view |

Если фраза пользователя двусмысленна между `KPI medicine view` и `KPI team admin view`
(обе подходят под «командный KPI») — уточни один раз, какая модель имеется в виду, а не
гадай (пока обе не прогнаны через `discover-schema` и не описаны конкретные меры ниже).
