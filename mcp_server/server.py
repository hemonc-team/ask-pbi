"""MCP-сервер для read-only доступа к Power BI (workspace KPI Team).

Транспорт:
- Streamable HTTP на DWH — `ASKPBI_TRANSPORT=http python3 -m mcp_server.server`
- stdio локально для разработки — `python3 -m mcp_server.server`

LLM никогда не пишет DAX — только `get_available_metrics` /
`get_metric_value` / `analyze_trend`.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date as date_cls
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from pbi_service_client import Config, PBIClient  # noqa: E402  (после sys.path.insert)

from mcp_server.critic import (  # noqa: E402
    build_trend_warnings,
    check_low_confidence,
    check_single_month_required,
    compare_period_lengths,
    month_count,
    normalize_by_days,
    period_days,
    spans_single_month,
    year_month,
)
from mcp_server.dax_templates import (  # noqa: E402
    build_month_range_query,
    build_period_query,
    build_snapshot_query,
)
from mcp_server.registry import find_metric, get_registry  # noqa: E402

from mcp.server import MCPServer  # noqa: E402
from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse, Response  # noqa: E402

from mcp_server.http_auth import build_http_auth  # noqa: E402

WORKSPACE_HINT = "KPI Team"


def _load_env_from_json_config() -> None:
    """Заполняет PBI_TENANT_ID/PBI_CLIENT_ID/PBI_TOKENS_PATH из config/pbi_config.json,
    если они ещё не заданы переменными окружения."""
    cfg_path = REPO_ROOT / "config" / "pbi_config.json"
    if not cfg_path.exists():
        return
    data = json.loads(cfg_path.read_text())
    os.environ.setdefault("PBI_TENANT_ID", data["tenant_id"])
    os.environ.setdefault("PBI_CLIENT_ID", data["client_id"])
    os.environ.setdefault("PBI_TOKENS_PATH", data["tokens_path"])


_load_env_from_json_config()
_cfg = Config.load()
_client = PBIClient(_cfg)

_http_auth, _http_verifier = build_http_auth()
_mcp_kwargs: dict = {}
if _http_auth is not None and _http_verifier is not None:
    _mcp_kwargs["auth"] = _http_auth
    _mcp_kwargs["token_verifier"] = _http_verifier
mcp = MCPServer("ask-pbi", **_mcp_kwargs)


def _public_metric(m) -> dict:
    """Версия Metric для ответа наружу — без внутренних DAX-деталей (measure_dax_name,
    date_table), которые LLM не нужны и не должны провоцировать писать DAX руками."""
    return {
        "metric_id": m.metric_id,
        "display_name": m.display_name,
        "description": m.description,
        "status": m.status,
        "datasets": list(m.datasets),
        "date_aware": m.date_aware,
        "date_granularity": m.date_granularity,
        "multi_period_aggregatable": m.multi_period_aggregatable,
        "supported_filters": list(m.supported_filters),
        "notes": m.notes,
        "confirmed_on": m.confirmed_on,
    }


def _extract_value(result: dict) -> float | int | None:
    rows = result.get("results", [{}])[0].get("tables", [{}])[0].get("rows", [])
    # DAX executeQueries возвращает имена колонок в квадратных скобках ("[value]"),
    # а не голым именем — см. references/known-fields.md / pbi_service_client._row_get.
    row = rows[0] if rows else {}
    return row.get("value", row.get("[value]"))


@mcp.tool()
def get_available_metrics() -> dict:
    """Вернуть список подтверждённых бизнес-метрик Power BI (workspace KPI Team).

    Это ЕДИНСТВЕННЫЙ способ узнать, какие метрики существуют — не пытайся
    писать сырой DAX или изобретать metric_id. Метрики со status="broken"
    намеренно оставлены в списке (не скрыты) — get_metric_value на них честно
    откажет. Поле date_granularity ("month"/"day") — минимальный шаг периода,
    который метрика реально поддерживает; multi_period_aggregatable=false
    значит, что период обязан укладываться ровно в один такой шаг (см.
    get_metric_value/analyze_trend).
    """
    return {"ok": True, "metrics": [_public_metric(m) for m in get_registry()]}


@mcp.tool()
def get_metric_value(
    metric_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    filters: dict | None = None,
) -> dict:
    """Получить значение одной метрики по её metric_id (из get_available_metrics).

    Никогда не вызывай с metric_id, которого не видел в get_available_metrics —
    неизвестная метрика вернёт {"ok": false, "reason": "metric_not_found"}, а не
    приблизительное значение. start_date/end_date — "YYYY-MM-DD", оба вместе
    или ни одного (без дат — итог за всё время). Гранулярность фильтра
    определяется метрикой (date_granularity в реестре): для "month" период
    округляется до целых календарных месяцев — если запрошенный диапазон не
    совпадает с границами месяца(ев), в ответе будет warnings об округлении.
    Если multi_period_aggregatable=false, а диапазон шире одного месяца —
    вернётся честный отказ reason="metric_single_month_only", а не
    домысленное среднее/сумма.
    """
    metric = find_metric(metric_id)
    if metric is None:
        return {
            "ok": False,
            "reason": "metric_not_found",
            "detail": f"metric_id '{metric_id}' не найден в реестре — сначала вызови get_available_metrics.",
        }
    if metric.status == "broken":
        return {
            "ok": False,
            "reason": "metric_broken",
            "detail": metric.notes or "Эта метрика зарегистрирована как нерабочая.",
        }
    if metric.status == "unverified":
        return {
            "ok": False,
            "reason": "metric_unverified",
            "detail": "Эта метрика ни разу не проверена живым запросом — использовать нельзя.",
        }
    if not metric.date_aware and (start_date or end_date):
        return {
            "ok": False,
            "reason": "not_date_filterable",
            "detail": (
                "Эта метрика игнорирует фильтр по дате (подтверждено живым "
                "запросом) — доступен только снепшот без периода. Повтори "
                "вызов без start_date/end_date."
            ),
        }
    if (start_date is None) != (end_date is None):
        return {
            "ok": False,
            "reason": "invalid_period",
            "detail": "start_date и end_date нужно передавать вместе, либо не передавать ни один из них.",
        }

    dataset_name = metric.datasets[0]
    try:
        resolved = _client.resolve_dataset(dataset_name, WORKSPACE_HINT)
    except RuntimeError as e:
        return {"ok": False, "reason": "dataset_resolve_failed", "detail": str(e)}

    warnings: list[str] = []
    period = {"start_date": None, "end_date": None, "label": "all_time_snapshot"}

    if start_date is None:
        query = build_snapshot_query(metric.measure_dax_name)
    elif metric.date_granularity == "month":
        refusal = check_single_month_required(metric.multi_period_aggregatable, start_date, end_date)
        if refusal is not None:
            return refusal
        ym_start, ym_end = year_month(start_date), year_month(end_date)
        query = build_month_range_query(metric.measure_dax_name, metric.date_table, ym_start, ym_end)
        period = {"start_date": start_date, "end_date": end_date, "label": f"{ym_start}..{ym_end}"}
        first_of_month = start_date[:8] + "01"
        if start_date != first_of_month or not _is_month_end(end_date):
            warnings.append(
                f"Гранулярность этой метрики — календарный месяц: запрошенный частичный период "
                f"округлён до {ym_start}..{ym_end} целиком."
            )
    elif metric.date_granularity == "day":
        query = build_period_query(
            metric.measure_dax_name,
            metric.date_table,
            date_cls.fromisoformat(start_date),
            date_cls.fromisoformat(end_date),
        )
        period = {"start_date": start_date, "end_date": end_date, "label": f"{start_date}..{end_date}"}
    else:
        return {
            "ok": False,
            "reason": "unsupported_granularity",
            "detail": f"date_granularity='{metric.date_granularity}' у метрики не поддерживается сервером.",
        }

    try:
        result = _client.execute_dax(resolved["group_id"], resolved["dataset_id"], query)
    except RuntimeError as e:
        return {"ok": False, "reason": "pbi_query_failed", "detail": str(e)}

    value = _extract_value(result)

    return {
        "ok": True,
        "metric_id": metric.metric_id,
        "value": value,
        "period": period,
        "dataset": resolved["dataset"],
        "group_id": resolved["group_id"],
        "warnings": warnings,
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


def _is_month_end(iso_date: str) -> bool:
    y, m, d = (int(p) for p in iso_date.split("-"))
    next_month = date_cls(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1)
    last_day = (next_month - date_cls(y, m, 1)).days
    return d == last_day


@mcp.tool()
def analyze_trend(metric_id: str, current_period: dict, previous_period: dict) -> dict:
    """ОБЯЗАТЕЛЬНАЯ точка входа для ЛЮБОГО вопроса про динамику/тренд/сравнение
    периодов/конверсию во времени. НИКОГДА не собирай тренд вручную из двух
    вызовов get_metric_value — вся логика гейта критика (сопоставимость
    периодов, минимальная значимость, отказ для метрик с ограниченной
    гранулярностью) здесь.

    current_period/previous_period: {"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}.
    Если у метрики multi_period_aggregatable=false (см. get_available_metrics) —
    каждый из периодов обязан быть ровно одним календарным месяцем (напр.
    "квартал к кварталу" для такой метрики вернёт честный отказ
    metric_single_month_only, а не домысленное среднее по трём месяцам —
    сравнивай такую метрику месяц к месяцу).

    Поле "explanation" в ответе всегда null — этот инструмент никогда не
    сочиняет причину роста/падения ("выросло потому что..."). Если нужна
    причина — это отдельный анализ, не выдумывай её сам от лица инструмента.
    """
    metric = find_metric(metric_id)
    if metric is None:
        return {
            "ok": False,
            "reason": "metric_not_found",
            "detail": f"metric_id '{metric_id}' не найден в реестре.",
        }
    if not metric.date_aware:
        return {
            "ok": False,
            "reason": "metric_not_date_aware",
            "detail": (
                "Эта метрика не реагирует на фильтр по дате (подтверждено живым "
                "запросом) — анализ динамики/тренда для неё невозможен."
            ),
        }
    if metric.date_granularity == "month" and not metric.multi_period_aggregatable:
        for label, p in (("current_period", current_period), ("previous_period", previous_period)):
            if not spans_single_month(p["start_date"], p["end_date"]):
                return {
                    "ok": False,
                    "reason": "metric_single_month_only",
                    "detail": (
                        f"{label} шире одного календарного месяца, а эта метрика "
                        "не агрегируется больше чем на месяц за раз (подтверждено "
                        "живым тестом — возвращает пусто на диапазоне из "
                        "нескольких месяцев). Сравнивай эту метрику месяц к месяцу."
                    ),
                }

    cur = get_metric_value(metric_id, current_period.get("start_date"), current_period.get("end_date"))
    prev = get_metric_value(metric_id, previous_period.get("start_date"), previous_period.get("end_date"))
    if not cur.get("ok"):
        return cur
    if not prev.get("ok"):
        return prev

    days_cur = period_days(current_period["start_date"], current_period["end_date"])
    days_prev = period_days(previous_period["start_date"], previous_period["end_date"])
    if metric.date_granularity == "month":
        # Сравниваем число календарных месяцев, а не дней — иначе июнь (30 дн.)
        # и май (31 дн.) ложно флагуются как "периоды разной длины", хотя оба
        # ровно один месяц. Среднедневная нормализация ниже всё равно считает
        # по реальным дням — тут только флаг сопоставимости другой.
        length_cmp = compare_period_lengths(
            month_count(current_period["start_date"], current_period["end_date"]),
            month_count(previous_period["start_date"], previous_period["end_date"]),
            unit="мес.",
        )
    else:
        length_cmp = compare_period_lengths(days_cur, days_prev)

    cur_value = cur["value"] or 0
    prev_value = prev["value"] or 0
    delta_abs = cur_value - prev_value
    delta_pct = (delta_abs / prev_value * 100) if prev_value else None
    low_confidence = check_low_confidence(prev_value)
    warnings = build_trend_warnings(length_cmp, low_confidence)
    warnings.extend(cur.get("warnings") or [])
    warnings.extend(prev.get("warnings") or [])

    return {
        "ok": True,
        "metric_id": metric.metric_id,
        "current": {"value": cur_value, "period": cur["period"], "days": days_cur},
        "previous": {"value": prev_value, "period": prev["period"], "days": days_prev},
        "delta_absolute": delta_abs,
        "delta_pct": delta_pct,
        "period_length_mismatch": length_cmp["mismatch"],
        "normalized": {
            "current_daily_avg": normalize_by_days(cur_value, days_cur),
            "previous_daily_avg": normalize_by_days(prev_value, days_prev),
        },
        "low_confidence": low_confidence,
        "warnings": warnings,
        "explanation": None,
    }


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> Response:
    return JSONResponse({"ok": True, "server": "ask-pbi"})


def main() -> None:
    transport = os.environ.get("ASKPBI_TRANSPORT", "stdio").strip().lower()
    if transport in ("http", "streamable-http"):
        if not os.environ.get("ASKPBI_MCP_TOKEN", "").strip():
            sys.stderr.write("ERROR: ASKPBI_TRANSPORT=http требует ASKPBI_MCP_TOKEN\n")
            sys.exit(2)
        mcp.run(
            transport="streamable-http",
            host=os.environ.get("ASKPBI_BIND", "127.0.0.1"),
            port=int(os.environ.get("ASKPBI_PORT", "8100")),
            streamable_http_path="/mcp",
            stateless_http=True,
            transport_security=TransportSecuritySettings(
                enable_dns_rebinding_protection=False
            ),
        )
        return
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
