"""Встроенный гейт критика — чистые функции без сетевых вызовов.

Раньше это был отдельный skill (critic-gate), который LLM могла вызвать, а
могла и забыть. Теперь эта логика — часть кода analyze_trend в server.py:
пропустить её невозможно, если хочешь получить ответ про динамику.

Каждая функция ничего не знает про Power BI/DAX — принимает готовые числа/дни,
возвращает структурированный вердикт. Из-за этого их легко проверить юнит-тестом
без токена/сети.
"""

from __future__ import annotations

from datetime import date

LOW_CONFIDENCE_THRESHOLD = 20  # знаменатель меньше этого — считаем результат ненадёжным


def year_month(iso_date: str) -> str:
    """"2026-06-15" -> "2026-06" (ключ date_dim_month[YearMonth])."""
    return iso_date[:7]


def spans_single_month(start_date: str, end_date: str) -> bool:
    return year_month(start_date) == year_month(end_date)


def month_count(start_date: str, end_date: str) -> int:
    """Число календарных месяцев в диапазоне (включительно), напр.
    2026-04-01..2026-06-30 -> 3. Используется вместо количества дней для
    сравнения "сопоставимости периодов" у помесячных метрик — иначе июнь
    (30 дн.) и май (31 дн.) всегда ложно флагуются как "периоды разной длины",
    хотя оба являются ровно одним календарным месяцем."""
    y1, m1 = (int(p) for p in start_date[:7].split("-"))
    y2, m2 = (int(p) for p in end_date[:7].split("-"))
    return (y2 - y1) * 12 + (m2 - m1) + 1


def check_single_month_required(
    multi_period_aggregatable: bool, start_date: str, end_date: str
) -> dict | None:
    """Для метрик с multi_period_aggregatable=False (напр.
    fresh_contact_conversion_rate_pct — подтверждено живым тестом: возвращает
    пусто при фильтре на диапазон из >1 месяца) — период обязан укладываться в
    один календарный месяц. Иначе возвращает refusal-словарь."""
    if multi_period_aggregatable:
        return None
    if spans_single_month(start_date, end_date):
        return None
    return {
        "ok": False,
        "reason": "metric_single_month_only",
        "detail": (
            "Эта метрика не агрегируется корректно больше чем на один "
            "календарный месяц за раз (подтверждено живым тестом — на "
            "диапазоне из нескольких месяцев мера возвращает пусто, а не "
            "число). Запроси её по одному месяцу за раз."
        ),
    }


def check_date_aware(date_aware: bool) -> dict | None:
    """Возвращает refusal-словарь, если метрика не период-фильтруема, иначе None."""
    if date_aware:
        return None
    return {
        "ok": False,
        "reason": "metric_not_date_aware",
        "detail": (
            "Эта метрика не реагирует на фильтр по дате (подтверждено живым "
            "запросом) — анализ динамики/тренда для неё невозможен. Доступен "
            "только снепшот через get_metric_value без дат."
        ),
    }


def period_days(start_date: str, end_date: str) -> int:
    """Количество дней в периоде (включительно), ISO-строки YYYY-MM-DD."""
    s = date.fromisoformat(start_date)
    e = date.fromisoformat(end_date)
    return (e - s).days + 1


def compare_period_lengths(current_len: int, previous_len: int, unit: str = "дн.") -> dict:
    """Флаг несопоставимости периодов разной длины (частичный месяц vs полный и т.п.).

    `unit` — что означают current_len/previous_len в сообщении для человека:
    "дн." для дневной гранулярности, "мес." если сравниваются числа месяцев
    (иначе июнь-30дн vs май-31дн ложно флагуются как разной длины, хотя оба —
    ровно один календарный месяц)."""
    return {
        "mismatch": current_len != previous_len,
        "current_len": current_len,
        "previous_len": previous_len,
        "unit": unit,
    }


def normalize_by_days(value: float, days: int) -> float:
    if days <= 0:
        return 0.0
    return value / days


def check_low_confidence(reference_value: float, threshold: int = LOW_CONFIDENCE_THRESHOLD) -> bool:
    """True, если знаменатель/база сравнения слишком мала для уверенного вывода."""
    return reference_value < threshold


def build_trend_warnings(length_cmp: dict, low_confidence: bool) -> list[str]:
    warnings: list[str] = []
    if length_cmp["mismatch"]:
        unit = length_cmp.get("unit", "дн.")
        warnings.append(
            "Периоды разной длины ({} {unit} vs {} {unit}) — сырые суммы напрямую "
            "не сопоставимы, смотри нормализованное (среднедневное) сравнение.".format(
                length_cmp["current_len"], length_cmp["previous_len"], unit=unit
            )
        )
    if low_confidence:
        warnings.append(
            "Базовое значение слишком мало для уверенного вывода о динамике "
            "(низкая статистическая значимость)."
        )
    return warnings
