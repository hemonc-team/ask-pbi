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
    # доп. FILTER в TOPN (напр. "[П_Записи] >= 50") — только ranking
    breakdown_row_filter: str | None = None


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
        date_granularity="month",
        multi_period_aggregatable=True,
        supported_filters=(),
        notes=(
            "Подтверждено 2026-08-19: таблица без связей с остальной моделью (отдельный "
            "island-импорт Метрики). Колонка 'Месяц визита' типа Date, но зерно "
            "физически месячное: одна строка на месяц с якорем на 1-е число "
            "(ym:s:startOfMonth / dwh.metrika_monthly_totals). Не named-мера, а "
            "SUM по колонке. date_granularity=month (исправлено 2026-09-03: раньше "
            "стояло day — «вчера»/частичный диапазон мимо 1-го числа отдавали пусто). "
            "SUM по нескольким месяцам корректен. Live: 2026-07=21171, 2026-03=59962."
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
        date_granularity="month",
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
            "Без дат — за всё время; с датами — по колонке Месяц (календарный месяц)."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Контент landing✅'[Лиды])",
        date_aware=True,
        date_table="'Контент landing✅'[Месяц]",
        date_granularity="month",
        multi_period_aggregatable=True,
        notes=(
            "Сверено с визуалом 2026-08-19: итог 2451 лид при фильтре «Все». "
            "Колонка Месяц — month-start Date (dwh.content_landing_monthly)."
        ),
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
        date_granularity="month",
        multi_period_aggregatable=True,
        notes="Сверено с визуалом 2026-08-19: итог 218 записей. Та же month-grain колонка Месяц.",
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
        date_granularity="month",
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
        date_granularity="month",
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
        date_granularity="month",
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
        date_granularity="month",
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
        date_granularity="month",
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
        date_granularity="month",
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
        date_granularity="month",
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
        date_granularity="month",
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
    # --- KPI team admin view: записи / дошедшие / отмены (П_*) ---
    Metric(
        metric_id="bookings_count",
        display_name="Записи на приём (шт)",
        description="Количество записей на приём (мера [П_Записи], admin KPI).",
        status="confirmed",
        datasets=("KPI team admin view",),
        measure_dax_name="[П_Записи]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes=(
            "Live 2026-09-03: март 2026=804 (совпадает с визуалом admin). "
            "Связь ОказаниеУслуг[ДатаОказанияУслуг]→date_dim_daily. Только admin."
        ),
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="attended_count",
        display_name="Дошедшие на приём (шт)",
        description="Количество состоявшихся приёмов / дошедших (мера [П_Дошедшие]).",
        status="confirmed",
        datasets=("KPI team admin view",),
        measure_dax_name="[П_Дошедшие]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Live 2026-09-03: март 2026=653 — как на визуале «Записи на приём и отмены».",
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="cancellations_count",
        display_name="Отмены записей (шт)",
        description="Количество отменённых записей (мера [П_Отмены]).",
        status="confirmed",
        datasets=("KPI team admin view",),
        measure_dax_name="[П_Отмены]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Live 2026-09-03: март 2026=151; Q1 2026=397 (сумма месяцев ок).",
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="cancellation_rate_pct",
        display_name="Доля отмен записей (%)",
        description="Доля отмен от записей, доля 0–1 (мера [П_Отмены %]). Умножай на 100 для процентов.",
        status="confirmed",
        datasets=("KPI team admin view",),
        measure_dax_name="[П_Отмены %]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes=(
            "Live 2026-09-03: март≈0.1878 (18.8% как на визуале), Q1≈0.1797 — "
            "агрегируется по диапазону (не как Fresh_Contact_Conversion). Значение — доля, не %*100."
        ),
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="primary_bookings_count",
        display_name="Первичные записи (шт)",
        description="Первичные записи на приём (мера [П_Записи первичные]).",
        status="confirmed",
        datasets=("KPI team admin view",),
        measure_dax_name="[П_Записи первичные]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Live 2026-09-03: март 2026=335. Не путать с [Primary_Bookings 1c] (другая семантика/масштаб).",
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="primary_attended_count",
        display_name="Первичные дошедшие (шт)",
        description="Первичные дошедшие на приём (мера [П_Дошедшие первичные]).",
        status="confirmed",
        datasets=("KPI team admin view",),
        measure_dax_name="[П_Дошедшие первичные]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Live 2026-09-03: март 2026=243.",
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="primary_cancellations_count",
        display_name="Первичные отмены (шт)",
        description="Отмены первичных записей (мера [П_Отмены первичные]).",
        status="confirmed",
        datasets=("KPI team admin view",),
        measure_dax_name="[П_Отмены первичные]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Live 2026-09-03: март 2026=92.",
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="primary_cancellation_rate_pct",
        display_name="Доля отмен первичных (%)",
        description="Доля отмен среди первичных записей, 0–1 (мера [П_Отмены первичные %]).",
        status="confirmed",
        datasets=("KPI team admin view",),
        measure_dax_name="[П_Отмены первичные %]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Live 2026-09-03: март≈0.275; Q1≈0.229 — диапазон ок. Доля, не %*100.",
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="top_cancellation_reasons",
        display_name="Топ причин отмены",
        description="Рейтинг причин отмены записи по числу отмен. get_breakdown.",
        status="confirmed",
        datasets=("KPI team admin view",),
        measure_dax_name="[П_Отмены]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=True,
        kind="ranking",
        category_column="'ПричиныОтменыЗаписи'[Наименование]",
        value_alias="cancels",
        extra_values=(("share", "[П_Отмены доля причины %]"),),
        notes=(
            "Live 2026-09-03: all-time топ — «Отмена…пациента» 996, «Ошибка ввода» 840. "
            "Пустые причины (доминируют на визуале как «(Пусто)») отфильтровываются TOPN-шаблоном. "
            "share — доля 0–1."
        ),
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="top_doctors_by_bookings",
        display_name="Топ врачей по записям",
        description="Специалисты по числу записей; в ответе также отмены и доля отмен. get_breakdown.",
        status="confirmed",
        datasets=("KPI team admin view",),
        measure_dax_name="[П_Записи]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=True,
        kind="ranking",
        category_column="'Специалисты'[НаименованиеПолное]",
        value_alias="bookings",
        extra_values=(
            ("cancels", "[П_Отмены]"),
            ("cancel_pct", "[П_Отмены %]"),
        ),
        notes=(
            "Live 2026-09-03 март: Борисов ~129 / Аболмасов ~104 / Серебрийский ~101. "
            "Категория — ФИО специалиста (не пациент). cancel_pct — доля 0–1."
        ),
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="top_doctors_by_cancellation_rate",
        display_name="Топ врачей по доле отмен",
        description="Специалисты с наибольшей долей отмен (мин. 50 записей). get_breakdown.",
        status="confirmed",
        datasets=("KPI team admin view",),
        measure_dax_name="[П_Отмены %]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=True,
        kind="ranking",
        category_column="'Специалисты'[НаименованиеПолное]",
        value_alias="cancel_pct",
        extra_values=(
            ("bookings", "[П_Записи]"),
            ("cancels", "[П_Отмены]"),
        ),
        breakdown_row_filter="[П_Записи] >= 50",
        notes=(
            "Без порога объёма топ забивают 100% при 1 записи — FILTER [П_Записи]>=50. "
            "Live all-time: Фролова ~33%, Багова ~32%."
        ),
        confirmed_on="2026-09-03",
    ),
    # --- medicine (+ admin): записи/отмены 1С ---
    Metric(
        metric_id="primary_bookings_1c",
        display_name="Записи Primary_Bookings 1c",
        description=(
            "Мера [Primary_Bookings 1c] по ОказаниеУслуг. На проверенных месяцах "
            "совпадает с [All_Bookings 1c]/[Total_Consultations 1c] — не путать с "
            "admin [П_Записи первичные]."
        ),
        status="confirmed",
        datasets=("KPI medicine view", "KPI team admin view"),
        measure_dax_name="[Primary_Bookings 1c]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes=(
            "Live 2026-09-03 medicine: июнь=729, июль=833, Q2=2325. "
            "All_Bookings/Total_Consultations на тех же месяцах дали то же число — "
            "в каталог не дублируем. На marketing view меры нет."
        ),
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="true_canceled_count_1c",
        display_name="Истинно отменённые (1c)",
        description="Мера [True_Canceled_Count 1c] — только один календарный месяц за раз.",
        status="confirmed",
        datasets=("KPI medicine view", "KPI team admin view"),
        measure_dax_name="[True_Canceled_Count 1c]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=False,
        notes=(
            "Live 2026-09-03: июнь medicine=89, июль=106, март admin=117; "
            "Q1/Q2 и снепшот → пусто. Как fresh_contact_conversion — только месяц."
        ),
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="true_canceled_rate_pct_1c",
        display_name="Доля истинно отменённых % (1c)",
        description=(
            "Мера [Percent_True_Canceled 1c] — процент (уже *100, напр. 12.2), "
            "только один календарный месяц."
        ),
        status="confirmed",
        datasets=("KPI medicine view", "KPI team admin view"),
        measure_dax_name="[Percent_True_Canceled 1c]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=False,
        notes=(
            "Live 2026-09-03 medicine июнь≈12.21, июль≈12.73; Q2 пусто. "
            "Шкала %*100 (не доля 0–1 как [П_Отмены %])."
        ),
        confirmed_on="2026-09-03",
    ),
    # --- волна 2: КЦ, онко/гемато, сарафан, демография/фразы Директ ---
    Metric(
        metric_id="incoming_calls_total",
        display_name="Входящие звонки всего",
        description="Все входящие звонки КЦ (мера [Входящие всего], admin).",
        status="confirmed",
        datasets=("KPI team admin view",),
        measure_dax_name="[Входящие всего]",
        date_aware=True,
        date_table="'telephony_call✅'[CALL_START_TIME]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes=(
            "Live 2026-09-03: фильтр только через CALL_START_TIME (date_dim_daily "
            "не режет — нет активной связи). Янв≈1041 ок+miss, фев≈1266."
        ),
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="incoming_calls_success",
        display_name="Входящие успешные",
        description="Успешные входящие звонки КЦ ([Входящие успешные]).",
        status="confirmed",
        datasets=("KPI team admin view",),
        measure_dax_name="[Входящие успешные]",
        date_aware=True,
        date_table="'telephony_call✅'[CALL_START_TIME]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Live: янв 2026=595, фев=730 (визуал КЦ ~589/~714 — близко).",
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="incoming_calls_missed",
        display_name="Входящие пропущенные",
        description="Пропущенные входящие звонки КЦ ([Входящие пропущенные]).",
        status="confirmed",
        datasets=("KPI team admin view",),
        measure_dax_name="[Входящие пропущенные]",
        date_aware=True,
        date_table="'telephony_call✅'[CALL_START_TIME]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Live: янв=446, фев=536. Визуал может чуть отличаться из-за срезов статуса.",
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="incoming_calls_success_pct",
        display_name="Доля успешных входящих",
        description="Доля успешных входящих, 0–1 ([Входящие успешные %]).",
        status="confirmed",
        datasets=("KPI team admin view",),
        measure_dax_name="[Входящие успешные %]",
        date_aware=True,
        date_table="'telephony_call✅'[CALL_START_TIME]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Доля 0–1. Дата только через CALL_START_TIME.",
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="incoming_calls_missed_pct",
        display_name="Доля пропущенных входящих",
        description="Доля пропущенных входящих, 0–1 ([Входящие пропущенные %]).",
        status="confirmed",
        datasets=("KPI team admin view",),
        measure_dax_name="[Входящие пропущенные %]",
        date_aware=True,
        date_table="'telephony_call✅'[CALL_START_TIME]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Доля 0–1.",
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="oncology_bookings_count",
        display_name="Записи к онкологам",
        description="Записи к онкологам ([Записи к онкологам], admin).",
        status="confirmed",
        datasets=("KPI team admin view",),
        measure_dax_name="[Записи к онкологам]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Live 2026-09-03: март=324, Q1=956.",
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="hematology_bookings_count",
        display_name="Записи к гематологам",
        description="Записи к гематологам ([Записи к гематологам], admin).",
        status="confirmed",
        datasets=("KPI team admin view",),
        measure_dax_name="[Записи к гематологам]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Live 2026-09-03: март=101, Q1=242.",
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="oncology_hematology_bookings_count",
        display_name="Записи к онкологам и гематологам",
        description="Суммарные записи к онкологам и гематологам.",
        status="confirmed",
        datasets=("KPI team admin view",),
        measure_dax_name="[Записи к онкологам и гематологам]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Live март 2026=425 (=324+101).",
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="sarafan_patients_count",
        display_name="Уникальные пациенты с сарафаном",
        description="Уникальные пациенты с сарафаном по актам.",
        status="confirmed",
        datasets=("KPI marketing view", "KPI medicine view"),
        measure_dax_name="[Уникальные пациенты с сарафаном (Акты)]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Live marketing: июнь=140, июль=154, Q2=346. Мера «Уникальные пациенты Сарафан (Акты)» без with/without — пусто, не регистрируем.",
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="non_sarafan_patients_count",
        display_name="Уникальные пациенты без сарафана",
        description="Уникальные пациенты без сарафана по актам.",
        status="confirmed",
        datasets=("KPI marketing view", "KPI medicine view"),
        measure_dax_name="[Уникальные пациенты без сарафана (Акты)]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Live marketing: июнь=329, июль=343, Q2=842.",
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="top_sarafan_agents",
        display_name="Топ агентов сарафана",
        description="Агенты/каналы сарафана по уникальным пациентам с сарафаном. get_breakdown.",
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[Уникальные пациенты с сарафаном (Акты)]",
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=True,
        kind="ranking",
        category_column="'Сарафан'[Наименование]",
        value_alias="patients",
        notes="Live all-time: Коллега группа 796, Другой наш пациент 725, Неизвестный сарафан 535…",
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="top_doctors_by_sarafan_patients",
        display_name="Топ врачей по пациентам сарафана",
        description="Врачи: уникальные пациенты с/без сарафана (акты). get_breakdown.",
        status="confirmed",
        datasets=("KPI marketing view", "KPI medicine view"),
        measure_dax_name=(
            "[Уникальные пациенты с сарафаном по врачу (Акты)] "
            "+ [Уникальные пациенты без сарафана по врачу (Акты)]"
        ),
        date_aware=True,
        date_table="date_dim_daily[Date]",
        date_granularity="day",
        multi_period_aggregatable=True,
        kind="ranking",
        category_column="'Специалисты'[Наименование пользователей]",
        value_alias="patients",
        extra_values=(
            ("with_sarafan", "[Уникальные пациенты с сарафаном по врачу (Акты)]"),
            ("without_sarafan", "[Уникальные пациенты без сарафана по врачу (Акты)]"),
        ),
        notes="Категория как на визуале (краткое ФИО). Сортировка по сумме with+without.",
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="top_visitors_by_gender",
        display_name="Посетители по полу",
        description="Пол посетителей сайта (таблица демографии Метрики). get_breakdown.",
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Посещения сайта демография✅📅'[Посетители])",
        date_aware=True,
        date_table="'Посещения сайта демография✅📅'[Месяц визита]",
        date_granularity="month",
        multi_period_aggregatable=True,
        kind="ranking",
        category_column="'Посещения сайта демография✅📅'[Пол]",
        value_alias="visitors",
        notes=(
            "Month-start Date. Не Директ CPC — в модели Директ сводка нет колонки CPC/пол; "
            "пол в демографии сайта. «Не определено» отфильтровывается TOPN."
        ),
        confirmed_on="2026-09-03",
    ),
    Metric(
        metric_id="top_direct_search_phrases",
        display_name="Топ поисковых фраз Директа",
        description="Поисковые фразы Директа по посетителям. get_breakdown.",
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Директ сводка✅📅'[Посетители])",
        date_aware=True,
        date_table="'Директ сводка✅📅'[Месяц визита]",
        date_granularity="month",
        multi_period_aggregatable=True,
        kind="ranking",
        category_column="'Директ сводка✅📅'[Поисковая фраза (Директ)]",
        value_alias="visitors",
        notes=(
            "Month-start. CPC в семантической модели нет — только посетители/визиты. "
            "«Не определено» отфильтровывается. Live Q1 2026: клиника ласкова 131…"
        ),
        confirmed_on="2026-09-03",
    ),
]


def get_registry() -> list[Metric]:
    """Копия текущего реестра (список объектов Metric)."""
    return list(REGISTRY)


def find_metric(metric_id: str) -> Metric | None:
    return next((m for m in REGISTRY if m.metric_id == metric_id), None)
