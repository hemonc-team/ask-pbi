# Реестр метрик (человекочитаемое зеркало)

Источник правды на рантайме — [`mcp_server/registry.py`](../mcp_server/registry.py).
Этот файл — то, что редактируют руками первым делом при добавлении/правке
метрики, и только потом переносят в `.py`. Не давать этому файлу разойтись с
кодом — при любом расхождении код (`registry.py`) главнее.

**Обновление 2026-08-19 (вечер):** `discover-schema` заработал (см.
`FOR_DEVELOPERS.md` → «Открытые проблемы»), реестр ниже переписан с трёх
подтверждённых через реальную схему метрик — старые записи «мера не
фильтруется по дате» были ошибкой методики проверки (фильтровали не через ту
таблицу дат), см. `known-fields.md` за 2026-08-19 вечер.

| metric_id | Датасеты | Мера (DAX) | Таблица дат | Гранулярность | Квартал/диапазон из >1 периода? |
|---|---|---|---|---|---|
| `fresh_contacts_count` | marketing / admin / medicine view | `[Количество свежих контактов]` | `date_dim_month[YearMonth]` | месяц | ✅ да, суммируется корректно |
| `fresh_contact_conversion_rate_pct` | marketing / admin / medicine view | `[Fresh_Contact_Conversion_Rate_%]` | `date_dim_month[YearMonth]` | месяц | ❌ нет — возвращает пусто, спрашивать месяц за месяцем |
| `contact_to_visit_conversion_pct` | marketing / admin / medicine view | `[Conversion_Primary_Booking_to_Visit_% 1c]` | `date_dim_daily[Date]` | день | предварительно да (не так тщательно перепроверено, как выше) |

| `site_visitors_count` | marketing view | `SUM(…[Посетители])` | `'Посетители сайта во времени✅📅'[Месяц визита]` | месяц (якорь 1-е) | ✅ SUM по месяцам |
| `site_pageviews_count` | marketing view | `SUM(…[Просмотры])` | та же | месяц (якорь 1-е) | ✅ |
| `content_leads_count` | marketing view | `SUM('Контент landing✅'[Лиды])` | `'Контент landing✅'[Месяц]` | месяц (якорь 1-е) | ✅ |
| `content_bookings_count` | marketing view | `[Записи]` | та же | месяц (якорь 1-е) | ✅ |
| `total_leads_count` | marketing view | `[Лиды, шт.]` | `date_dim_month[YearMonth]` | месяц | предварительно |

**Admin — записи / отмены (`KPI team admin view`, `date_dim_daily`, день):**

| metric_id | Мера | multi-period |
|---|---|---|
| `bookings_count` | `[П_Записи]` | ✅ |
| `attended_count` | `[П_Дошедшие]` | ✅ |
| `cancellations_count` | `[П_Отмены]` | ✅ |
| `cancellation_rate_pct` | `[П_Отмены %]` (доля 0–1) | ✅ |
| `primary_bookings_count` | `[П_Записи первичные]` | ✅ |
| `primary_attended_count` | `[П_Дошедшие первичные]` | ✅ |
| `primary_cancellations_count` | `[П_Отмены первичные]` | ✅ |
| `primary_cancellation_rate_pct` | `[П_Отмены первичные %]` | ✅ |

**Medicine (+ admin) — 1С:**

| metric_id | Мера | multi-period |
|---|---|---|
| `primary_bookings_1c` | `[Primary_Bookings 1c]` | ✅ (не путать с `П_Записи первичные`) |
| `true_canceled_count_1c` | `[True_Canceled_Count 1c]` | ❌ только месяц |
| `true_canceled_rate_pct_1c` | `[Percent_True_Canceled 1c]` (%*100) | ❌ только месяц |

**Admin — КЦ / онко-гемато:**

| metric_id | Мера | Дата |
|---|---|---|
| `incoming_calls_total` / `_success` / `_missed` / `_*_pct` | `[Входящие …]` | `telephony_call✅[CALL_START_TIME]` день |
| `oncology_bookings_count` | `[Записи к онкологам]` | date_dim_daily |
| `hematology_bookings_count` | `[Записи к гематологам]` | date_dim_daily |
| `oncology_hematology_bookings_count` | сумма онко+гемато | date_dim_daily |

**Marketing/medicine — сарафан:**

| metric_id | Мера |
|---|---|
| `sarafan_patients_count` / `non_sarafan_patients_count` | with/without сарафан (Акты) |

`All_Bookings 1c` / `Total_Consultations 1c` на проверенных месяцах = `Primary_Bookings 1c` — в каталог не дублируем.

