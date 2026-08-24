"""Реестр подтверждённых бизнес-метрик Power BI (workspace KPI Team).

История: до 2026-08-19 `discover-schema` (INFO.TABLES/INFO.MEASURES) падал с
AnalysisServicesErrorCode 3239575574 — считалось, что аккаунту не хватает
Build permission. Маркетолог выдал Build permission на датасет, но КЛАССИЧЕСКИЕ
INFO.TABLES()/INFO.MEASURES() всё равно падают той же ошибкой — рабочая замена
оказалась INFO.VIEW.TABLES()/INFO.VIEW.MEASURES() (см.
scripts/pbi_service_client.py). С этого момента реестр строится на реальном
обнаружении схемы, а не на угадывании имён мер вручную.

Это открытие также ПЕРЕВОРАЧИВАЕТ более раннее (ошибочное) заключение, что
`[Количество свежих контактов]`/`Fresh_Contact_Conversion_Rate_%` не реагируют
на фильтр по дате — на самом деле они прекрасно фильтруются, просто через
ДРУГУЮ таблицу дат (`date_dim_month`, месячная гранулярность), а не через
`Date_dim` (с которой у таблицы `Лиды✅` нет активной связи вообще — поэтому
фильтр по `Date_dim` не делал ничего, а не потому что мера "снепшот").

Правило: не удалять и не скрывать сломанную/неподтверждённую метрику молча —
регистрировать её с честным `status`, а не тихо опускать.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    metric_id: str
    display_name: str
    description: str
    # "confirmed"  — работает, значение подтверждено живым execute-dax
    # "broken"     — мера существует в модели, но возвращает мусор/None
    # "unverified" — есть только по названию, ни разу не проверена execute-dax
    status: str
    datasets: tuple[str, ...]  # разрешённые имена датасетов (см. references/workspaces.md)
    measure_dax_name: str  # точное имя меры в DAX, например "[Количество свежих контактов]"
    date_aware: bool  # реагирует ли мера на фильтр по дате (подтверждено пробой)
    date_table: str | None  # колонка для фильтрации, напр. "date_dim_month[YearMonth]"
    date_granularity: str | None  # "month" | "day" | None — минимальный шаг фильтра
    multi_period_aggregatable: bool  # можно ли фильтровать диапазоном из >1 периода за раз
    supported_filters: tuple[str, ...] = ()  # подтверждённые разрезы; пусто = только total
    notes: str = ""
    confirmed_on: str = ""  # ISO-дата последней живой проверки
    # "scalar" — одно число; "ranking" — топ строк по категории (get_breakdown)
    kind: str = "scalar"
    category_column: str | None = None  # для ranking: 'Таблица'[Колонка]
    value_alias: str = "value"
    extra_values: tuple[tuple[str, str], ...] = ()  # (alias, DAX-выражение)


REGISTRY: list[Metric] = [
    Metric(
        metric_id="fresh_contacts_count",
        display_name="Свежие контакты (количество)",
        description=(
            "Количество свежих контактов. Без дат — общий итог за всё время; "
            "с датами — по месяцам/кварталам (гранулярность — календарный месяц)."
        ),
        status="confirmed",
        datasets=("KPI marketing view", "KPI team admin view", "KPI medicine view"),
        measure_dax_name="[Количество свежих контактов]",
        date_aware=True,
        date_table="date_dim_month[YearMonth]",
        date_granularity="month",
        multi_period_aggregatable=True,
        supported_filters=(),
        notes=(
            "Подтверждено живым тестом 2026-08-19 через SUMMARIZECOLUMNS(date_dim_month[YearMonth], ...): "
            "нормальные помесячные значения (напр. 2026-06=509, 2026-07=574 в KPI marketing view), "
            "и корректная сумма по кварталу (Q2 2026 = 1584 = 577+498+509 за апр/май/июн — совпадает "
            "точно). Более раннее заключение 'мера игнорирует дату' (было записано 2026-08-19 утром) "
            "было ошибкой методики: фильтровали по Date_dim, с которой у таблицы Лиды✅ нет активной "
            "связи. Правильная таблица дат — date_dim_month (только на уровне месяца, дневной таблицы "
            "для этой цепочки Лиды✅→crm_lead_uf✅→date_dim_month нет)."
        ),
        confirmed_on="2026-08-19",
    ),
    Metric(
        metric_id="fresh_contact_conversion_rate_pct",
        display_name="Fresh Contact Conversion Rate %",
        description=(
            "Конверсия свежих контактов, % — ТОЛЬКО на уровне одного календарного "
            "месяца за раз, не суммируется/усредняется по кварталу или диапазону месяцев."
        ),
        status="confirmed",
        datasets=("KPI marketing view", "KPI team admin view", "KPI medicine view"),
        measure_dax_name="[Fresh_Contact_Conversion_Rate_%]",
        date_aware=True,
        date_table="date_dim_month[YearMonth]",
        date_granularity="month",
        multi_period_aggregatable=False,
        supported_filters=(),
        notes=(
            "Подтверждено 2026-08-19: по одному месяцу возвращает разумные % (напр. 2026-06≈51.08, "
            "2026-07≈48.95 в KPI marketing view). НО при фильтре на диапазон из >1 месяца (квартал, "
            "SUMMARIZECOLUMNS с группировкой Year+Quarter, явный CALCULATE с Year=2026 && Quarter=\"Q2\") "
            "возвращает ПУСТО, а не число — похоже на HASONEVALUE-подобную логику внутри самой меры, "
            "рассчитанную на ровно один месяц в контексте фильтра. get_metric_value/analyze_trend "
            "обязаны требовать start_date и end_date в пределах одного календарного месяца для этой "
            "метрики и честно отказывать (reason=metric_single_month_only) на более широкий диапазон, "
            "а не молча суммировать/усреднять проценты вручную (это было бы статистически некорректно "
            "без знания числителя/знаменателя)."
        ),
        confirmed_on="2026-08-19",
    ),
    Metric(
        metric_id="contact_to_visit_conversion_pct",
        display_name="Conversion Primary Booking to Visit %",
        description=(
            "Конверсия первичной записи в состоявшийся приём, % — таблица ОказаниеУслуг, "
            "дневная гранулярность через date_dim_daily."
        ),
        status="confirmed",
        datasets=("KPI marketing view", "KPI team admin view", "KPI medicine view"),
        measure_dax_name="[Conversion_Primary_Booking_to_Visit_% 1c]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=True,
        supported_filters=(),
        notes=(
            "Подтверждено 2026-08-19 через SUMMARIZECOLUMNS(date_dim_daily[YearMonth], ...) — "
            "разумные % (65-82% диапазон за 2021-2026), связь ОказаниеУслуг[ДатаОказанияУслуг] -> "
            "date_dim_daily[Date] активна. В отличие от fresh_contact_conversion_rate_pct эта мера "
            "живёт на другой таблице (ОказаниеУслуг, не Лиды✅) и агрегируется по диапазону дат "
            "нормально (не проверено на многомесячных диапазонах так же тщательно, как quarter-тест "
            "у fresh_contact_conversion_rate_pct — считать multi_period_aggregatable предварительным, "
            "перепроверить перед тем как полагаться на квартальное сравнение)."
        ),
        confirmed_on="2026-08-19",
    ),
    Metric(
        metric_id="site_visitors_count",
        display_name="Посетители сайта",
        description="Количество посетителей сайта, по месяцам (таблица 'Посетители сайта во времени✅📅').",
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Посетители сайта во времени✅📅'[Посетители])",
        date_aware=True,
        date_table="'Посетители сайта во времени✅📅'[Месяц визита]",
        date_granularity="day",
        multi_period_aggregatable=True,
        supported_filters=(),
        notes=(
            "Подтверждено 2026-08-19: таблица без связей с остальной моделью (отдельный "
            "island-импорт, похоже на выгрузку Яндекс.Метрики), у неё своя дата "
            "'Месяц визита' прямо в этой же таблице (данные помесячные, но колонка типа Date — "
            "фильтр диапазоном дат работает штатно, CALCULATE на той же таблице). Не named-мера "
            "модели, а прямая агрегация SUM по колонке — собрано так намеренно, никакой named "
            "меры про посетителей в модели нет. Проверено live: 2026-07=21171, 2026-03=59962 — "
            "совпадает по форме с визуалом пользователя 'Посетители и Просмотры по Месяц визита'."
        ),
        confirmed_on="2026-08-19",
    ),
    Metric(
        metric_id="site_pageviews_count",
        display_name="Просмотры сайта",
        description="Количество просмотров страниц сайта, по месяцам (та же таблица, что и посетители).",
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Посетители сайта во времени✅📅'[Просмотры])",
        date_aware=True,
        date_table="'Посетители сайта во времени✅📅'[Месяц визита]",
        date_granularity="day",
        multi_period_aggregatable=True,
        supported_filters=(),
        notes="См. site_visitors_count — та же таблица, тот же принцип, колонка 'Просмотры'.",
        confirmed_on="2026-08-19",
    ),
    Metric(
        metric_id="content_leads_count",
        display_name="Лиды с посадочных (контент)",
        description=(
            "Сумма лидов из таблицы «Контент landing» (страница «Контент → лиды»). "
            "Без дат — за всё время; с датами — по колонке Месяц."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Контент landing✅'[Лиды])",
        date_aware=True,
        date_table="'Контент landing✅'[Месяц]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Сверено с визуалом 2026-08-19: итог 2451 лид при фильтре «Все».",
        confirmed_on="2026-08-19",
    ),
    Metric(
        metric_id="content_bookings_count",
        display_name="Записи с посадочных (контент)",
        description="Мера [Записи] таблицы «Контент landing» — записи на приём с лендингов.",
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[Записи]",
        date_aware=True,
        date_table="'Контент landing✅'[Месяц]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Сверено с визуалом 2026-08-19: итог 218 записей.",
        confirmed_on="2026-08-19",
    ),
    Metric(
        metric_id="total_leads_count",
        display_name="Все лиды CRM",
        description="Мера [Лиды, шт.] по таблице Лиды — все лиды Bitrix, не только свежие контакты.",
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[Лиды, шт.]",
        date_aware=True,
        date_table="date_dim_month[YearMonth]",
        date_granularity="month",
        multi_period_aggregatable=True,
        notes="Связь Лиды→месяц идёт через crm_lead_uf DATE_CREATE YearMonth.",
        confirmed_on="2026-08-19",
    ),
    Metric(
        metric_id="top_content_landings_by_leads",
        display_name="Топ посадочных по лидам",
        description=(
            "Страницы (Landing URL) с наибольшим числом лидов. Страница "
            "«Контент → лиды». Для топа вызывай get_breakdown, не get_metric_value."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Контент landing✅'[Лиды])",
        date_aware=True,
        date_table="'Контент landing✅'[Месяц]",
        date_granularity="day",
        multi_period_aggregatable=True,
        kind="ranking",
        category_column="'Контент landing✅'[Landing URL]",
        value_alias="leads",
        extra_values=(
            ("visitors", "SUM('Контент landing✅'[Посетители])"),
            ("bookings", "[Записи]"),
        ),
        notes="Сверено с визуалом: 1) дексаметазон 272 лида / 22 записи.",
        confirmed_on="2026-08-19",
    ),
    Metric(
        metric_id="top_content_landings_by_visitors",
        display_name="Топ посадочных по посетителям",
        description="Те же лендинги, сортировка по посетителям. get_breakdown.",
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Контент landing✅'[Посетители])",
        date_aware=True,
        date_table="'Контент landing✅'[Месяц]",
        date_granularity="day",
        multi_period_aggregatable=True,
        kind="ranking",
        category_column="'Контент landing✅'[Landing URL]",
        value_alias="visitors",
        extra_values=(("leads", "SUM('Контент landing✅'[Лиды])"),),
        confirmed_on="2026-08-19",
    ),
    Metric(
        metric_id="top_entry_pages",
        display_name="Топ страниц входа",
        description=(
            "Страницы входа сайта (полный URL) по посетителям. Визуал "
            "«Страница входа». get_breakdown."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Посещения сайта страницы входа✅📅'[Посетители])",
        date_aware=True,
        date_table="'Посещения сайта страницы входа✅📅'[Месяц визита]",
        date_granularity="day",
        multi_period_aggregatable=True,
        kind="ranking",
        category_column="'Посещения сайта страницы входа✅📅'[Страница входа]",
        value_alias="visitors",
        notes="Пустые и Not specified отбрасываются.",
        confirmed_on="2026-08-19",
    ),
    Metric(
        metric_id="top_popular_pages",
        display_name="Топ популярных страниц",
        description=(
            "Популярные адреса (ур. 3) по посетителям. В этой таблице нет даты — "
            "только снепшот за всё время."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Посещение сайта популярное✅📅'[Посетители])",
        date_aware=False,
        date_table=None,
        date_granularity=None,
        multi_period_aggregatable=False,
        kind="ranking",
        category_column="'Посещение сайта популярное✅📅'[Адрес, ур. 3]",
        value_alias="visitors",
        confirmed_on="2026-08-19",
    ),
    Metric(
        metric_id="top_traffic_sources",
        display_name="Топ источников трафика",
        description="Источник трафика (поиск, direct, реклама…) по посетителям. Без фильтра по дате — колонка месяца текстовая.",
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Посещение сайта источник сводка✅📅'[Посетители])",
        date_aware=False,
        date_table=None,
        date_granularity=None,
        multi_period_aggregatable=False,
        kind="ranking",
        category_column="'Посещение сайта источник сводка✅📅'[Источник трафика]",
        value_alias="visitors",
        confirmed_on="2026-08-19",
    ),
    Metric(
        metric_id="top_regions",
        display_name="Топ регионов по посетителям",
        description="Область (география Метрики) по посетителям. get_breakdown.",
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Посещения сайта география✅📅'[Посетители])",
        date_aware=True,
        date_table="'Посещения сайта география✅📅'[Месяц визита]",
        date_granularity="day",
        multi_period_aggregatable=True,
        kind="ranking",
        category_column="'Посещения сайта география✅📅'[Область]",
        value_alias="visitors",
        confirmed_on="2026-08-19",
    ),
    Metric(
        metric_id="top_cities",
        display_name="Топ городов по посетителям",
        description="Город (география Метрики) по посетителям. get_breakdown.",
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Посещения сайта география✅📅'[Посетители])",
        date_aware=True,
        date_table="'Посещения сайта география✅📅'[Месяц визита]",
        date_granularity="day",
        multi_period_aggregatable=True,
        kind="ranking",
        category_column="'Посещения сайта география✅📅'[Город]",
        value_alias="visitors",
        confirmed_on="2026-08-19",
    ),
    Metric(
        metric_id="top_search_engines",
        display_name="Топ поисковых систем",
        description="Переходы из поисковых систем по посетителям. get_breakdown.",
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Переходы на сайт из поисковых систем✅📅'[Посетители])",
        date_aware=True,
        date_table="'Переходы на сайт из поисковых систем✅📅'[Месяц визита]",
        date_granularity="day",
        multi_period_aggregatable=True,
        kind="ranking",
        category_column="'Переходы на сайт из поисковых систем✅📅'[Поисковая система]",
        value_alias="visitors",
        confirmed_on="2026-08-19",
    ),
    Metric(
        metric_id="top_social_networks",
        display_name="Топ соцсетей",
        description="Переходы из соцсетей по посетителям. get_breakdown.",
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Переходы на сайт из соцсетей✅📅'[Посетители])",
        date_aware=True,
        date_table="'Переходы на сайт из соцсетей✅📅'[Месяц визита]",
        date_granularity="day",
        multi_period_aggregatable=True,
        kind="ranking",
        category_column="'Переходы на сайт из соцсетей✅📅'[Cоциальная сеть]",
        value_alias="visitors",
        notes="В модели колонка с латинской C: Cоциальная сеть.",
        confirmed_on="2026-08-19",
    ),
    Metric(
        metric_id="top_direct_campaigns",
        display_name="Топ кампаний Яндекс.Директа",
        description="Кампании Директа по посетителям. get_breakdown.",
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Директ сводка✅📅'[Посетители])",
        date_aware=True,
        date_table="'Директ сводка✅📅'[Месяц визита]",
        date_granularity="day",
        multi_period_aggregatable=True,
        kind="ranking",
        category_column="'Директ сводка✅📅'[Кампания Яндекс.Директа]",
        value_alias="visitors",
        confirmed_on="2026-08-19",
    ),
    Metric(
        metric_id="top_lead_sources",
        display_name="Топ источников лидов CRM",
        description="Источник лида Bitrix (звонок, WhatsApp, сайт…) по мере [Лиды, шт.]. get_breakdown.",
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[Лиды, шт.]",
        date_aware=False,
        date_table=None,
        date_granularity=None,
        multi_period_aggregatable=False,
        kind="ranking",
        category_column="'Лиды✅'[Источник]",
        value_alias="leads",
        notes="Не путать со свежими контактами. Дата через YearMonth в TOPN пока не подключена — только всё время.",
        confirmed_on="2026-08-19",
    ),
]


def get_registry() -> list[Metric]:
    """Копия текущего реестра (список объектов Metric)."""
    return list(REGISTRY)


def find_metric(metric_id: str) -> Metric | None:
    return next((m for m in REGISTRY if m.metric_id == metric_id), None)
