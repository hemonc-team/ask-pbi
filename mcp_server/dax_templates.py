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
    """Запрос значения меры за период по Date/DateTime-колонке.

    Нижняя граница включительно (`>= DATE(start)`), верхняя — начало следующего
    дня после end (`< DATE(end)+1`). Так корректно и для Date (`date_dim_daily`),
    и для DateTime (`CALL_START_TIME`): иначе `<= DATE(end)` отсекает почти весь
    последний день у datetime.
    """
    from datetime import timedelta

    end_exclusive = end_date + timedelta(days=1)
    return (
        'EVALUATE ROW("value", CALCULATE('
        f"{measure_dax_name}, "
        f"{date_table} >= DATE({start_date.year},{start_date.month},{start_date.day}) "
        f"&& {date_table} < DATE({end_exclusive.year},{end_exclusive.month},{end_exclusive.day})"
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


def build_topn_query(
    category_column: str,
    value_alias: str,
    value_expr: str,
    extra_values: tuple[tuple[str, str], ...] = (),
    top_n: int = 10,
    date_column: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    row_filter: str | None = None,
) -> str:
    """TOPN по категории. LLM не передаёт DAX — только id метрики, даты и top_n.

    row_filter — опциональное DAX-условие в FILTER (напр. "[П_Записи] >= 50").
    """
    n = max(1, min(int(top_n), 20))
    parts = [f"  {category_column},"]
    if date_column and start_date and end_date:
        from datetime import timedelta

        end_exclusive = end_date + timedelta(days=1)
        parts.append(
            "  FILTER(ALL("
            f"{date_column}), {date_column} >= DATE({start_date.year},{start_date.month},{start_date.day})"
            f" && {date_column} < DATE({end_exclusive.year},{end_exclusive.month},{end_exclusive.day})"
            "),"
        )
    parts.append(f'  "{value_alias}", {value_expr}')
    for alias, expr in extra_values:
        parts.append(f'  "{alias}", {expr}')
    summarize = "SUMMARIZECOLUMNS(\n" + ",\n".join(p.rstrip(",") for p in parts) + "\n)"
    blank = (
        f"NOT ISBLANK({category_column}) && {category_column} <> \"\" "
        f'&& {category_column} <> "Not specified" '
        f'&& {category_column} <> "Не определено"'
    )
    if row_filter:
        blank = f"({blank}) && ({row_filter})"
    return (
        "EVALUATE\n"
        f"TOPN({n},\n"
        f"  FILTER(\n    {summarize},\n    {blank}\n  ),\n"
        f"  [{value_alias}], DESC\n"
        ")\n"
        f"ORDER BY [{value_alias}] DESC"
    )
