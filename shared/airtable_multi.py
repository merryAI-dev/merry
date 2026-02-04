"""
Airtable 다중 테이블 로더
- 여러 테이블을 한번에 로드하여 pandas DataFrame으로 반환
- Streamlit 캐시로 세션/TTL 기반 재사용
"""
from __future__ import annotations

import os
from typing import Dict, Iterable, Optional, Tuple
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st

from shared.logging_config import get_logger

logger = get_logger("airtable_multi")

AIRTABLE_MAX_PAGE_SIZE = 100
PLACEHOLDER_VALUES = {
    "key": "pat_placeholder_value",
    "base": "app_placeholder_value",
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.fillna("")
    df.columns = [str(col).replace("\n", " ").strip() for col in df.columns]
    return df


def _is_placeholder(key: Optional[str], base: Optional[str]) -> bool:
    if key and key == PLACEHOLDER_VALUES["key"]:
        return True
    if base and base == PLACEHOLDER_VALUES["base"]:
        return True
    return False


def get_airtable_config() -> Tuple[Optional[str], Optional[str]]:
    key = os.getenv("AIRTABLE_API_KEY")
    base = os.getenv("AIRTABLE_BASE_ID")

    try:
        if hasattr(st, "secrets"):
            key = key or st.secrets.get("AIRTABLE_API_KEY")
            base = base or st.secrets.get("AIRTABLE_BASE_ID")
    except Exception as exc:
        logger.debug("Streamlit secrets 읽기 실패: %s", exc)

    try:
        if hasattr(st, "session_state"):
            key = key or st.session_state.get("airtable_api_key")
            base = base or st.session_state.get("airtable_base_id")
    except Exception as exc:
        logger.debug("Session state 읽기 실패: %s", exc)

    if key and base and not _is_placeholder(key, base):
        logger.debug("Airtable config loaded: base=%s, key=***%s", base, key[-8:])
    else:
        logger.debug("Airtable config not found, will skip Airtable")

    return key, base


def airtable_enabled() -> bool:
    key, base = get_airtable_config()
    return bool(key and base)


@st.cache_data(ttl=600, show_spinner="Airtable 데이터 로드 중...")
def _fetch_airtable_tables_cached(
    base_id: str,
    api_key: str,
    table_names: Tuple[str, ...],
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Dict[str, object]]]:
    """여러 테이블을 Airtable에서 로드하고 상태 정보를 함께 반환"""
    headers = {"Authorization": f"Bearer {api_key}"}
    results: Dict[str, pd.DataFrame] = {}
    status: Dict[str, Dict[str, object]] = {}

    for table in table_names:
        table_encoded = quote(table, safe="")
        url = f"https://api.airtable.com/v0/{base_id}/{table_encoded}"
        all_records = []
        offset = None
        error_text = None
        status_code = None

        try:
            while True:
                params = {"pageSize": AIRTABLE_MAX_PAGE_SIZE}
                if offset:
                    params["offset"] = offset

                resp = requests.get(url, headers=headers, params=params, timeout=15)
                status_code = resp.status_code
                if resp.status_code != 200:
                    error_text = resp.text[:300]
                    logger.warning("Airtable 응답 오류(%s): %s", table, error_text)
                    break
                resp.raise_for_status()
                payload = resp.json()

                records = payload.get("records", [])
                for entry in records:
                    fields = entry.get("fields", {})
                    all_records.append({
                        k: str(v).strip() if v not in (None, float("nan")) else ""
                        for k, v in fields.items()
                    })

                offset = payload.get("offset")
                if not offset:
                    break

            df = pd.DataFrame(all_records)
            df = _normalize_columns(df)
            results[table] = df
            status[table] = {
                "rows": len(df),
                "status_code": status_code,
                "error": error_text,
            }
            logger.info("Airtable 테이블 로드 완료: %s (%d rows)", table, len(df))

        except Exception as exc:
            logger.warning("Airtable 테이블 로드 실패(%s): %s", table, exc)
            results[table] = pd.DataFrame()
            status[table] = {
                "rows": 0,
                "status_code": status_code,
                "error": str(exc),
            }

    return results, status


def fetch_airtable_tables(
    base_id: str,
    api_key: str,
    table_names: Tuple[str, ...],
) -> Dict[str, pd.DataFrame]:
    """여러 테이블을 Airtable에서 로드하여 DataFrame dict 반환"""
    results, _ = _fetch_airtable_tables_cached(base_id, api_key, table_names)
    return results


def fetch_airtable_tables_with_status(
    base_id: str,
    api_key: str,
    table_names: Tuple[str, ...],
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Dict[str, object]]]:
    """여러 테이블을 Airtable에서 로드하여 DataFrame + 상태 반환"""
    return _fetch_airtable_tables_cached(base_id, api_key, table_names)


def load_airtable_tables(table_names: Iterable[str]) -> Dict[str, pd.DataFrame]:
    """Airtable 설정을 읽고 테이블 로드 (설정 없으면 빈 dict)"""
    key, base = get_airtable_config()
    if not key or not base:
        return {}
    names = tuple(table_names)
    if not names:
        return {}
    return fetch_airtable_tables(base_id=base, api_key=key, table_names=names)


def load_airtable_tables_with_status(
    table_names: Iterable[str],
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Dict[str, object]]]:
    key, base = get_airtable_config()
    if not key or not base:
        return {}, {}
    names = tuple(table_names)
    if not names:
        return {}, {}
    return fetch_airtable_tables_with_status(base_id=base, api_key=key, table_names=names)
