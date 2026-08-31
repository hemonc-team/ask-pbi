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


def main() -> None:
    _check_catalog_helpers()
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
        "get_metric_value('site_pageviews_count', Q1 2026 = янв-мар)  — ожидаем ok:true, сумма месяцев",
        get_metric_value("site_pageviews_count", "2026-01-01", "2026-03-31"),
    )

    _p(
        "get_metric_value('nonexistent_metric')  — ожидаем ok:false, metric_not_found",
        get_metric_value("nonexistent_metric"),
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
        "get_metric_value('top_entry_pages')  — ожидаем ok:false, use_get_breakdown",
        get_metric_value("top_entry_pages"),
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
