"""
펀드/포트폴리오/컴플라이언스 대시보드용 데이터 로더 및 정규화
- CSV 또는 Airtable 다중 탭을 동일 스키마로 로드
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

import os
import pandas as pd
import streamlit as st

from shared.airtable_multi import (
    airtable_enabled,
    load_airtable_tables,
    load_airtable_tables_with_status,
)
from shared.logging_config import get_logger

logger = get_logger("fund_dashboard_data")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV_DIR = PROJECT_ROOT / "temp"

DEFAULT_TABLE_MAP = {
    "funds": "투자조합-펀드 리스트",
    "obligations": "의무 투자",
    "portfolio": "포폴사 결산 자료",
}

DEFAULT_CSV_FILES = {
    "funds": "투자조합-펀드 리스트.csv",
    "obligations": "의무 투자-Grid view.csv",
    "portfolio": "포폴사 결산 자료-Grid view.csv",
}


def get_dashboard_table_map(defaults: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Airtable 테이블명 설정 (env/secrets 우선 적용)"""
    table_map = (defaults or DEFAULT_TABLE_MAP).copy()
    def _first(*values: Optional[str]) -> Optional[str]:
        for value in values:
            if value:
                return value
        return None

    env_overrides = {
        "funds": _first(
            os.getenv("AIRTABLE_FUND_TABLE_ID"),
            os.getenv("AIRTABLE_FUND_TABLE"),
            os.getenv("AIRTABLE_FUND_TABLE_NAME"),
        ),
        "obligations": _first(
            os.getenv("AIRTABLE_OBLIGATION_TABLE_ID"),
            os.getenv("AIRTABLE_OBLIGATION_TABLE"),
            os.getenv("AIRTABLE_OBLIGATION_TABLE_NAME"),
        ),
        "portfolio": _first(
            os.getenv("AIRTABLE_PORTFOLIO_TABLE_ID"),
            os.getenv("AIRTABLE_PORTFOLIO_TABLE"),
            os.getenv("AIRTABLE_PORTFOLIO_TABLE_NAME"),
        ),
    }
    for key, value in env_overrides.items():
        if value:
            table_map[key] = value

    try:
        if hasattr(st, "secrets"):
            table_map["funds"] = _first(
                st.secrets.get("AIRTABLE_FUND_TABLE_ID"),
                st.secrets.get("AIRTABLE_FUND_TABLE"),
                st.secrets.get("AIRTABLE_FUND_TABLE_NAME"),
                table_map["funds"],
            )
            table_map["obligations"] = _first(
                st.secrets.get("AIRTABLE_OBLIGATION_TABLE_ID"),
                st.secrets.get("AIRTABLE_OBLIGATION_TABLE"),
                st.secrets.get("AIRTABLE_OBLIGATION_TABLE_NAME"),
                table_map["obligations"],
            )
            table_map["portfolio"] = _first(
                st.secrets.get("AIRTABLE_PORTFOLIO_TABLE_ID"),
                st.secrets.get("AIRTABLE_PORTFOLIO_TABLE"),
                st.secrets.get("AIRTABLE_PORTFOLIO_TABLE_NAME"),
                table_map["portfolio"],
            )
    except Exception as exc:
        logger.debug("Streamlit secrets 읽기 실패: %s", exc)

    return table_map


def normalize_table_ref(value: str) -> str:
    """Airtable 테이블 참조 정규화 (URL/ID/이름 허용)"""
    if not value:
        return value
    text = str(value).strip()
    # URL 형태: https://airtable.com/app.../tblXXXX/...
    match = re.search(r"/(tbl[A-Za-z0-9]+)/", text)
    if match:
        return match.group(1)
    # table ID 형태
    if text.startswith("tbl") and len(text) >= 10:
        return text
    return text


def normalize_table_map(table_map: Dict[str, str]) -> Dict[str, str]:
    return {key: normalize_table_ref(value) for key, value in table_map.items()}


@dataclass
class DashboardData:
    source: str
    funds: pd.DataFrame
    obligations: pd.DataFrame
    portfolio: pd.DataFrame
    debug: Dict[str, Dict[str, object]] = field(default_factory=dict)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.fillna("")
    df.columns = [str(col).replace("\n", " ").strip() for col in df.columns]
    return df


def _normalize_join_key(value: str) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", "", text)
    return text


def _extract_record_ids(value: object) -> list[str]:
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    if isinstance(value, str):
        return re.findall(r"rec[A-Za-z0-9]+", value)
    return []


def _resolve_fund_names(value: object, id_to_name: Dict[str, str]) -> list[str]:
    ids = _extract_record_ids(value)
    if ids:
        names = [id_to_name.get(rec_id) for rec_id in ids if id_to_name.get(rec_id)]
        if names:
            return names
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    return [text] if text else []


