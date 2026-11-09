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


# «Рост контактов»: общие определения для описаний метрик (их читает LLM маркетолога).
_GROWTH_MONTH = "'Рост месяц✅'[Месяц (рост)]"
_GROWTH_COHORT_COL = "'Рост когорты✅'[Когорта публикации]"
_GROWTH_TERMS = (
    "Страница PBI «Рост контактов» (проект: статьи под ситуацию пациента или близкого "
    "должны приводить новых людей минимум на 50% лучше обычных статей фабрики). "
    "Новый контакт — первое обращение человека в клинику с 2024 года (целевой звонок, "
    "заявка «Перезвоните мне» или запись через сайт). Вход — страница, с которой начался "
    "визит на сайт, в котором человек обратился. Проект — статьи полки «рост-контактов»; "
    "контроль — обычные статьи фабрики; легаси — старые статьи сайта вне фабрики; "
    "прочее — главная, врачи, услуги. Данные с 29.06.2026."
)
_GROWTH_REF = "Рост контактов (термины: вход, проект, контроль — в growth_new_contacts)."
_GROWTH_COHORT = (
    "Метрика по когортам: start_date/end_date — месяц ПУБЛИКАЦИИ статей (когорта), "
    "а не месяц обращения. Проект и контроль сравниваются на статьях одного возраста."
)

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
    # --- KPI marketing view: региональная воронка Директа (island) ---
    Metric(
        metric_id="regional_clicks_count",
        display_name="Клики региональной воронки Директа",
        description=(
            "Клики Яндекс.Директа из витрины «Региональная воронка» "
            "(область × кампания × день). Не топ посетителей Метрики."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Региональная воронка✅'[Клики])",
        date_aware=True,
        date_table="'Региональная воронка✅'[Дата]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes=(
            "Island dwh.marketing_regional_funnel_daily. Live 2026-10-30: "
            "все время=14378 (в опубликованной модели пока пилот 705957657). "
            "Окно #24396 20.07–10.08.2026=1495. Не city Calltouch и не top_regions."
        ),
        confirmed_on="2026-10-30",
    ),
    Metric(
        metric_id="regional_visits_count",
        display_name="Визиты региональной воронки",
        description="Визиты Метрики в срезе региональной воронки Директа (гео визита).",
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Региональная воронка✅'[Визиты])",
        date_aware=True,
        date_table="'Региональная воронка✅'[Дата]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Live 2026-10-30 snapshot=2564 (пилот 705957657).",
        confirmed_on="2026-10-30",
    ),
    Metric(
        metric_id="regional_calls_count",
        display_name="Звонки региональной воронки",
        description=(
            "Обращения Calltouch после атрибуции DWH в региональной воронке. "
            "Не city Calltouch."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Региональная воронка✅'[Звонки])",
        date_aware=True,
        date_table="'Региональная воронка✅'[Дата]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Live 2026-10-30 snapshot=420. «Звонки high» — отдельная колонка.",
        confirmed_on="2026-10-30",
    ),
    Metric(
        metric_id="regional_leads_count",
        display_name="Лиды CRM региональной воронки",
        description="Лиды Bitrix, привязанные DWH к области и кампании Директа.",
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Региональная воронка✅'[Лиды CRM])",
        date_aware=True,
        date_table="'Региональная воронка✅'[Дата]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Live 2026-10-30 snapshot=262. Не Лиды✅[Область] — то поле пустое.",
        confirmed_on="2026-10-30",
    ),
    Metric(
        metric_id="regional_bookings_count",
        display_name="Записи региональной воронки",
        description="Записи 1С (e1cib) в региональной воронке Директа.",
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Региональная воронка✅'[Записи])",
        date_aware=True,
        date_table="'Региональная воронка✅'[Дата]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Live 2026-10-30 snapshot=107. Не content_bookings_count (лендинги).",
        confirmed_on="2026-10-30",
    ),
    Metric(
        metric_id="regional_cost_rub",
        display_name="Расход Директа региональной воронки, ₽",
        description="Расход Яндекс.Директа (руб.) в срезе области × кампании.",
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Региональная воронка✅'[Расход])",
        date_aware=True,
        date_table="'Региональная воронка✅'[Дата]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes="Live 2026-10-30 snapshot≈536139. CPC как отдельной меры в модели нет.",
        confirmed_on="2026-10-30",
    ),
    Metric(
        metric_id="regional_cr_calls_high_pct",
        display_name="CR звонки high региональной воронки",
        description=(
            "Доля 0–1: звонки high / визиты в текущем срезе. "
            "Не использовать при малом числе обращений (n<5)."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[CR звонки high]",
        date_aware=True,
        date_table="'Региональная воронка✅'[Дата]",
        date_granularity="day",
        multi_period_aggregatable=True,
        notes=(
            "DIVIDE(SUM звонки high, SUM визиты). Live snapshot≈0.0335. "
            "Не путать с top_regions (посетители Метрики)."
        ),
        confirmed_on="2026-10-30",
    ),
    Metric(
        metric_id="top_regional_oblasts_by_clicks",
        display_name="Топ областей региональной воронки",
        description=(
            "Области Директа (канон витрины) по кликам, с визитами/звонками/"
            "лидами/записями. get_breakdown. Не география сайта Метрики."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Региональная воронка✅'[Клики])",
        date_aware=True,
        date_table="'Региональная воронка✅'[Дата]",
        date_granularity="day",
        multi_period_aggregatable=True,
        kind="ranking",
        category_column="'Региональная воронка✅'[Область]",
        value_alias="clicks",
        extra_values=(
            ("visits", "SUM('Региональная воронка✅'[Визиты])"),
            ("calls", "SUM('Региональная воронка✅'[Звонки])"),
            ("calls_high", "SUM('Региональная воронка✅'[Звонки high])"),
            ("leads", "SUM('Региональная воронка✅'[Лиды CRM])"),
            ("bookings", "SUM('Региональная воронка✅'[Записи])"),
            ("cost", "SUM('Региональная воронка✅'[Расход])"),
        ),
        notes=(
            "Live 2026-10-30: Москва И 11475 кликов / 203 лида; unknown — бакет "
            "атрибуции, не пусто. Не city Calltouch. «Москва И» — имя из dim."
        ),
        confirmed_on="2026-10-30",
    ),
    Metric(
        metric_id="top_regional_campaigns_by_clicks",
        display_name="Топ региональных кампаний Директа",
        description=(
            "Кампании Директа из региональной воронки по кликам, с визитами/"
            "звонками/лидами/записями. get_breakdown. Не top_direct_campaigns "
            "(посетители Метрики)."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="SUM('Региональная воронка✅'[Клики])",
        date_aware=True,
        date_table="'Региональная воронка✅'[Дата]",
        date_granularity="day",
        multi_period_aggregatable=True,
        kind="ranking",
        category_column="'Региональная воронка✅'[Кампания]",
        value_alias="clicks",
        extra_values=(
            ("visits", "SUM('Региональная воронка✅'[Визиты])"),
            ("calls", "SUM('Региональная воронка✅'[Звонки])"),
            ("calls_high", "SUM('Региональная воронка✅'[Звонки high])"),
            ("leads", "SUM('Региональная воронка✅'[Лиды CRM])"),
            ("bookings", "SUM('Региональная воронка✅'[Записи])"),
            ("cost", "SUM('Региональная воронка✅'[Расход])"),
        ),
        notes=(
            "Live 2026-10-30 в Service: одна кампания 705957657 (M-фильтр пилота). "
            "В DWH 42 кампании; после Replace M без фильтра топ станет полным. "
            "ID кампании — текст, как в Директе."
        ),
        confirmed_on="2026-10-30",
    ),
    # --- KPI marketing view: статистика соцсетей (#26158) ---
    # Источник: «Соцсети по месяцам✅» = dwh.smm_monthly (лист «По месяцам» Google-таблицы
    # соцсетей). Меры — вкладка «Соцсети» (pbi expressions/Соцсети_меры.dax). Зерно — месяц.
    # Одна сеть / сравнение сетей — smm_by_network (get_breakdown): фильтра по сети у
    # get_metric_value нет. Сравнение двух периодов по одной сети — два вызова get_breakdown.
    Metric(
        metric_id="smm_followers",
        display_name="Подписчики соцсетей (все 4 сети)",
        description=(
            "Подписчики ВКонтакте + Facebook + Instagram + Telegram на КОНЕЦ периода "
            "(значение за последний месяц периода, не сумма по месяцам). Одна сеть — "
            "get_breakdown('smm_by_network'). Без дат — на последний собранный месяц."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[Соцсети подписчики]",
        date_aware=True,
        date_table="date_dim_month[YearMonth]",
        date_granularity="month",
        multi_period_aggregatable=True,
        notes=(
            "Остаток на дату: в analyze_trend смотри delta_absolute, среднедневное "
            "(normalized) для подписчиков бессмысленно. Live 2026-11-07: Q3 2026 = 17878, "
            "2025 = 16758 (на конец декабря). Текущий месяц неполный (данные на дату сбора)."
        ),
        confirmed_on="2026-11-07",
    ),
    Metric(
        metric_id="smm_followers_growth",
        display_name="Прирост подписчиков соцсетей (все 4 сети)",
        description=(
            "Прирост подписчиков за период: подписчики на конец периода минус на конец "
            "месяца перед периодом (бывает минус — отписки). Обязательно с датами: без "
            "дат пусто. Одна сеть — get_breakdown('smm_by_network'), поле growth."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[Соцсети прирост подписчиков]",
        date_aware=True,
        date_table="date_dim_month[YearMonth]",
        date_granularity="month",
        multi_period_aggregatable=True,
        notes=(
            "Считается разницей подписчиков, не строкой «Прирост» Google-таблицы (та за "
            "10–11.2026 неверна — ошибка сборщика). Ноябрь 2025: Instagram +1734 — вирусный "
            "пост, не ошибка. Live 2026-11-07: Q3 2026 = +10, 2025 = +4125."
        ),
        confirmed_on="2026-11-07",
    ),
    Metric(
        metric_id="smm_posts",
        display_name="Посты в соцсетях (все 4 сети)",
        description="Сумма постов за период по 4 сетям. Одна сеть — get_breakdown('smm_by_network'), поле posts.",
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[Соцсети посты]",
        date_aware=True,
        date_table="date_dim_month[YearMonth]",
        date_granularity="month",
        multi_period_aggregatable=True,
        notes="Live 2026-11-07: Q3 2026 = 124, 2025 = 616, октябрь 2026 = 37.",
        confirmed_on="2026-11-07",
    ),
    Metric(
        metric_id="smm_reach",
        display_name="Охват публикаций в соцсетях (все 4 сети)",
        description=(
            "Сумма помесячного охвата публикаций за период. У Telegram охвата нет — это "
            "просмотры. Охват ВКонтакте с октября 2026 не собирается (0). Одна сеть — "
            "get_breakdown('smm_by_network'), поле reach."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[Соцсети охват]",
        date_aware=True,
        date_table="date_dim_month[YearMonth]",
        date_granularity="month",
        multi_period_aggregatable=True,
        notes=(
            "Сумма по месяцам: один человек может быть посчитан в нескольких месяцах. "
            "Ноябрь 2025 — Instagram 387562 (вирусный пост). Live 2026-11-07: Q3 2026 = 110564, "
            "2025 = 1183748."
        ),
        confirmed_on="2026-11-07",
    ),
    Metric(
        metric_id="smm_reactions",
        display_name="Реакции в соцсетях",
        description=(
            "Лайки + комментарии + репосты + сохранения за период. Реакции ВКонтакте не "
            "собираются; у Facebook и Telegram нет данных за март 2025 — сентябрь 2026 — "
            "сравнивать годы нельзя, предупреди. Одна сеть — get_breakdown('smm_by_network')."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[Соцсети реакции]",
        date_aware=True,
        date_table="date_dim_month[YearMonth]",
        date_granularity="month",
        multi_period_aggregatable=True,
        notes="Live 2026-11-07: Q3 2026 = 854 (только Instagram), 2025 = 30446.",
        confirmed_on="2026-11-07",
    ),
    Metric(
        metric_id="smm_by_network",
        display_name="Соцсети по сетям: подписчики, прирост, посты, охват, реакции",
        description=(
            "Строка на каждую сеть (ВКонтакте, Facebook, Instagram, Telegram): followers "
            "(на конец периода), growth (прирост за период), posts, reach, reactions. "
            "get_breakdown. Вопрос про одну сеть — бери её строку. Сравнение периодов "
            "(«лето против весны») — два вызова get_breakdown, по одному на период, и "
            "разница growth/posts/… Прирост без дат пуст — всегда задавай период."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[Соцсети подписчики]",
        date_aware=True,
        date_table="date_dim_month[MonthStartDate]",
        date_granularity="month",
        multi_period_aggregatable=True,
        kind="ranking",
        category_column="'Соцсети по месяцам✅'[Сеть]",
        value_alias="followers",
        extra_values=(
            ("growth", "[Соцсети прирост подписчиков]"),
            ("posts", "[Соцсети посты]"),
            ("reach", "[Соцсети охват]"),
            ("reactions", "[Соцсети реакции]"),
        ),
        notes=(
            "Дата для топа — MonthStartDate (date), не YearMonth: get_breakdown с YearMonth "
            "отказывает. Live 2026-11-07: прирост весна 2026 (мар–май) Instagram +97, "
            "Telegram +57, Facebook +49, ВКонтакте −48; лето 2026 (июн–авг) ВКонтакте +30, "
            "Facebook −1, Instagram −2, Telegram −7. Охват ВК с 10.2026 = 0, реакций ВК нет."
        ),
        confirmed_on="2026-11-07",
    ),
    # --- «Рост контактов» (Фабрика роста новых контактов), KPI marketing view ---
    # Страница PBI «Рост контактов»; данные считает DWH (dwh.v_growth_*), с 29.06.2026.
    # Месячные метрики — дата через справочник 'Рост месяц✅'[Месяц (рост)]
    # (Date, 1-е число месяца обращения). Когортные — через 'Рост когорты✅'
    # [Когорта публикации] (Date, 1-е число месяца публикации статьи): у таблицы
    # когорт нет связи с месяцем обращения, период для них = месяц публикации.
    Metric(
        metric_id="growth_new_contacts",
        display_name="Новые контакты клиники (рост контактов)",
        description=(
            f"{_GROWTH_TERMS} Сколько новых контактов было в месяце обращения — по всем "
            "страницам входа, включая обращения без связанного визита на сайт. Итог клиники, "
            "не только статьи."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[Новые контакты (рост)]",
        date_aware=True,
        date_table=_GROWTH_MONTH,
        date_granularity="month",
        multi_period_aggregatable=True,
        notes=(
            "Мера страницы «Рост контактов», SUM по 'Рост по месяцам✅'. Данные с 29.06.2026. "
            "Разрезы по группе/направлению в ask-pbi не подключены — группы смотри в "
            "growth_groups_by_new_contacts."
        ),
        confirmed_on="2026-11-09",
    ),
    Metric(
        metric_id="growth_project_new_contacts",
        display_name="Новые контакты проекта (вход через проектную статью)",
        description=(
            f"{_GROWTH_REF} Сколько новых контактов вошли на сайт через проектную статью "
            "(полка «рост-контактов») в месяце обращения. Главное число проекта. Пусто, пока "
            "проектные статьи не опубликованы."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[Новые контакты проекта]",
        date_aware=True,
        date_table=_GROWTH_MONTH,
        date_granularity="month",
        multi_period_aggregatable=True,
        notes=(
            "Мера = [Новые контакты (рост)] с группой «project». Все направления (DP, SEG, RP) "
            "вместе — разрез по направлению в ask-pbi не подключён."
        ),
        confirmed_on="2026-11-09",
    ),
    Metric(
        metric_id="growth_project_weighted_kpi",
        display_name="Взвешенный KPI проекта",
        description=(
            f"{_GROWTH_REF} Баллы проектных статей в визитах новых контактов: статья — вход "
            "визита = 1 балл, статья в середине пути = 0,5 балла, на человека не больше 1. "
            "Дополнительное число к «Новым контактам проекта»: учитывает статьи, которые "
            "помогли, не будучи входом. Пусто, пока проектные статьи не опубликованы."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[Взвешенный KPI проекта]",
        date_aware=True,
        date_table=_GROWTH_MONTH,
        date_granularity="month",
        multi_period_aggregatable=True,
        notes="Дробное число (шаг 0,5). Месяц — месяц обращения.",
        confirmed_on="2026-11-09",
    ),
    Metric(
        metric_id="growth_project_per_1000_entries",
        display_name="Новые контакты на 1000 входов: проект",
        description=(
            f"{_GROWTH_REF} Новые контакты × 1000 / входы через проектные статьи за месяцы "
            "обращения. Пусто, пока проектные статьи не опубликованы. Для вердикта гипотезы "
            "сравнивай по когортам (growth_cohort_*), не по месяцам."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[На 1000 входов: проект]",
        date_aware=True,
        date_table=_GROWTH_MONTH,
        date_granularity="month",
        multi_period_aggregatable=True,
        notes=(
            "Отношение сумм (DIVIDE(SUM новые × 1000, SUM входы)), поэтому на диапазоне "
            "месяцев считается честно, а не средним по месяцам."
        ),
        confirmed_on="2026-11-09",
    ),
    Metric(
        metric_id="growth_control_per_1000_entries",
        display_name="Новые контакты на 1000 входов: контроль",
        description=(
            f"{_GROWTH_REF} Новые контакты × 1000 / входы через обычные статьи фабрики "
            "(контроль) за месяцы обращения. База для сравнения с проектом."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[На 1000 входов: контроль]",
        date_aware=True,
        date_table=_GROWTH_MONTH,
        date_granularity="month",
        multi_period_aggregatable=True,
        notes=(
            "Отношение сумм. Контроль не режется направлением и ситуацией (у обычных статей их "
            "нет). Малые числа: 1 новый контакт на ~1900 входов в месяц — одно обращение "
            "заметно сдвигает значение."
        ),
        confirmed_on="2026-11-09",
    ),
    Metric(
        metric_id="growth_project_lift_vs_control_reference",
        display_name="Прирост проекта к контролю по месяцам (справочно)",
        description=(
            f"{_GROWTH_REF} На 1000 входов проект / контроль − 1, доля (0,5 = +50%). "
            "Справочно: в месяце обращения вместе считаются статьи любого возраста — свежие "
            "проектные против давно живущих обычных, сравнение нечестно к проекту. Вердикт "
            "гипотезы +50% — только growth_hypothesis_verdict (по когортам публикации). "
            "Пусто, пока нет проектных значений."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[Прирост к контролю]",
        date_aware=True,
        date_table=_GROWTH_MONTH,
        date_granularity="month",
        multi_period_aggregatable=True,
        notes="Доля 0–1, не %*100. Пусто, если проект или контроль пусты либо контроль = 0.",
        confirmed_on="2026-11-09",
    ),
    Metric(
        metric_id="growth_cohort_project_per_1000_entries",
        display_name="На 1000 входов в когорте: проект",
        description=(
            f"{_GROWTH_REF} {_GROWTH_COHORT} Новые контакты × 1000 / входы у проектных "
            "статей, опубликованных в выбранные месяцы. Пусто, пока проектные статьи не "
            "опубликованы."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[На 1000 в когорте: проект]",
        date_aware=True,
        date_table=_GROWTH_COHORT_COL,
        date_granularity="month",
        multi_period_aggregatable=True,
        notes=(
            "start_date/end_date = месяц ПУБЛИКАЦИИ статей, не месяц обращения. Все прожитые "
            "месяцы жизни статей (фильтра «Месяц жизни» в ask-pbi нет). Отношение сумм."
        ),
        confirmed_on="2026-11-09",
    ),
    Metric(
        metric_id="growth_cohort_control_per_1000_entries",
        display_name="На 1000 входов в когорте: контроль",
        description=(
            f"{_GROWTH_REF} {_GROWTH_COHORT} Новые контакты × 1000 / входы у обычных статей "
            "фабрики, опубликованных в выбранные месяцы."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[На 1000 в когорте: контроль]",
        date_aware=True,
        date_table=_GROWTH_COHORT_COL,
        date_granularity="month",
        multi_period_aggregatable=True,
        notes=(
            "start_date/end_date = месяц ПУБЛИКАЦИИ статей. Все прожитые месяцы жизни (у "
            "свежих когорт — неполные). Не режется направлением."
        ),
        confirmed_on="2026-11-09",
    ),
    Metric(
        metric_id="growth_cohort_lift",
        display_name="Прирост проекта к контролю в когорте",
        description=(
            f"{_GROWTH_REF} {_GROWTH_COHORT} На 1000 входов проект / контроль − 1 у статей "
            "одной когорты публикации, доля (0,5 = +50%). +50% и выше — то, что ищет проект. "
            "Пусто, пока нет проектных статей в когорте."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[Прирост в когорте]",
        date_aware=True,
        date_table=_GROWTH_COHORT_COL,
        date_granularity="month",
        multi_period_aggregatable=True,
        notes="Доля 0–1. Период = месяц публикации. Вердикт — growth_hypothesis_verdict.",
        confirmed_on="2026-11-09",
    ),
    Metric(
        metric_id="growth_cohort_control_entries_m0_2",
        display_name="Входы контроля когорты за месяцы жизни 0–2",
        description=(
            f"{_GROWTH_REF} {_GROWTH_COHORT} Сколько входов набрали обычные статьи фабрики "
            "когорты за первые три месяца жизни (0 — месяц публикации, 1, 2). Порог вердикта — "
            "1000 входов: меньше — «данных мало». Называй рядом с вердиктом."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[Входы контроля, мес. 0–2]",
        date_aware=True,
        date_table=_GROWTH_COHORT_COL,
        date_granularity="month",
        multi_period_aggregatable=True,
        notes="Период = месяц публикации. Человек, вошедший через две статьи когорты, учтён дважды.",
        confirmed_on="2026-11-09",
    ),
    Metric(
        metric_id="growth_hypothesis_verdict",
        display_name="Гипотеза +50%: вердикт по когортам",
        description=(
            f"{_GROWTH_REF} {_GROWTH_COHORT} Текст, не число: «гипотеза подтверждена», «не "
            "подтверждена», «данных мало» или для нескольких когорт «подтверждена в N из M "
            "зрелых когорт». Гипотеза: проектные статьи дают ≥ 1,5 × новых контактов на 1000 "
            "входов против обычных статей той же когорты. Правило: месяцы жизни 0–2, когорта "
            "прожила 3 месяца, у контроля когорты ≥ 1000 входов, иначе «данных мало». Без дат — "
            "по всем когортам. Рядом называй growth_cohort_control_entries_m0_2 и "
            "growth_project_new_contacts."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[Гипотеза +50%]",
        date_aware=True,
        date_table=_GROWTH_COHORT_COL,
        date_granularity="month",
        multi_period_aggregatable=True,
        notes=(
            "Значение — строка; analyze_trend для неё отказывает (text_metric). Период = месяц "
            "публикации. «Зрелость» когорты считается от TODAY() Service (UTC)."
        ),
        confirmed_on="2026-11-09",
    ),
    Metric(
        metric_id="growth_groups_by_new_contacts",
        display_name="Новые контакты по группам страниц входа",
        description=(
            f"{_GROWTH_REF} Новые контакты, входы и на 1000 входов по группе страницы входа: "
            "проект, контроль, легаси, прочее, без входа. Отвечает, через какие страницы "
            "приходят новые люди. get_breakdown."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[Новые контакты (рост)]",
        date_aware=True,
        date_table=_GROWTH_MONTH,
        date_granularity="month",
        multi_period_aggregatable=True,
        kind="ranking",
        category_column="'Рост группа✅'[Группа (код)]",
        value_alias="new_contacts",
        extra_values=(
            ("entries", "[Входы (рост)]"),
            ("per_1000_entries", "[На 1000 входов (рост)]"),
        ),
        notes=(
            "Коды групп: project — проект, control — контроль, legacy — легаси, other — прочее, "
            "none — без входа (у неё входов нет, per_1000 пусто). Месяц — месяц обращения."
        ),
        confirmed_on="2026-11-09",
    ),
    Metric(
        metric_id="growth_top_articles_by_new_contacts",
        display_name="Топ статей по новым контактам (рост контактов)",
        description=(
            f"{_GROWTH_REF} Статьи сайта, через которые вошли новые контакты: новые контакты, "
            "входы, на 1000 входов, группа статьи (project / control / legacy) и когорта "
            "публикации. Только статьи с ≥ 1 новым контактом. Сравнивай статьи одной когорты. "
            "get_breakdown."
        ),
        status="confirmed",
        datasets=("KPI marketing view",),
        measure_dax_name="[Новые контакты (статья)]",
        date_aware=True,
        date_table=_GROWTH_MONTH,
        date_granularity="month",
        multi_period_aggregatable=True,
        kind="ranking",
        category_column="'Рост по статьям✅'[Статья]",
        value_alias="new_contacts",
        extra_values=(
            ("entries", "[Входы (статья)]"),
            ("per_1000_entries", "[На 1000 входов (статья)]"),
            ("group", "SELECTEDVALUE('Рост по статьям✅'[Группа (код)])"),
            ("cohort", "SELECTEDVALUE('Рост по статьям✅'[Когорта публикации])"),
        ),
        breakdown_row_filter="[Новые контакты (статья)] > 0",
        notes=(
            "Категория — URL статьи. Порог > 0: при 0–1 новых контактах на статью TOPN без "
            "порога возвращает все статьи с ничьей нулей. Месяц — месяц обращения."
        ),
        confirmed_on="2026-11-09",
    ),
]


def get_registry() -> list[Metric]:
    """Копия текущего реестра (список объектов Metric)."""
    return list(REGISTRY)


def find_metric(metric_id: str) -> Metric | None:
    return next((m for m in REGISTRY if m.metric_id == metric_id), None)
