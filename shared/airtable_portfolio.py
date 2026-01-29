"""
Airtable 초기화된 투자기업 포트폴리오 조회 모듈
기본적으로 로컬 CSV를 사용하지만, 환경 변수 또는 secrets에 Airtable API 키/베이스/테이블이 있으면
AirTable REST API로 실시간 조회를 수행하고 CSV는 fallback으로 동작합니다.
"""

from __future__ import annotations

import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

from shared.logging_config import get_logger

logger = get_logger("airtable_portfolio")

DATA_FILE = Path(__file__).resolve().parent.parent / "투자기업-Grid view.csv"
DEFAULT_LIMIT = 5
SEARCH_COLUMNS = [
    "기업명",
    "제품/서비스",
    "카테고리1",
    "카테고리2",
    "SDGs",
    "Exit방안",
    "Investment Summary",
    "키워드 (Business)",
    "키워드 (Social Impact)",
    "대표자명",
    "투자포인트",
]

AIRTABLE_MAX_PAGE_SIZE = 100


def _ensure_data_file() -> Optional[Path]:
    if not DATA_FILE.exists():
        return None
    return DATA_FILE


def _get_airtable_config() -> Tuple[Optional[str], Optional[str], str]:
    key = os.getenv("AIRTABLE_API_KEY")
    base = os.getenv("AIRTABLE_BASE_ID")
    table = os.getenv("AIRTABLE_TABLE_NAME") or "투자기업"
    try:
        import streamlit as st

        secrets = getattr(st, "secrets", None) or {}
        key = key or secrets.get("AIRTABLE_API_KEY") or secrets.get("airtable_api_key") or secrets.get("airtable", {}).get("api_key")
        base = base or secrets.get("AIRTABLE_BASE_ID") or secrets.get("airtable_base_id") or secrets.get("airtable", {}).get("base_id")
        table = table or secrets.get("AIRTABLE_TABLE_NAME") or secrets.get("airtable_table_name") or secrets.get("airtable", {}).get("table_name") or table
    except Exception:
        pass
    return key, base, table


def _airtable_enabled() -> bool:
    key, base, _ = _get_airtable_config()
    return bool(key and base)


@lru_cache(maxsize=1)
def _load_dataframe() -> pd.DataFrame:
    path = _ensure_data_file()
    if not path:
        return pd.DataFrame(columns=SEARCH_COLUMNS)
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [col.replace("\n", " ").strip() for col in df.columns]
    df = df.fillna("")
    return df


def get_portfolio_columns() -> List[str]:
    """사용자에게 표시할 수 있는 컬럼 리스트"""
    if _airtable_enabled():
        columns = _get_airtable_columns()
        if columns:
            return columns
    return _load_dataframe().columns.tolist()


@lru_cache(maxsize=1)
def _get_airtable_columns() -> List[str]:
    records = _fetch_airtable_records(limit=1)
    if not records:
        return []
    first = records[0]
    return list(first.keys())


def _escape_airtable_value(value: str) -> str:
    return value.replace('"', '\\"').replace("'", "\\'")


def _build_airtable_formula(query: Optional[str], filters: Optional[Dict[str, Any]]) -> Optional[str]:
    clauses = []

    if filters:
        for column, value in filters.items():
            if not column or value is None:
                continue
            if isinstance(value, (list, tuple)):
                inner = [
                    f"{{{column}}} = \"{_escape_airtable_value(str(item))}\""
                    for item in value
                ]
                if inner:
                    clauses.append(f"OR({', '.join(inner)})")
            else:
                clauses.append(f"{{{column}}} = \"{_escape_airtable_value(str(value))}\"")

    if query:
        query_lower = query.strip()
        if query_lower:
            ors = []
            for column in SEARCH_COLUMNS:
                ors.append(f"FIND(\"{_escape_airtable_value(query_lower)}\", {{{column}}})")
            clauses.append(f"OR({', '.join(ors)})")

    if not clauses:
        return None

    if len(clauses) == 1:
        return clauses[0]

    return f"AND({', '.join(clauses)})"


