"""Проверка логики tool-функций напрямую, без MCP-транспорта.

Запуск: `python3 -m mcp_server.smoke_test`.
На проде — `.env` с Service Principal. Локально — delegated `pbi_run.sh login`.
"""

from __future__ import annotations

import json

from mcp_server.model_catalog import (  # noqa: E402
    named_measure_from_dax,
    resolve_allowed_dataset,
)
from mcp_server.server import (  # noqa: E402
    analyze_trend,
    get_available_metrics,
    get_breakdown,
    get_metric_value,
    list_model_measures,
)


def _p(label: str, obj) -> None:
    print(f"\n== {label} ==")
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def _check_catalog_helpers() -> None:
    assert named_measure_from_dax("[Количество свежих контактов]") == (
        "Количество свежих контактов"
    )
    assert named_measure_from_dax("SUM('Посетители сайта во времени✅📅'[Посетители])") is None
    assert resolve_allowed_dataset(None) == "KPI marketing view"
    assert resolve_allowed_dataset("leads_marketing") is None
    from mcp_server.model_catalog import measures_from_schema

    leaked = measures_from_schema(
        {
            "measures": [
                {
                    "[Name]": "X",
                    "[Table]": "T",
                    "[Expression]": "CALCULATE(1)",
                    "[IsHidden]": False,
                }
            ]
        }
    )
    assert leaked == [
        {
            "name": "X",
            "table": "T",
            "description": "",
            "display_folder": "",
            "hidden": False,
            "in_registry": False,
            "registry_ids": [],
        }
    ]
    assert measures_from_schema(
        {"measures": [{"[Name]": "ФИО", "[Table]": "Пациенты", "[IsHidden]": False}]}
    ) == []
    print("ok catalog helpers")


def _check_month_grain_registry() -> None:
    """Офлайн: island Метрики/контент — month, не day; % с single-month — false."""
    from datetime import date

    from mcp_server.critic import calendar_month_bounds, uses_year_month_key
    from mcp_server.dax_templates import build_period_query
    from mcp_server.registry import find_metric, get_registry

    assert calendar_month_bounds("2026-08-24", "2026-08-30") == (
        date(2026, 8, 1),
        date(2026, 8, 31),
    )
    assert uses_year_month_key("date_dim_month[YearMonth]") is True
    assert uses_year_month_key("'Посетители сайта во времени✅📅'[Месяц визита]") is False

    month_ids = (
        "site_visitors_count",
        "site_pageviews_count",
        "content_leads_count",
        "content_bookings_count",
        "top_entry_pages",
        "top_regions",
        "top_cities",
        "top_search_engines",
        "top_social_networks",
        "top_direct_campaigns",
        "top_content_landings_by_leads",
        "top_content_landings_by_visitors",
    )
    for mid in month_ids:
        m = find_metric(mid)
        assert m is not None, mid
        assert m.date_granularity == "month", mid
        assert m.multi_period_aggregatable is True, mid

    conv = find_metric("fresh_contact_conversion_rate_pct")
    assert conv is not None
    assert conv.date_granularity == "month"
    assert conv.multi_period_aggregatable is False

    daily = find_metric("contact_to_visit_conversion_pct")
    assert daily is not None
    assert daily.date_granularity == "day"

    q = build_period_query(
        "SUM('T'[X])",
        "'T'[Месяц визита]",
        date(2026, 8, 1),
        date(2026, 8, 31),
    )
    assert "DATE(2026,8,1)" in q and "DATE(2026,9,1)" in q
    assert "< DATE(2026,9,1)" in q

    # sanity: в реестре нет «ложного day» на колонках Месяц*
    for m in get_registry():
        if m.date_table and ("Месяц" in m.date_table):
            assert m.date_granularity == "month", m.metric_id

    for mid in (
        "bookings_count",
        "attended_count",
        "cancellations_count",
        "cancellation_rate_pct",
        "top_cancellation_reasons",
        "top_doctors_by_bookings",
        "primary_bookings_1c",
    ):
        m = find_metric(mid)
        assert m is not None, mid
        assert m.date_granularity == "day", mid
        assert "admin" in m.datasets[0] or "medicine" in m.datasets[0], mid

    tc = find_metric("true_canceled_count_1c")
    assert tc is not None and tc.multi_period_aggregatable is False
    assert find_metric("top_doctors_by_cancellation_rate").breakdown_row_filter

    from mcp_server.dax_templates import build_topn_query

    tq = build_topn_query(
        "'Специалисты'[НаименованиеПолное]",
        "cancel_pct",
        "[П_Отмены %]",
        row_filter="[П_Записи] >= 50",
    )
    assert "[П_Записи] >= 50" in tq

    for mid in (
        "regional_clicks_count",
        "regional_visits_count",
        "regional_calls_count",
        "regional_leads_count",
        "regional_bookings_count",
        "regional_cost_rub",
        "regional_cr_calls_high_pct",
        "top_regional_oblasts_by_clicks",
        "top_regional_campaigns_by_clicks",
    ):
        m = find_metric(mid)
        assert m is not None, mid
        assert m.date_granularity == "day", mid
        assert m.datasets == ("KPI marketing view",), mid
        assert m.date_table == "'Региональная воронка✅'[Дата]", mid
        assert m.multi_period_aggregatable is True, mid
    assert find_metric("top_regional_campaigns_by_clicks").kind == "ranking"
    assert find_metric("regional_cr_calls_high_pct").measure_dax_name == "[CR звонки high]"
    smm = (
        "smm_followers",
        "smm_followers_growth",
        "smm_posts",
        "smm_reach",
        "smm_reactions",
        "smm_by_network",
    )
    for mid in smm:
        m = find_metric(mid)
        assert m is not None, mid
        assert m.date_granularity == "month" and m.multi_period_aggregatable is True, mid
        assert m.datasets == ("KPI marketing view",), mid
    for mid in smm[:-1]:
        assert find_metric(mid).date_table == "date_dim_month[YearMonth]", mid
    net = find_metric("smm_by_network")
    assert net.kind == "ranking" and net.date_table == "date_dim_month[MonthStartDate]"
    assert [a for a, _ in net.extra_values] == ["growth", "posts", "reach", "reactions"]
    print("ok month-grain registry")


