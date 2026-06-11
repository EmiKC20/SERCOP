"""Opportunity scoring for SERCOP procurement processes."""

from __future__ import annotations

import math
import unicodedata
from datetime import date, datetime
from typing import Any

import pandas as pd

from core.keywords import BUSINESS_LINES, KNOWN_BUYERS, PREFERRED_PROCUREMENT_TYPES


def normalize_text(value: Any) -> str:
    """Normalize text for case-insensitive and accent-insensitive matching."""
    text = "" if value is None else str(value)
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def business_line_matches(process: dict[str, Any]) -> dict[str, list[str]]:
    """Return matched keywords by business line for a process."""
    haystack = normalize_text(
        " ".join(
            [
                str(process.get("titulo") or ""),
                str(process.get("objeto") or ""),
                str(process.get("descripcion") or ""),
            ]
        )
    )
    matches: dict[str, list[str]] = {}
    for line, keywords in BUSINESS_LINES.items():
        found = []
        for keyword in keywords:
            if normalize_text(keyword) in haystack:
                found.append(keyword)
        matches[line] = found
    return matches


def keyword_score(matches: dict[str, list[str]]) -> tuple[float, str]:
    """Score keyword relevance and return the most likely business line."""
    best_line = max(matches, key=lambda line: len(matches[line])) if matches else "Sin clasificar"
    best_count = len(matches.get(best_line, []))
    total_count = sum(len(values) for values in matches.values())
    if total_count == 0:
        return 0.0, "Sin clasificar"

    # Three strong hits usually indicate a highly relevant services opportunity.
    score = min(40.0, 18.0 + (best_count * 8.0) + max(0, total_count - best_count) * 2.0)
    return score, best_line


def amount_score(amount: float) -> float:
    """Score budget amount on a logarithmic scale with full score above USD 50,000."""
    amount = max(float(amount or 0), 0.0)
    if amount <= 0:
        return 0.0
    if amount >= 50_000:
        return 25.0
    return min(25.0, 25.0 * (math.log10(amount + 1) / math.log10(50_000)))


def business_days_until(target: date | datetime | pd.Timestamp | None, today: date | None = None) -> int | None:
    """Calculate weekdays until a target date."""
    if target is None or pd.isna(target):
        return None
    if isinstance(target, pd.Timestamp):
        target_date = target.date()
    elif isinstance(target, datetime):
        target_date = target.date()
    else:
        target_date = target
    today = today or date.today()
    if target_date < today:
        return 0
    days = pd.bdate_range(today, target_date).size - 1
    return max(int(days), 0)


def closing_score(close_date: date | datetime | pd.Timestamp | None) -> tuple[float, int | None]:
    """Score deadline attractiveness, favoring 5 to 20 remaining business days."""
    days = business_days_until(close_date)
    if days is None:
        return 4.0, None
    if 5 <= days <= 20:
        return 20.0, days
    if 1 <= days < 5:
        return 8.0 + days
    if 21 <= days <= 40:
        return max(8.0, 20.0 - ((days - 20) * 0.6))
    if days == 0:
        return 2.0, days
    return 6.0, days


def known_buyer_score(buyer_name: str) -> float:
    """Score whether a buyer belongs to the known-entity whitelist."""
    normalized = normalize_text(buyer_name)
    return 10.0 if any(normalize_text(buyer) in normalized for buyer in KNOWN_BUYERS) else 0.0


def preferred_type_score(procurement_type: str) -> float:
    """Score whether the process type matches preferred contracting modes."""
    normalized = normalize_text(procurement_type)
    return 5.0 if any(normalize_text(proc_type) in normalized for proc_type in PREFERRED_PROCUREMENT_TYPES) else 0.0


def score_process(process: dict[str, Any]) -> dict[str, Any]:
    """Return total score, breakdown and suggested business line for one process."""
    matches = business_line_matches(process)
    kw_score, suggested_line = keyword_score(matches)
    budget_score = amount_score(process.get("monto", 0.0))
    deadline_score, business_days = closing_score(process.get("fecha_cierre"))
    buyer_score = known_buyer_score(process.get("entidad", ""))
    type_score = preferred_type_score(process.get("tipo_proceso", ""))

    breakdown = {
        "palabras_clave": round(kw_score, 2),
        "monto": round(budget_score, 2),
        "dias_hasta_cierre": round(deadline_score, 2),
        "entidad_conocida": round(buyer_score, 2),
        "tipo_proceso": round(type_score, 2),
    }
    total = min(100.0, sum(breakdown.values()))
    return {
        "score": round(total, 2),
        "score_desglose": breakdown,
        "linea_negocio": suggested_line,
        "keywords_detectadas": matches.get(suggested_line, []),
        "dias_habiles_cierre": business_days,
    }


def score_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply opportunity scoring to every row in a DataFrame."""
    if frame.empty:
        return frame.assign(
            score=pd.Series(dtype=float),
            linea_negocio=pd.Series(dtype=str),
            dias_habiles_cierre=pd.Series(dtype="Int64"),
        )
    scored_rows = []
    for _, row in frame.iterrows():
        process = row.to_dict()
        scored_rows.append(score_process(process))
    score_frame = pd.DataFrame(scored_rows)
    return pd.concat([frame.reset_index(drop=True), score_frame], axis=1)
