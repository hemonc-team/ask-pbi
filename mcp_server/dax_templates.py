"""Сборка безопасного DAX по жёстко заданным шаблонам.

LLM никогда не передаёт сюда сырой DAX — только имя метрики и даты. Единственные
места, где строится текст запроса — функции этого файла.
"""

from __future__ import annotations

from datetime import date


def build_snapshot_query(measure_dax_name: str) -> str:
    """Запрос значения меры без фильтра — для метрик со status=confirmed/broken,
    date_aware=False (снепшот)."""
    return f'EVALUATE ROW("value", {measure_dax_name})'


def build_period_query(
    measure_dax_name: str,
    date_table: str,
    start_date: date,
    end_date: date,
) -> str:
    """Запрос значения меры за период по дневной таблице дат (`<table>[Date]`).

    Задел на будущее: сегодня ни одна метрика в реестре не привязана к дневной
    таблице дат с активной связью до нужной таблицы фактов (`Лиды✅` связана с
    `date_dim_month` только помесячно — см. build_month_range_query). Годится,
    как только появится метрика с реальной дневной гранулярностью.
    """
    return (
        'EVALUATE ROW("value", CALCULATE('
        f"{measure_dax_name}, "
        f"{date_table} >= DATE({start_date.year},{start_date.month},{start_date.day}) "
        f"&& {date_table} <= DATE({end_date.year},{end_date.month},{end_date.day})"
        "))"
    )


def build_month_range_query(
    measure_dax_name: str,
    year_month_column: str,
    start_year_month: str,
    end_year_month: str,
) -> str:
    """Запрос значения меры за диапазон календарных месяцев через
    `date_dim_month[YearMonth]` (текстовый ключ формата "YYYY-MM").

    Подтверждено живым тестом 2026-08-19: связь `Лиды✅` -> `crm_lead_uf✅` ->
    `date_dim_month` активна только на уровне месяца (YearMonth), дневной
    таблицы дат для этой цепочки нет — поэтому гранулярность всегда месяц,
    не день. `year_month_column` — например "date_dim_month[YearMonth]".
    Сравнение строк "YYYY-MM" лексикографически совпадает с хронологическим
    порядком, поэтому >=/<= работает корректно как диапазон.
    """
    return (
        'EVALUATE ROW("value", CALCULATE('
        f"{measure_dax_name}, "
        f'{year_month_column} >= "{start_year_month}" && {year_month_column} <= "{end_year_month}"'
        "))"
    )