def _smm_scenarios() -> None:
    """Соцсети (#26158): контрольные цифры — pbi docs/domain/СОЦСЕТИ_визуалы_и_ask-pbi_TZ.md §3.4."""
    _p(
        "get_metric_value('smm_followers', Q3 2026)  — ожидаем 17878 (на конец сентября)",
        get_metric_value("smm_followers", "2026-07-01", "2026-09-30"),
    )
    _p(
        "get_metric_value('smm_followers_growth', 2025)  — ожидаем +4125",
        get_metric_value("smm_followers_growth", "2025-01-01", "2025-12-31"),
    )
    _p(
        "get_breakdown('smm_by_network', весна 2026)  — Telegram growth +57",
        get_breakdown("smm_by_network", 10, "2026-03-01", "2026-05-31"),
    )
    _p(
        "get_breakdown('smm_by_network', лето 2026)  — Telegram growth −7",
        get_breakdown("smm_by_network", 10, "2026-06-01", "2026-08-31"),
    )
    _p(
        "analyze_trend('smm_posts', лето vs весна 2026)",
        analyze_trend(
            "smm_posts",
            {"start_date": "2026-06-01", "end_date": "2026-08-31"},
            {"start_date": "2026-03-01", "end_date": "2026-05-31"},
        ),
    )


def _check_growth_registry() -> None:
    """Офлайн: «Рост контактов» — месячные через 'Рост месяц✅', когортные через когорту."""
    from mcp_server.critic import uses_year_month_key
    from mcp_server.registry import get_registry

    growth = [m for m in get_registry() if m.metric_id.startswith("growth_")]
    assert len(growth) == 13, len(growth)
    for m in growth:
        assert m.datasets == ("KPI marketing view",), m.metric_id
        assert m.date_granularity == "month", m.metric_id
        assert not uses_year_month_key(m.date_table), m.metric_id  # Date-якорь, DATE()-фильтр
        if "cohort" in m.metric_id or m.metric_id == "growth_hypothesis_verdict":
            assert m.date_table == "'Рост когорты✅'[Когорта публикации]", m.metric_id
            assert "ПУБЛИКАЦИИ" in m.description, m.metric_id
        else:
            assert m.date_table == "'Рост месяц✅'[Месяц (рост)]", m.metric_id
    print("ok growth registry")


