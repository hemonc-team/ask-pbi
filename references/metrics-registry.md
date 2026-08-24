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

| `site_visitors_count` | marketing view | `SUM(…[Посетители])` | `'Посетители сайта во времени✅📅'[Месяц визита]` | день | ✅ |
| `site_pageviews_count` | marketing view | `SUM(…[Просмотры])` | та же | день | ✅ |
| `content_leads_count` | marketing view | `SUM('Контент landing✅'[Лиды])` | `'Контент landing✅'[Месяц]` | день | ✅ |
| `content_bookings_count` | marketing view | `[Записи]` | та же | день | ✅ |
| `total_leads_count` | marketing view | `[Лиды, шт.]` | `date_dim_month[YearMonth]` | месяц | предварительно |

**Ranking** (`kind=ranking`, инструмент `get_breakdown`):

| metric_id | Категория | Значение | Дата |
|---|---|---|---|
| `top_content_landings_by_leads` | Landing URL | лиды + посетители + записи | Месяц |
| `top_content_landings_by_visitors` | Landing URL | посетители + лиды | Месяц |
| `top_entry_pages` | Страница входа | посетители | Месяц визита |
| `top_popular_pages` | Адрес, ур. 3 | посетители | нет |
| `top_traffic_sources` | Источник трафика | посетители | нет (месяц текстовый) |
| `top_regions` / `top_cities` | Область / Город | посетители | Месяц визита |
| `top_search_engines` | Поисковая система | посетители | Месяц визита |
| `top_social_networks` | Cоциальная сеть | посетители | Месяц визита |
| `top_direct_campaigns` | Кампания Директа | посетители | Месяц визита |
| `top_lead_sources` | Лиды✅[Источник] | [Лиды, шт.] | нет |

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
- В `KPI marketing view` — 66 мер всего, разобраны только 3. В `KPI team admin
  view` — 163 меры, в `KPI medicine view` — 67. Остальные не тронуты, реестр
  специально узкий (только реально подтверждённое, честно, а не «весь каталог»).
- `Contact_to_Visit_Conversion_% 1c` (без Primary_Booking) тоже существует на
  той же таблице `ОказаниеУслуг` — не добавлена в реестр, значения не совпали
  так же явно с примером пользователя, требует отдельной проверки прежде чем
  включать.
