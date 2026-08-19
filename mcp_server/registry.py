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
]


def get_registry() -> list[Metric]:
    """Копия текущего реестра (список объектов Metric)."""
    return list(REGISTRY)


def find_metric(metric_id: str) -> Metric | None:
    return next((m for m in REGISTRY if m.metric_id == metric_id), None)
