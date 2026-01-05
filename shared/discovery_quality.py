"""
Quality gates and evidence marker checks for Startup Discovery outputs.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

REQUIRED_SLOTS = ("rationale", "evidence", "sources", "assumptions", "uncertainties")
REQUIRED_MARKERS = ("[FINDING]", "[ASSUMPTION]", "[UNCERTAINTY]")

_EFFECT_SIZE_PATTERN = re.compile(r"\d+(\.\d+)?\s*(%|퍼센트|배|조|억|만|천|십억|조원|억원)")


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _has_effect_size(evidence: List[str], markers: List[Dict[str, Any]]) -> bool:
    for item in evidence:
        if isinstance(item, str) and _EFFECT_SIZE_PATTERN.search(item):
            return True
    for item in markers:
        if not isinstance(item, dict):
            continue
        effect_size = item.get("effect_size")
        if isinstance(effect_size, str) and effect_size.strip():
            return True
        if isinstance(effect_size, (int, float)):
            return True
        statement = item.get("statement", "")
        if isinstance(statement, str) and _EFFECT_SIZE_PATTERN.search(statement):
            return True
    return False


def evaluate_recommendations(recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluate recommendation quality with mandatory slots and evidence markers.
    """
    issues: List[Dict[str, Any]] = []
    missing_by_field = {slot: 0 for slot in REQUIRED_SLOTS}
    missing_marker_count = 0
    missing_effect_size_count = 0

    for rec in recommendations or []:
        rec_issues = []
        industry = rec.get("industry", "N/A")

        for slot in REQUIRED_SLOTS:
            value = rec.get(slot)
            if not value:
                missing_by_field[slot] += 1
                rec_issues.append(f"missing:{slot}")

        markers = _as_list(rec.get("evidence_markers"))
        marker_labels = [
            item.get("marker") for item in markers
            if isinstance(item, dict) and item.get("marker")
        ]
        for marker in REQUIRED_MARKERS:
            if marker not in marker_labels:
                missing_marker_count += 1
                rec_issues.append(f"missing_marker:{marker}")

        evidence_items = _as_list(rec.get("evidence"))
        if not _has_effect_size(evidence_items, markers):
            missing_effect_size_count += 1
            rec_issues.append("missing_effect_size")

        if rec_issues:
            issues.append({"industry": industry, "issues": rec_issues})

    missing_slot_total = sum(missing_by_field.values())
    score = 100
    score -= missing_slot_total * 5
    score -= missing_marker_count * 3
    score -= missing_effect_size_count * 4
    score = max(score, 0)

    return {
        "quality_score": score,
        "missing_by_field": missing_by_field,
        "issues": issues,
        "required_slots": list(REQUIRED_SLOTS),
        "required_markers": list(REQUIRED_MARKERS),
    }