def main() -> None:
    _check_catalog_helpers()
    _check_month_grain_registry()
    _smm_scenarios()
    _check_growth_registry()
    _p("get_available_metrics()", get_available_metrics())

    _p(
        "get_metric_value('fresh_contacts_count')  — без дат, ожидаем ok:true, всего за всё время",
        get_metric_value("fresh_contacts_count"),
    )

    _p(
        "get_metric_value('fresh_contacts_count', июнь 2026)  — ожидаем ok:true, ~509",
        get_metric_value("fresh_contacts_count", "2026-06-01", "2026-06-30"),
    )

    _p(
        "get_metric_value('fresh_contacts_count', Q2 2026 = апр-июн)  — ожидаем ok:true, сумма месяцев (1584)",
        get_metric_value("fresh_contacts_count", "2026-04-01", "2026-06-30"),
    )

    _p(
        "get_metric_value('fresh_contact_conversion_rate_pct', июнь 2026)  — ожидаем ok:true, ~51",
        get_metric_value("fresh_contact_conversion_rate_pct", "2026-06-01", "2026-06-30"),
    )

    _p(
        "get_metric_value('fresh_contact_conversion_rate_pct', Q2 2026)  — ожидаем ok:false, metric_single_month_only",
        get_metric_value("fresh_contact_conversion_rate_pct", "2026-04-01", "2026-06-30"),
    )

    _p(
        "get_metric_value('site_visitors_count', июль 2026)  — ожидаем ok:true, ~21171",
        get_metric_value("site_visitors_count", "2026-07-01", "2026-07-31"),
    )

    _p(
        "get_metric_value('site_visitors_count', 24–30 авг 2026)  — ожидаем ok:true + warning округления до августа",
        get_metric_value("site_visitors_count", "2026-08-24", "2026-08-30"),
    )

    _p(
        "get_metric_value('site_pageviews_count', Q1 2026 = янв-мар)  — ожидаем ok:true, сумма месяцев",
        get_metric_value("site_pageviews_count", "2026-01-01", "2026-03-31"),
    )

    _p(
        "get_metric_value('nonexistent_metric')  — ожидаем ok:false, metric_not_found",
        get_metric_value("nonexistent_metric"),
    )

    _p(
        "get_metric_value('attended_count', март 2026)  — ожидаем ~653",
        get_metric_value("attended_count", "2026-03-01", "2026-03-31"),
    )
    _p(
        "get_metric_value('cancellations_count', март 2026)  — ожидаем ~151",
        get_metric_value("cancellations_count", "2026-03-01", "2026-03-31"),
    )
    _p(
        "get_metric_value('cancellation_rate_pct', Q1 2026)  — ожидаем ok:true ~0.18",
        get_metric_value("cancellation_rate_pct", "2026-01-01", "2026-03-31"),
    )
    _p(
        "get_metric_value('primary_bookings_1c', июнь 2026)  — ожидаем ~729 medicine",
        get_metric_value("primary_bookings_1c", "2026-06-01", "2026-06-30"),
    )
    _p(
        "get_metric_value('true_canceled_count_1c', июнь 2026)  — ожидаем ~89",
        get_metric_value("true_canceled_count_1c", "2026-06-01", "2026-06-30"),
    )
    _p(
        "get_metric_value('true_canceled_count_1c', Q2 2026)  — ожидаем metric_single_month_only",
        get_metric_value("true_canceled_count_1c", "2026-04-01", "2026-06-30"),
    )
    _p(
        "get_breakdown('top_cancellation_reasons', 5)  — ожидаем причины отмены",
        get_breakdown("top_cancellation_reasons", 5),
    )
    _p(
        "get_breakdown('top_doctors_by_bookings', 3, март 2026)",
        get_breakdown("top_doctors_by_bookings", 3, "2026-03-01", "2026-03-31"),
    )

    _p(
        "get_metric_value('incoming_calls_success', янв 2026)  — ожидаем ~595",
        get_metric_value("incoming_calls_success", "2026-01-01", "2026-01-31"),
    )
    _p(
        "get_metric_value('oncology_bookings_count', март 2026)  — ожидаем ~324",
        get_metric_value("oncology_bookings_count", "2026-03-01", "2026-03-31"),
    )
    _p(
        "get_metric_value('sarafan_patients_count', июнь 2026)  — ожидаем ~140",
        get_metric_value("sarafan_patients_count", "2026-06-01", "2026-06-30"),
    )
    _p(
        "get_breakdown('top_sarafan_agents', 3)",
        get_breakdown("top_sarafan_agents", 3),
    )
    _p(
        "get_breakdown('top_direct_search_phrases', 3)",
        get_breakdown("top_direct_search_phrases", 3),
    )

    _p(
        "analyze_trend('fresh_contact_conversion_rate_pct', июнь vs май 2026)  — ожидаем ok:true, оба месяца, дельта",
        analyze_trend(
            "fresh_contact_conversion_rate_pct",
            {"start_date": "2026-06-01", "end_date": "2026-06-30"},
            {"start_date": "2026-05-01", "end_date": "2026-05-31"},
        ),
    )

    _p(
        "analyze_trend('fresh_contact_conversion_rate_pct', Q2 2026 vs Q1 2026)  — ожидаем ok:false, metric_single_month_only",
        analyze_trend(
            "fresh_contact_conversion_rate_pct",
            {"start_date": "2026-04-01", "end_date": "2026-06-30"},
            {"start_date": "2026-01-01", "end_date": "2026-03-31"},
        ),
    )

    _p(
        "analyze_trend('fresh_contacts_count', Q2 2026 vs Q1 2026)  — ожидаем ok:true (count агрегируется по кварталу)",
        analyze_trend(
            "fresh_contacts_count",
            {"start_date": "2026-04-01", "end_date": "2026-06-30"},
            {"start_date": "2026-01-01", "end_date": "2026-03-31"},
        ),
    )

    _p(
        "analyze_trend('site_visitors_count', 2026 vs 2025)  — ожидаем ok:true, годовое сравнение",
        analyze_trend(
            "site_visitors_count",
            {"start_date": "2026-01-01", "end_date": "2026-08-31"},
            {"start_date": "2025-01-01", "end_date": "2025-08-31"},
        ),
    )

    _p(
        "get_breakdown('top_content_landings_by_leads', 3)  — ожидаем дексаметазон ~272",
        get_breakdown("top_content_landings_by_leads", 3),
    )

    _p(
        "get_breakdown('top_entry_pages', 3)  — ожидаем URL hemonc.ru/poleznoe/…",
        get_breakdown("top_entry_pages", 3),
    )

    _p(
        "get_metric_value('growth_control_per_1000_entries', окт 2026)  — ожидаем ~0.527",
        get_metric_value("growth_control_per_1000_entries", "2026-10-01", "2026-10-31"),
    )
    _p(
        "get_metric_value('growth_cohort_control_per_1000_entries', когорта 2026-09)  — ожидаем ~0.45",
        get_metric_value("growth_cohort_control_per_1000_entries", "2026-09-01", "2026-09-30"),
    )
    _p(
        "get_metric_value('growth_hypothesis_verdict')  — ожидаем текст, пока «данных мало»",
        get_metric_value("growth_hypothesis_verdict"),
    )
    _p(
        "analyze_trend('growth_hypothesis_verdict', …)  — ожидаем ok:false, text_metric",
        analyze_trend(
            "growth_hypothesis_verdict",
            {"start_date": "2026-09-01", "end_date": "2026-09-30"},
            {"start_date": "2026-08-01", "end_date": "2026-08-31"},
        ),
    )
    _p(
        "get_breakdown('growth_groups_by_new_contacts', 10, окт 2026)  — ожидаем control 1897 входов / 1 новый",
        get_breakdown("growth_groups_by_new_contacts", 10, "2026-10-01", "2026-10-31"),
    )

    _p(
        "get_metric_value('top_entry_pages')  — ожидаем ok:false, use_get_breakdown",
        get_metric_value("top_entry_pages"),
    )

    _p(
        "get_metric_value('regional_clicks_count')  — ожидаем ok:true, ~14378",
        get_metric_value("regional_clicks_count"),
    )
    _p(
        "get_metric_value('regional_clicks_count', 20.07–10.08.2026)  — ожидаем ~1495",
        get_metric_value("regional_clicks_count", "2026-07-20", "2026-08-10"),
    )
    _p(
        "get_breakdown('top_regional_campaigns_by_clicks', 5)",
        get_breakdown("top_regional_campaigns_by_clicks", 5),
    )
    _p(
        "get_breakdown('top_regional_oblasts_by_clicks', 5, июль 2026)",
        get_breakdown(
            "top_regional_oblasts_by_clicks", 5, "2026-07-01", "2026-07-31"
        ),
    )
    _p(
        "list_model_measures(search='CR звонки')  — ожидаем in_registry true",
        list_model_measures(search="CR звонки"),
    )
    _p(
        "list_model_measures(search='свежих')  — ожидаем in_registry true, Количество свежих контактов",
        list_model_measures(search="свежих"),
    )
    _p(
        "list_model_measures(search='Chemo')  — ожидаем меры, in_registry false",
        list_model_measures(search="Chemo"),
    )
    _p(
        "list_model_measures(dataset='leads_marketing')  — ожидаем ok:false, dataset_not_allowed",
        list_model_measures(dataset="leads_marketing"),
    )


if __name__ == "__main__":
    main()