def _to_number(value: object) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    text = text.replace(",", "")
    text = text.replace("(", "-").replace(")", "")
    text = re.sub(r"[^0-9.\-]", "", text)
    if not text or text == "-":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_percent(value: object) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    text = text.replace("%", "")
    return _to_number(text)


def _coerce_numeric(df: pd.DataFrame, columns: Iterable[str], percent_columns: Iterable[str] = ()) -> pd.DataFrame:
    for col in columns:
        if col in df.columns:
            df[col + "_num"] = df[col].apply(_to_number)
    for col in percent_columns:
        if col in df.columns:
            df[col + "_num"] = df[col].apply(_to_percent)
    return df


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        logger.warning("CSV 파일을 찾을 수 없습니다: %s", path)
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        df = pd.read_csv(path)
    return _normalize_columns(df)


@st.cache_data(ttl=600, show_spinner="펀드 데이터 로드 중...")
def _load_from_csv(csv_dir: str) -> Dict[str, pd.DataFrame]:
    base = Path(csv_dir)
    data = {
        key: _load_csv(base / filename)
        for key, filename in DEFAULT_CSV_FILES.items()
    }
    return data


def _load_from_csv_with_debug(csv_dir: str) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Dict[str, object]]]:
    base = Path(csv_dir)
    data = _load_from_csv(str(base))
    debug: Dict[str, Dict[str, object]] = {}
    for key, filename in DEFAULT_CSV_FILES.items():
        path = base / filename
        df = data.get(key, pd.DataFrame())
        debug[key] = {
            "file": str(path),
            "exists": path.exists(),
            "rows": len(df),
            "columns": list(df.columns)[:6],
        }
    return data, debug


@st.cache_data(ttl=600, show_spinner="펀드 데이터 로드 중...")
def _load_from_airtable(table_map: Tuple[Tuple[str, str], ...]) -> Dict[str, pd.DataFrame]:
    table_map_dict = dict(table_map)
    raw = load_airtable_tables(table_map_dict.values())
    data = {}
    for key, table_name in table_map_dict.items():
        data[key] = raw.get(table_name, pd.DataFrame())
    return data


def _load_from_airtable_with_debug(
    table_map: Tuple[Tuple[str, str], ...],
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Dict[str, object]]]:
    table_map_dict = dict(table_map)
    raw, status = load_airtable_tables_with_status(table_map_dict.values())
    data = {}
    debug: Dict[str, Dict[str, object]] = {}
    for key, table_name in table_map_dict.items():
        df = raw.get(table_name, pd.DataFrame())
        data[key] = df
        table_status = status.get(table_name, {})
        debug[key] = {
            "table": table_name,
            "rows": len(df),
            "status_code": table_status.get("status_code"),
            "error": table_status.get("error"),
            "columns": list(df.columns)[:6],
        }
    return data, debug


def load_dashboard_tables(
    source: str = "auto",
    csv_dir: Optional[Path] = None,
    table_map: Optional[Dict[str, str]] = None,
) -> DashboardData:
    """대시보드용 테이블 로드 (CSV or Airtable)"""
    source = (source or "auto").lower()
    csv_dir = csv_dir or DEFAULT_CSV_DIR
    table_map = table_map or DEFAULT_TABLE_MAP

    used_source = source
    data: Dict[str, pd.DataFrame]
    debug: Dict[str, Dict[str, object]] = {}

    if source == "auto":
        if airtable_enabled():
            used_source = "airtable"
        else:
            used_source = "csv"

    if used_source == "airtable":
        data, debug = _load_from_airtable_with_debug(tuple(table_map.items()))
    else:
        data, debug = _load_from_csv_with_debug(str(csv_dir))
        used_source = "csv"

    return DashboardData(
        source=used_source,
        funds=data.get("funds", pd.DataFrame()),
        obligations=data.get("obligations", pd.DataFrame()),
        portfolio=data.get("portfolio", pd.DataFrame()),
        debug=debug,
    )


def get_airtable_debug(table_map: Optional[Dict[str, str]] = None) -> Dict[str, Dict[str, object]]:
    """Airtable 테이블 상태만 확인 (로딩 실패/상태코드/컬럼 확인용)"""
    table_map = table_map or DEFAULT_TABLE_MAP
    _, debug = _load_from_airtable_with_debug(tuple(table_map.items()))
    return debug