def _fetch_airtable_records(
    query: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "desc",
) -> List[Dict[str, str]]:
    key, base, table = _get_airtable_config()

    if not key or not base:
        return []

    url = f"https://api.airtable.com/v0/{base}/{table}"
    headers = {"Authorization": f"Bearer {key}"}
    params: Dict[str, Any] = {}
    page_size = min(limit if limit else DEFAULT_LIMIT, AIRTABLE_MAX_PAGE_SIZE)
    params["pageSize"] = page_size
    formula = _build_airtable_formula(query=query, filters=filters)
    if formula:
        params["filterByFormula"] = formula
    if sort_by:
        params["sort[0][field]"] = sort_by
        params["sort[0][direction]"] = "asc" if sort_order.lower() == "asc" else "desc"

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
    except Exception as exc:
        logger.warning("Airtable 요청 실패: %s", exc)
        return []

    payload = response.json()
    raw_records = payload.get("records", []) or []
    normalized = []
    for entry in raw_records[: limit or DEFAULT_LIMIT]:
        fields = entry.get("fields", {})
        normalized.append({k: str(v).strip() if v not in (None, float("nan")) else "" for k, v in fields.items()})
    return normalized


def _normalize_record(record: Dict[str, Any]) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    for column, value in record.items():
        if value is None or (isinstance(value, float) and math.isnan(value)):
            normalized[column] = ""
        else:
            normalized[column] = str(value).strip()
    return normalized


def _apply_filters(df: pd.DataFrame, filters: Dict[str, Any]) -> pd.DataFrame:
    if not filters:
        return df

    mask = pd.Series(True, index=df.index)
    for column, value in filters.items():
        if column not in df.columns:
            continue
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        values = value if isinstance(value, (list, tuple)) else [value]
        values = [str(v).strip().lower() for v in values if str(v).strip()]
        if not values:
            continue
        column_series = df[column].astype(str).str.lower()
        column_mask = column_series.isin(values)
        mask &= column_mask
    return df[mask]


def _apply_query_mask(df: pd.DataFrame, query: str) -> pd.DataFrame:
    if not query:
        return df
    query_lower = query.strip().lower()
    if not query_lower:
        return df

    masks = []
    for column in SEARCH_COLUMNS:
        if column not in df.columns:
            continue
        column_series = df[column].astype(str).str.lower()
        masks.append(column_series.str.contains(query_lower, regex=False, na=False))
    if not masks:
        return df

    combined = masks[0].copy()
    for mask in masks[1:]:
        combined |= mask
    return df[combined]


def _order_dataframe(
    df: pd.DataFrame,
    sort_by: Optional[str],
    sort_order: str,
) -> pd.DataFrame:
    if not sort_by or sort_by not in df.columns:
        return df
    ascending = sort_order.lower() != "desc"
    try:
        return df.sort_values(by=sort_by, ascending=ascending, kind="mergesort")
    except Exception:
        return df


def search_portfolio_records(
    query: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "desc",
) -> List[Dict[str, str]]:
    """
    투자기업 조회. Airtable이 활성화된 경우 REST 호출, 아니면 CSV 검색.
    """
    if _airtable_enabled():
        records = _fetch_airtable_records(
            query=query,
            filters=filters or {},
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return [_normalize_record(record) for record in records]

    df = _load_dataframe()
    df = _apply_filters(df, filters or {})
    df = _apply_query_mask(df, query or "")
    df = _order_dataframe(df, sort_by, sort_order)
    if limit is None:
        limit = DEFAULT_LIMIT
    result_rows = df.head(limit)
    return [_normalize_record(row) for _, row in result_rows.iterrows()]


def summarize_portfolio_records(
    records: List[Dict[str, str]],
    query: str = "",
    filters: Optional[Dict[str, Any]] = None,
) -> str:
    """검색 결과 요약 텍스트"""
    if not records:
        return "조건에 맞는 투자기업을 찾을 수 없습니다."

    names = [rec.get("기업명") for rec in records if rec.get("기업명")]
    unique_names = []
    for name in names:
        if name and name not in unique_names:
            unique_names.append(name)
        if len(unique_names) >= 3:
            break

    parts = [
        f"전체 {len(records)}개 결과 ({'검색어: ' + query if query else '검색어 없음'})",
    ]
    if filters:
        filter_desc = ", ".join(
            f"{col}={','.join(map(str, val if isinstance(val, (list, tuple)) else [val]))}"
            for col, val in filters.items()
            if val
        )
        if filter_desc:
            parts.append(f"필터: {filter_desc}")

    if unique_names:
        parts.append(f"예시 기업: {', '.join(unique_names)}")

    return " · ".join(parts)
