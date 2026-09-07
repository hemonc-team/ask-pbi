"""Справочник именованных мер модели — без DAX-выражений и без цифр.

Нужен инструменту list_model_measures: LLM видит, что мера существует, но не
может её посчитать, пока запись не попала в registry.py. Expression / FormatString
наружу не отдаём — провоцируют писать DAX руками.
"""

from __future__ import annotations

import re
from typing import Any

from mcp_server.registry import get_registry

ALLOWED_DATASETS: tuple[str, ...] = (
    "KPI marketing view",
    "KPI medicine view",
    "KPI team admin view",
)
DEFAULT_DATASET = "KPI marketing view"

# ПДн / персональный уровень — имена мер с этих таблиц не показываем.
_BLOCKED_TABLE_MARKERS = ("пациент", "фио", "телефон", "phone")

_NAMED_MEASURE_RE = re.compile(
    r"^(?:'[^']+'|[A-Za-zА-Яа-яЁё_][\wА-Яа-яЁё]*)\s*\[([^\[\]]+)\]$"
)


def resolve_allowed_dataset(name: str | None) -> str | None:
    """Точное имя из allowlist или None, если датасет вне периметра."""
    raw = (name or DEFAULT_DATASET).strip()
    if not raw:
        raw = DEFAULT_DATASET
    folded = raw.casefold()
    for allowed in ALLOWED_DATASETS:
        if allowed.casefold() == folded:
            return allowed
    return None


def named_measure_from_dax(dax: str) -> str | None:
    """Имя именованной меры из DAX-ссылки, или None для SUM/CALCULATE/прочего."""
    s = (dax or "").strip()
    if re.fullmatch(r"\[[^\[\]]+\]", s):
        return s[1:-1]
    m = _NAMED_MEASURE_RE.fullmatch(s)
    return m.group(1) if m else None


def registry_ids_by_measure_name() -> dict[str, list[str]]:
    """casefold(имя меры) → metric_id из реестра (только именованные меры)."""
    out: dict[str, list[str]] = {}
    for metric in get_registry():
        name = named_measure_from_dax(metric.measure_dax_name)
        if not name:
            continue
        key = name.casefold()
        out.setdefault(key, []).append(metric.metric_id)
    return out


def _row_get(row: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in row:
            return row[k]
        bracket = f"[{k}]"
        if bracket in row:
            return row[bracket]
    return None


def _as_bool(value: Any) -> bool:
    if value in (True, False):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in ("true", "1", "yes")
    return bool(value)


def _table_blocked(table: str) -> bool:
    folded = table.casefold()
    return any(marker in folded for marker in _BLOCKED_TABLE_MARKERS)


def measures_from_schema(
    schema: dict[str, Any],
    *,
    include_hidden: bool = False,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """Публичные поля мер из ответа discover_schema. Без Expression."""
    by_name = registry_ids_by_measure_name()
    needle = (search or "").strip().casefold()
    out: list[dict[str, Any]] = []
    for row in schema.get("measures") or []:
        name = str(_row_get(row, "Name", "MEASURE_NAME", "MeasureName") or "").strip()
        table = str(_row_get(row, "Table", "TableName", "TABLE_NAME") or "").strip()
        if not name or _table_blocked(table):
            continue
        hidden = _as_bool(_row_get(row, "IsHidden", "IsPrivate", "Hidden"))
        if hidden and not include_hidden:
            continue
        description = str(_row_get(row, "Description") or "").strip()
        folder = str(_row_get(row, "DisplayFolder") or "").strip()
        if needle:
            hay = " ".join((name, table, description, folder)).casefold()
            if needle not in hay:
                continue
        registry_ids = by_name.get(name.casefold(), [])
        out.append(
            {
                "name": name,
                "table": table,
                "description": description,
                "display_folder": folder,
                "hidden": hidden,
                "in_registry": bool(registry_ids),
                "registry_ids": registry_ids,
            }
        )
    out.sort(key=lambda m: (m["table"].casefold(), m["name"].casefold()))
    return out