**Обновление 2026-09-03:** у island-таблиц Метрики/`Контент landing` колонка дат
типа Date, но зерно физически месячное (`startOfMonth` / 1-е число). В реестре
было ошибочно `day` → частичные периоды («вчера», 24–30 авг) мимо якоря отдавали
пусто. Исправлено на `month`; сервер округляет период до календарных месяцев и
фильтрует через `DATE()` (не через строковый `YearMonth`). `multi_period_aggregatable`
остаётся `true` для SUM-метрик; `false` только у `%`-мер, которые на диапазоне
>1 месяца возвращают пусто (`fresh_contact_conversion_rate_pct`,
`true_canceled_*_1c`). Волна admin/medicine: `П_*` + ranking причин/врачей + 1c.

**Ranking** (`kind=ranking`, инструмент `get_breakdown`):

| metric_id | Категория | Значение | Дата |
|---|---|---|---|
| `top_content_landings_by_leads` | Landing URL | лиды + посетители + записи | Месяц (month) |
| `top_content_landings_by_visitors` | Landing URL | посетители + лиды | Месяц (month) |
| `top_entry_pages` | Страница входа | посетители | Месяц визита (month) |
| `top_popular_pages` | Адрес, ур. 3 | посетители | нет |
| `top_traffic_sources` | Источник трафика | посетители | нет (месяц текстовый) |
| `top_regions` / `top_cities` | Область / Город | посетители | Месяц визита (month) |
| `top_search_engines` | Поисковая система | посетители | Месяц визита (month) |
| `top_social_networks` | Cоциальная сеть | посетители | Месяц визита (month) |
| `top_direct_campaigns` | Кампания Директа | посетители | Месяц визита (month) |
| `top_lead_sources` | Лиды✅[Источник] | [Лиды, шт.] | нет |
| `top_cancellation_reasons` | ПричиныОтменыЗаписи[Наименование] | [П_Отмены] + share | день (admin) |
| `top_doctors_by_bookings` | Специалисты[НаименованиеПолное] | [П_Записи] + cancels/% | день (admin) |
| `top_doctors_by_cancellation_rate` | Специалисты[НаименованиеПолное] | [П_Отмены %] (min 50 записей) | день (admin) |
| `top_sarafan_agents` | Сарафан[Наименование] | пациенты с сарафаном | день |
| `top_doctors_by_sarafan_patients` | Специалисты[Наименование пользователей] | with+without сарафан | день |
| `top_visitors_by_gender` | демография[Пол] | посетители | месяц (якорь) |
| `top_direct_search_phrases` | Директ[Поисковая фраза] | посетители | месяц (якорь) |

**Волна 2 (2026-09-03):** КЦ (`incoming_calls_*`, дата = `CALL_START_TIME`), онко/гемато записи, сарафан (акты), пол демографии, фразы Директа. **CPC в модели нет.**

Не в реестре намеренно: Пациенты, ФИО, телефоны, таблицы 1С на уровне человека.

## Как добавить метрику — теперь через discover-schema

1. `~/ask-pbi/scripts/pbi_run.sh discover-schema --group <id> --dataset <id> --scope full --refresh-cache`
   — вернёт таблицы/меры/колонки/связи (кэш 7 дней в `~/.pbi/schema-cache/`).
2. Найди меру по имени, посмотри в `relationships`, через какую таблицу дат у
   неё реально активная связь (`[IsActive]: true`) — **не предполагай**, что
   это `Date_dim`, у разных таблиц фактов разные активные связи.
3. Подтверди живым `execute-dax` на 2+ разных периодах (не одном!), что мера
   реагирует на фильтр и не ломается на диапазоне из нескольких периодов
   (SUMMARIZECOLUMNS по нескольким группам подряд — если где-то пусто, это
   реальное ограничение меры, зафиксируй как `multi_period_aggregatable: false`).
4. Допиши находку в `known-fields.md`, обнови таблицу здесь, потом
   `Metric(...)` в `mcp_server/registry.py`.
5. Добавь сценарий в `mcp_server/smoke_test.py`, прогони
   `python3 -m mcp_server.smoke_test`.

## Что не проверено / дальше

- `contact_to_visit_conversion_pct` — не проверена на диапазоне из нескольких
  месяцев так же тщательно, как `fresh_contact_conversion_rate_pct` (у которой
  нашли реальный баг с квартальной агрегацией). Перепроверить перед тем как
  полагаться на квартальное сравнение для неё.
- В `KPI marketing view` — 66 именованных мер, в `KPI team admin view` — 163,
  в `KPI medicine view` — 67. Реестр специально узкий (только подтверждённое).
  Имена остальных Claude может увидеть через `list_model_measures`, но считать
  их нельзя, пока мера не прошла шаги выше и не попала в `registry.py`.
- `Contact_to_Visit_Conversion_% 1c` (без Primary_Booking) тоже существует на
  той же таблице `ОказаниеУслуг` — не добавлена в реестр, значения не совпали
  так же явно с примером пользователя, требует отдельной проверки прежде чем
  включать.
