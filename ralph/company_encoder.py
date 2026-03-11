"""Helpers for encoding and merging company-name aliases."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, Sequence, Tuple

from ralph.utils.korean_text import normalize_text


_COMPANY_PREFIXES = (
    "주식회사",
    "유한회사",
    "합자회사",
    "합명회사",
    "재단법인",
    "사단법인",
    "농업회사법인",
    "영농조합법인",
    "사회적협동조합",
    "협동조합",
)


def _normalize_group_label(value: object) -> str:
    label = normalize_text(str(value or ""))
    label = re.sub(r"\s+", " ", label).strip().strip(":：")
    label = label.replace("㈜", "")
    label = re.sub(r"\(\s*주\s*\)|（\s*주\s*）", "", label)
    label = re.sub(r"\(\s*유\s*\)|（\s*유\s*）", "", label)
    for prefix in _COMPANY_PREFIXES:
        label = re.sub(rf"^{re.escape(prefix)}\s*", "", label)
        label = re.sub(rf"\s*{re.escape(prefix)}$", "", label)
    label = re.sub(r"\s+", " ", label).strip(" -_.,:;")
    return label


def encode_company_alias(value: object) -> Dict[str, Any]:
    group_name = _normalize_group_label(value)
    compact = re.sub(r"[^0-9A-Za-z가-힣]+", "", group_name).lower()
    bigrams = {
        compact[index:index + 2]
        for index in range(max(len(compact) - 1, 0))
        if len(compact[index:index + 2]) == 2
    }
    return {
        "group_name": group_name,
        "compact": compact,
        "bigrams": bigrams,
    }


def company_alias_similarity(left: object, right: object) -> float:
    left_encoded = encode_company_alias(left)
    right_encoded = encode_company_alias(right)
    left_compact = str(left_encoded["compact"])
    right_compact = str(right_encoded["compact"])
    if not left_compact or not right_compact:
        return 0.0
    if left_compact == right_compact:
        return 1.0

    shorter, longer = (
        (left_compact, right_compact)
        if len(left_compact) <= len(right_compact)
        else (right_compact, left_compact)
    )
    if len(shorter) >= 3 and longer.startswith(shorter):
        # Truncated prefixes are the dominant real-world failure mode in OCR/PDF extraction.
        prefix_ratio = len(shorter) / max(len(longer), 1)
        return max(0.78, 0.72 + (prefix_ratio * 0.2))

    prefix_score = 0.0
    shared_prefix = 0
    for left_char, right_char in zip(shorter, longer):
        if left_char != right_char:
            break
        shared_prefix += 1
    if shorter:
        prefix_score = shared_prefix / len(shorter)

    ratio = SequenceMatcher(None, left_compact, right_compact).ratio()
    left_bigrams = left_encoded["bigrams"]
    right_bigrams = right_encoded["bigrams"]
    if not left_bigrams and not right_bigrams:
        jaccard = 1.0 if left_compact == right_compact else 0.0
    else:
        intersection = len(left_bigrams & right_bigrams)
        union = len(left_bigrams | right_bigrams) or 1
        jaccard = intersection / union
    return max(ratio, (jaccard * 0.55) + (prefix_score * 0.45))


def should_merge_company_alias(left: object, right: object) -> bool:
    left_encoded = encode_company_alias(left)
    right_encoded = encode_company_alias(right)
    left_compact = str(left_encoded["compact"])
    right_compact = str(right_encoded["compact"])
    if not left_compact or not right_compact:
        return False
    if left_compact == right_compact:
        return True

    shorter, longer = (
        (left_compact, right_compact)
        if len(left_compact) <= len(right_compact)
        else (right_compact, left_compact)
    )
    if len(shorter) >= 3 and longer.startswith(shorter):
        return True
    if len(shorter) >= 4 and shorter in longer and shorter[:2] == longer[:2]:
        return True

    similarity = company_alias_similarity(left_compact, right_compact)
    if similarity >= 0.88:
        return True
    if similarity >= 0.78 and len(shorter) >= 3 and shorter[:2] == longer[:2]:
        return True
    return False


def build_company_alias_map(
    groups: Sequence[Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, str]], Dict[str, int]]:
    candidates = [
        {
            "company_group_key": str(group.get("company_group_key") or "").strip().lower(),
            "company_group_name": _normalize_group_label(group.get("company_group_name") or ""),
            "file_count": int(group.get("file_count", 0) or 0),
        }
        for group in groups
    ]
    candidates = [
        candidate
        for candidate in candidates
        if candidate["company_group_key"] and candidate["company_group_name"]
    ]

    sorted_groups = sorted(
        candidates,
        key=lambda item: (-int(item["file_count"]), -len(str(item["company_group_name"])), str(item["company_group_name"])),
    )

    canonical_groups: list[Dict[str, Any]] = []
    alias_map: Dict[str, Dict[str, str]] = {}
    for group in sorted_groups:
        match = next(
            (
                canonical
                for canonical in canonical_groups
                if should_merge_company_alias(group["company_group_name"], canonical["company_group_name"])
            ),
            None,
        )
        if match is None:
            canonical_groups.append(group)
            alias_map[group["company_group_key"]] = {
                "company_group_key": str(group["company_group_key"]),
                "company_group_name": str(group["company_group_name"]),
            }
            continue

        alias_map[group["company_group_key"]] = {
            "company_group_key": str(match["company_group_key"]),
            "company_group_name": str(match["company_group_name"]),
        }

    raw_count = len(sorted_groups)
    canonical_count = len(canonical_groups)
    return alias_map, {
        "raw_group_count": raw_count,
        "canonical_group_count": canonical_count,
        "merged_group_count": max(raw_count - canonical_count, 0),
    }
