"""
펀드별/기업별 상세 뷰
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import altair as alt
import pandas as pd
import streamlit as st

from shared.auth import check_authentication
from shared.config import initialize_agent, initialize_session_state, inject_custom_css
from shared.sidebar import render_sidebar
from shared.fund_dashboard_data import (
    load_dashboard_tables,
    prepare_dashboard_views,
    DEFAULT_TABLE_MAP,
    get_dashboard_table_map,
    normalize_table_map,
    build_fund_company_map_combined,
    filter_portfolio_by_companies,
    to_display_dataframe,
)
from shared.airtable_multi import airtable_enabled

PROJECT_ROOT = Path(__file__).resolve().parent.parent

st.set_page_config(
    page_title="펀드/기업 상세 | 메리",
    page_icon="image-removebg-preview-5.png",
    layout="wide",
)

initialize_session_state()
check_authentication()
initialize_agent()
inject_custom_css()
render_sidebar(mode="collab")

st.markdown(
    """
    <style>
    @keyframes swoosh {
        0% { opacity: 0; transform: translateY(16px) scale(0.98); }
        100% { opacity: 1; transform: translateY(0) scale(1); }
    }
    .reveal { animation: swoosh 0.6s ease-out both; }
    .summary-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
        margin-bottom: 12px;
    }
    .summary-card {
        background: linear-gradient(135deg, #ffffff, #f7f4ef);
        border-radius: 14px;
        border: 1px solid rgba(31, 26, 20, 0.08);
        padding: 12px 14px;
        box-shadow: 0 10px 22px rgba(25, 18, 9, 0.08);
        min-height: 76px;
    }
    .summary-label {
        font-size: 12px;
        color: #6b5f53;
        margin-bottom: 6px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    .summary-value {
        font-size: 20px;
        font-weight: 600;
        color: #1f1a14;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("# 펀드/기업 상세 보기")
st.caption("펀드별로 투자기업을 선택하고, 기업별 KPI와 월별 추이를 확인합니다.")

source = "airtable" if airtable_enabled() else "csv"
if source == "airtable" and not airtable_enabled():
    source = "csv"

# 테이블 매핑
_table_map = get_dashboard_table_map(DEFAULT_TABLE_MAP)
_table_map = normalize_table_map(_table_map)

data = load_dashboard_tables(source=source, table_map=_table_map)
views = prepare_dashboard_views(data)

funds = views["funds"]
portfolio_latest = views["portfolio_latest"]
portfolio_all = views.get("portfolio_all", data.portfolio)

if funds.empty:
    st.error("펀드 데이터가 비어 있습니다. Airtable 설정을 확인해 주세요.")
    st.stop()

fund_company_map = build_fund_company_map_combined(funds, views["obligations"])
fund_options = sorted(fund_company_map.keys())

if not fund_options and "투자 조합명" in funds.columns:
    fund_options = sorted([str(v).strip() for v in funds["투자 조합명"].unique() if str(v).strip()])

with st.expander("펀드-기업 연동 상태", expanded=False):
    if not fund_company_map:
        st.info("연동된 펀드-기업 목록이 없습니다. 펀드/의무투자 탭의 기업 컬럼을 확인해 주세요.")
    else:
        rows = []
        for fund_name, companies in fund_company_map.items():
            sample = ", ".join(companies[:5]) if companies else "-"
            rows.append(
                {
                    "펀드": fund_name,
                    "기업 수": len(companies),
                    "샘플 기업": sample,
                }
            )
        status_df = pd.DataFrame(rows).sort_values("기업 수", ascending=False)
        st.dataframe(status_df, use_container_width=True, hide_index=True)

selected_fund = st.radio("펀드 선택", options=fund_options, horizontal=True)

companies_for_fund = fund_company_map.get(selected_fund, [])
company_search = st.text_input("기업 검색", value="")

filtered_company_options = companies_for_fund
if company_search:
    filtered_company_options = [
        name for name in companies_for_fund
        if company_search.lower() in name.lower()
    ]

if not filtered_company_options:
    st.warning("선택한 펀드에 연결된 기업 목록이 없습니다. 펀드 탭의 `투자기업` 컬럼을 확인해 주세요.")
    st.stop()

portfolio_fund_all = filter_portfolio_by_companies(portfolio_all, companies_for_fund)
companies_with_data = []
latest_date = None
if not portfolio_fund_all.empty and "법인명" in portfolio_fund_all.columns:
    companies_with_data = sorted([
        name for name in portfolio_fund_all["법인명"].dropna().unique() if str(name).strip()
    ])
    if "제출일" in portfolio_fund_all.columns:
        portfolio_fund_all["제출일_dt"] = pd.to_datetime(portfolio_fund_all["제출일"], errors="coerce")
        if portfolio_fund_all["제출일_dt"].notna().any():
            latest_date = portfolio_fund_all["제출일_dt"].max()

summary_html = """
<div class="summary-grid">
"""
summary_html += f"<div class=\"summary-card\"><div class=\"summary-label\">펀드 기업 수</div><div class=\"summary-value\">{len(companies_for_fund)}개</div></div>"
summary_html += f"<div class=\"summary-card\"><div class=\"summary-label\">결산 데이터 보유</div><div class=\"summary-value\">{len(companies_with_data)}개</div></div>"
summary_html += f"<div class=\"summary-card\"><div class=\"summary-label\">결산 데이터 건수</div><div class=\"summary-value\">{len(portfolio_fund_all)}건</div></div>"
summary_html += f"<div class=\"summary-card\"><div class=\"summary-label\">최신 제출</div><div class=\"summary-value\">{latest_date.date().isoformat() if latest_date else '-'} </div></div>"
summary_html += "</div>"

st.markdown(summary_html, unsafe_allow_html=True)

selected_company = st.selectbox("기업 선택", options=filtered_company_options)

# 기업 상세 (최신 제출 기준)
portfolio_company_latest = filter_portfolio_by_companies(portfolio_latest, [selected_company])

st.markdown("### 기업 상세 (최근 제출)")
if portfolio_company_latest.empty:
    st.info("선택한 기업의 최신 결산 데이터가 없습니다.")
else:
    summary_cols = [
        "법인명",
        "제출일",
        "매출액 (백만원)",
        "영업이익 (백만원)",
        "당기손익 (백만원)",
        "자산총계 (백만원)",
        "부채총계 (백만원)",
        "자본총계 (백만원)",
    ]
    existing = [col for col in summary_cols if col in portfolio_company_latest.columns]
    st.dataframe(to_display_dataframe(portfolio_company_latest[existing]), use_container_width=True, hide_index=True)

# 시계열
st.markdown("### 월별 KPI 추이")
compare_companies = st.multiselect(
    "KPI 비교 기업 선택",
    options=companies_for_fund,
    default=[selected_company],
)
if not compare_companies:
    compare_companies = [selected_company]

agg_mode = st.radio("월별 집계 기준", options=["합계", "평균"], horizontal=True)

portfolio_ts = filter_portfolio_by_companies(portfolio_all, compare_companies)

if "제출일" not in portfolio_ts.columns:
    st.info("제출일 컬럼이 없어 월별 추이를 생성할 수 없습니다. (없으면 취합이 필요합니다)")
else:
    portfolio_ts = portfolio_ts.copy()
    portfolio_ts["제출일_dt"] = pd.to_datetime(portfolio_ts["제출일"], errors="coerce")
    portfolio_ts = portfolio_ts.dropna(subset=["제출일_dt"])
    if portfolio_ts.empty:
        st.info("제출일 데이터가 없어 월별 추이를 생성할 수 없습니다. (없으면 취합이 필요합니다)")
    else:
        portfolio_ts["month"] = portfolio_ts["제출일_dt"].dt.to_period("M").dt.to_timestamp()
        kpi_options = {
            "매출액 (백만원)": "매출액 (백만원)_num",
            "영업이익 (백만원)": "영업이익 (백만원)_num",
            "당기손익 (백만원)": "당기손익 (백만원)_num",
            "자산총계 (백만원)": "자산총계 (백만원)_num",
            "부채총계 (백만원)": "부채총계 (백만원)_num",
            "자본총계 (백만원)": "자본총계 (백만원)_num",
        }
        available = {k: v for k, v in kpi_options.items() if v in portfolio_ts.columns}
        if not available:
            st.info("KPI 컬럼이 없어 월별 추이를 생성할 수 없습니다. (없으면 취합이 필요합니다)")
        else:
            selected_kpi_label = st.selectbox("KPI 선택", options=list(available.keys()))
            kpi_col = available[selected_kpi_label]
            kpi_series = portfolio_ts[["법인명", "month", kpi_col]].rename(columns={kpi_col: "value"}).dropna()
            if kpi_series.empty or "법인명" not in kpi_series.columns:
                st.info("선택한 KPI 데이터가 없습니다. (없으면 취합이 필요합니다)")
            else:
                per_company = (
                    kpi_series.groupby(["법인명", "month"], as_index=False)["value"].sum()
                )
                line = (
                    alt.Chart(per_company)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X("month:T", title="월"),
                        y=alt.Y("value:Q", title=selected_kpi_label),
                        color=alt.Color("법인명:N", legend=alt.Legend(title="기업")),
                        tooltip=["법인명", "month:T", "value:Q"],
                    )
                    .properties(height=280)
                )

                agg_func = "sum" if agg_mode == "합계" else "mean"
                agg_df = per_company.groupby("month", as_index=False)["value"].agg(agg_func)
                agg_df["법인명"] = f"선택 기업 {agg_mode}"
                agg_line = (
                    alt.Chart(agg_df)
                    .mark_line(point=True, strokeWidth=3, color="#1f1a14")
                    .encode(
                        x=alt.X("month:T", title="월"),
                        y=alt.Y("value:Q", title=selected_kpi_label),
                        tooltip=["month:T", "value:Q"],
                    )
                )
                st.markdown("<div class='reveal'>", unsafe_allow_html=True)
                st.altair_chart(alt.layer(line, agg_line), use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

st.caption(f"데이터 소스: {data.source.upper()} · 펀드: {selected_fund} · 기업: {selected_company}")