def prepare_dashboard_views(data: DashboardData) -> Dict[str, pd.DataFrame]:
    """정규화/조인/집계 결과 반환"""
    funds = _normalize_columns(data.funds.copy())
    obligations = _normalize_columns(data.obligations.copy())
    portfolio = _normalize_columns(data.portfolio.copy())

    funds = _coerce_numeric(
        funds,
        columns=[
            "약정총액",
            "총 투자금액(누적)",
            "회수원금",
            "회수수익",
            "multiple(x) (투자수익배수)",
        ],
    )
    obligations = _coerce_numeric(
        obligations,
        columns=["기준 금액", "투자금액", "미달성 금액(-는 달성완료임)"],
        percent_columns=["달성율(약정총액기준)"],
    )
    portfolio = _coerce_numeric(
        portfolio,
        columns=[
            "매출액 (백만원)",
            "영업이익 (백만원)",
            "당기손익 (백만원)",
            "자산총계 (백만원)",
            "부채총계 (백만원)",
            "자본총계 (백만원)",
            "자본금 (백만원)",
            "고용인원(명)",
        ],
    )

    if "투자 조합명" in funds.columns:
        funds["join_key"] = funds["투자 조합명"].apply(_normalize_join_key)
    else:
        funds["join_key"] = ""

    id_to_name: Dict[str, str] = {}
    if "_record_id" in funds.columns and "투자 조합명" in funds.columns:
        id_to_name = {
            str(row["_record_id"]): str(row["투자 조합명"]).strip()
            for _, row in funds.iterrows()
            if row.get("_record_id") and str(row.get("투자 조합명", "")).strip()
        }

    if "투자조합 정보" in obligations.columns:
        obligations["fund_names"] = obligations["투자조합 정보"].apply(
            lambda value: _resolve_fund_names(value, id_to_name)
        )
        obligations["펀드명"] = obligations["fund_names"].apply(
            lambda names: ", ".join(names) if names else ""
        )
        obligations["join_key"] = obligations["펀드명"].apply(_normalize_join_key)
    else:
        obligations["join_key"] = ""

    obligations["compliance_status"] = _classify_compliance(obligations)

    compliance_summary = _aggregate_compliance(obligations)
    funds_with_compliance = funds.merge(
        compliance_summary,
        on="join_key",
        how="left",
        suffixes=("", "_compliance"),
    )

    portfolio_latest = _latest_portfolio_snapshot(portfolio)

    return {
        "funds": funds,
        "obligations": obligations,
        "funds_with_compliance": funds_with_compliance,
        "compliance_summary": compliance_summary,
        "portfolio_latest": portfolio_latest,
    }


def _classify_compliance(obligations: pd.DataFrame) -> pd.Series:
    statuses = []
    for _, row in obligations.iterrows():
        miss = row.get("미달성 금액(-는 달성완료임)_num")
        rate = row.get("달성율(약정총액기준)_num")

        if miss is not None and miss < 0:
            statuses.append("달성")
            continue
        if rate is not None:
            if rate >= 100:
                statuses.append("달성")
            elif rate >= 80:
                statuses.append("주의")
            else:
                statuses.append("미달")
            continue
        statuses.append("미확인")
    return pd.Series(statuses)


def _aggregate_compliance(obligations: pd.DataFrame) -> pd.DataFrame:
    if obligations.empty:
        return pd.DataFrame(
            columns=[
                "join_key",
                "펀드명",
                "의무투자_건수",
                "투자금액_합계",
                "기준금액_합계",
                "최소_달성율",
                "최대_미달성금액",
                "compliance_status",
            ]
        )

    grouped = obligations.groupby("join_key", dropna=False)
    name_col = "펀드명" if "펀드명" in obligations.columns else "투자조합 정보"
    summary = grouped.agg(
        펀드명=(name_col, "first"),
        의무투자_건수=("의무투자", "count"),
        투자금액_합계=("투자금액_num", "sum"),
        기준금액_합계=("기준 금액_num", "sum"),
        최소_달성율=("달성율(약정총액기준)_num", "min"),
        최대_미달성금액=("미달성 금액(-는 달성완료임)_num", "max"),
    ).reset_index()

    status_map = {}
    for key, group in grouped:
        if any(group["compliance_status"] == "미달"):
            status_map[key] = "미달"
        elif any(group["compliance_status"] == "주의"):
            status_map[key] = "주의"
        elif any(group["compliance_status"] == "달성"):
            status_map[key] = "달성"
        else:
            status_map[key] = "미확인"

    summary["compliance_status"] = summary["join_key"].map(status_map)
    return summary


def _latest_portfolio_snapshot(portfolio: pd.DataFrame) -> pd.DataFrame:
    if portfolio.empty or "법인명" not in portfolio.columns:
        return portfolio

    if "제출일" in portfolio.columns:
        portfolio["제출일_dt"] = pd.to_datetime(portfolio["제출일"], errors="coerce")
    else:
        portfolio["제출일_dt"] = pd.NaT

    portfolio_sorted = portfolio.sort_values("제출일_dt", ascending=True)
    latest = portfolio_sorted.groupby("법인명", dropna=False).tail(1)
    return latest
