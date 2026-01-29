"""
Airtable 초기화된 투자기업 포트폴리오 조회 모듈

**새로운 아키텍처 (2026-01-29):**
- Airtable SEARCH() 문법은 한국어 텍스트에서 작동하지 않음
- 대신: 모든 데이터를 한 번 가져와서 pandas DataFrame으로 캐싱
- 모든 검색은 pandas 연산으로 수행 (str.contains, isin 등)
- Airtable API는 데이터 fetch만 담당, 검색 로직은 pandas가 담당
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
    "키워드\n(Business)",  # 실제 Airtable 컬럼명 (줄바꿈 포함)
    "키워드\n(Social Impact)",  # 실제 Airtable 컬럼명 (줄바꿈 포함)
    "대표자명",
    "투자포인트",
    "투자금액",  # 투자금액 검색 지원 추가
]

AIRTABLE_MAX_PAGE_SIZE = 100


def _ensure_data_file() -> Optional[Path]:
    return DATA_FILE if DATA_FILE.exists() else None


def _get_airtable_config() -> Tuple[Optional[str], Optional[str], str]:
    key = os.getenv("AIRTABLE_API_KEY")
    base = os.getenv("AIRTABLE_BASE_ID")
    table = os.getenv("AIRTABLE_TABLE_NAME") or "투자기업"

    try:
        import streamlit as st

        # Streamlit secrets에서 확인
        try:
            if hasattr(st, "secrets"):
                key = key or st.secrets.get("AIRTABLE_API_KEY")
                base = base or st.secrets.get("AIRTABLE_BASE_ID")
                table = table or st.secrets.get("AIRTABLE_TABLE_NAME") or table
        except Exception as e:
            logger.debug(f"Streamlit secrets 읽기 실패: {e}")

        # 세션 상태에서도 확인 (로그인 시 저장된 API 키)
        try:
            if hasattr(st, "session_state"):
                key = key or st.session_state.get("airtable_api_key")
                base = base or st.session_state.get("airtable_base_id")
                table = table or st.session_state.get("airtable_table_name") or table
        except Exception as e:
            logger.debug(f"Session state 읽기 실패: {e}")

    except Exception as e:
        logger.debug(f"Streamlit import 실패: {e}")

    if key and base:
        logger.debug(f"Airtable config loaded: base={base}, table={table}, key={'***' + key[-8:] if key else 'None'}")
    else:
        logger.debug("Airtable config not found, will use CSV fallback")

    return key, base, table


def _airtable_enabled() -> bool:
    key, base, _ = _get_airtable_config()
    return bool(key and base)


@lru_cache(maxsize=1)
def _load_csv_dataframe() -> pd.DataFrame:
    """CSV 파일에서 DataFrame 로드 (fallback용)"""
    path = _ensure_data_file()
    if not path:
        return pd.DataFrame(columns=SEARCH_COLUMNS)
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [col.replace("\n", " ").strip() for col in df.columns]
    df = df.fillna("")
    return df


@lru_cache(maxsize=1)
def _fetch_all_airtable_records_as_dataframe() -> pd.DataFrame:
    """
    Airtable에서 모든 레코드를 가져와 pandas DataFrame으로 캐싱
    페이징 처리로 전체 데이터 로드 (289개 기업 전체)
    """
    key, base, table = _get_airtable_config()

    if not key or not base:
        logger.debug("Airtable 설정 없음, CSV fallback 사용")
        return _load_csv_dataframe()

    url = f"https://api.airtable.com/v0/{base}/{table}"
    headers = {"Authorization": f"Bearer {key}"}

    all_records = []
    offset = None

    try:
        # 페이징 처리로 모든 데이터 가져오기
        while True:
            params: Dict[str, Any] = {"pageSize": 100}
            if offset:
                params["offset"] = offset

            logger.debug(f"Airtable fetch (offset={offset})")
            response = requests.get(url, headers=headers, params=params, timeout=15)

            if response.status_code != 200:
                logger.warning(f"Airtable 응답 오류: {response.text[:500]}")
                break

            response.raise_for_status()
            payload = response.json()

            records = payload.get("records", [])
            for entry in records:
                fields = entry.get("fields", {})
                all_records.append({
                    k: str(v).strip() if v not in (None, float("nan")) else ""
                    for k, v in fields.items()
                })

            offset = payload.get("offset")
            if not offset:
                break  # 더 이상 페이지 없음

        logger.info(f"Airtable에서 총 {len(all_records)}개 레코드 로드 완료")

        if not all_records:
            logger.warning("Airtable 레코드가 비어있음, CSV fallback 사용")
            return _load_csv_dataframe()

        # DataFrame 생성 및 정규화
        df = pd.DataFrame(all_records)
        df = df.fillna("")

        # 컬럼명 정규화 (줄바꿈 제거)
        df.columns = [col.replace("\n", " ").strip() for col in df.columns]

        return df

    except Exception as exc:
        logger.warning(f"Airtable 데이터 로드 실패: {exc}, CSV fallback 사용")
        return _load_csv_dataframe()


def _get_cached_dataframe() -> pd.DataFrame:
    """
    메모리에 캐싱된 DataFrame 반환
    Airtable 우선, 실패 시 CSV fallback
    """
    if _airtable_enabled():
        return _fetch_all_airtable_records_as_dataframe()
    return _load_csv_dataframe()


def get_portfolio_columns() -> List[str]:
    """사용자에게 표시할 수 있는 컬럼 리스트"""
    df = _get_cached_dataframe()
    return df.columns.tolist()


# ==========================================
# DEPRECATED 함수들 (Airtable SEARCH() 문법 사용)
# 2026-01-29: pandas 기반 검색으로 완전 전환
# ==========================================

def _escape_airtable_value(value: str) -> str:
    """DEPRECATED: Airtable formula용 이스케이프 (더 이상 사용 안 함)"""
    return value.replace('"', '\\"').replace("'", "\\'")


def _build_airtable_formula(query: Optional[str], filters: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    DEPRECATED: Airtable SEARCH() formula 생성
    한국어 텍스트에서 작동하지 않아 사용 중단
    """
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
        query_lower = query.strip().lower()
        if query_lower:
            ors = []
            for column in SEARCH_COLUMNS:
                ors.append(f"SEARCH(\"{_escape_airtable_value(query_lower)}\", LOWER({{{column}}}))")
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
    """
    DEPRECATED: Airtable API 직접 호출로 검색
    한국어 SEARCH() 문제로 사용 중단
    대신 _fetch_all_airtable_records_as_dataframe() 사용
    """
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
        logger.debug(f"Airtable formula: {formula[:200]}...")
    if sort_by:
        params["sort[0][field]"] = sort_by
        params["sort[0][direction]"] = "asc" if sort_order.lower() == "asc" else "desc"

    try:
        logger.debug(f"Airtable request params: {params}")
        response = requests.get(url, headers=headers, params=params, timeout=15)
        logger.debug(f"Airtable response status: {response.status_code}")
        if response.status_code != 200:
            logger.warning(f"Airtable response error: {response.text[:500]}")
        response.raise_for_status()
    except Exception as exc:
        logger.warning("Airtable 요청 실패: %s", exc)
        return []

    payload = response.json()
    raw_records = payload.get("records", []) or []
    logger.debug(f"Airtable returned {len(raw_records)} records")
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
    """
    텍스트 검색 (pandas str.contains 사용)
    기업명 검색 시 정규화된 변형도 자동으로 검색
    """
    if not query:
        return df
    query_lower = query.strip().lower()
    if not query_lower:
        return df

    # 기업명 정규화 변형 생성 (㈜ ↔ (주) ↔ 주식회사)
    query_variants = [query_lower]
    try:
        from shared.company_name_normalizer import normalize_company_name
        variants = normalize_company_name(query)
        query_variants.extend([v.lower() for v in variants if v.lower() not in query_variants])
    except Exception as e:
        logger.debug(f"기업명 정규화 실패: {e}")

    masks = []
    for column in SEARCH_COLUMNS:
        if column not in df.columns:
            continue
        column_series = df[column].astype(str).str.lower()

        # 각 변형에 대해 검색
        for variant in query_variants:
            masks.append(column_series.str.contains(variant, regex=False, na=False))

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
    투자기업 조회 (완전 pandas 기반)

    **새로운 아키텍처:**
    - Airtable/CSV에서 모든 데이터를 한 번 로드 (캐싱됨)
    - 모든 검색/필터링은 pandas 연산으로 수행
    - 기업명 정규화 자동 적용 (㈜ ↔ (주) ↔ 주식회사)

    Args:
        query: 텍스트 검색어
        filters: 컬럼별 필터 (예: {"카테고리1": "AI"})
        limit: 최대 결과 수
        sort_by: 정렬 컬럼
        sort_order: "asc" 또는 "desc"

    Returns:
        검색 결과 레코드 리스트
    """
    # 1. 캐싱된 DataFrame 가져오기 (Airtable 또는 CSV)
    df = _get_cached_dataframe()

    logger.debug(f"검색 시작 - query={query}, filters={filters}, 전체={len(df)}개")

    # 2. 필터 적용
    df = _apply_filters(df, filters or {})
    logger.debug(f"필터 적용 후: {len(df)}개")

    # 3. 텍스트 검색 (기업명 정규화 포함)
    df = _apply_query_mask(df, query or "")
    logger.debug(f"텍스트 검색 후: {len(df)}개")

    # 4. 정렬
    df = _order_dataframe(df, sort_by, sort_order)

    # 5. 제한
    if limit is None:
        limit = DEFAULT_LIMIT
    result_rows = df.head(limit)

    # 6. Dict 형태로 변환
    results = [_normalize_record(row) for _, row in result_rows.iterrows()]
    logger.debug(f"최종 결과: {len(results)}개 반환")

    return results


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
