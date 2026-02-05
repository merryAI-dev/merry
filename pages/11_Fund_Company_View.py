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
from shared.ui_components import (
    render_empty_state,
    render_error_state,
    render_download_button,
    render_fund_selector,
    render_filter_bar,
    calculate_chart_height,
)
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
from shared.airtable_portfolio import _get_cached_dataframe
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


# 기업 상세 모달
@st.dialog("기업 상세 정보", width="large")
def show_company_detail_modal(company_name: str, portfolio_data: pd.DataFrame):
    """기업 상세 정보 모달"""
    company_data = portfolio_data[portfolio_data["법인명"] == company_name]

    if company_data.empty:
        st.warning("기업 데이터를 찾을 수 없습니다.")
        return

    latest = company_data.iloc[0]

    st.markdown(f"## {company_name}")

    # KPI 메트릭
    kpi_cols = st.columns(3)

    def safe_get(row, col):
        val = row.get(col, 0)
        if pd.isna(val):
            return 0
        return float(val)

    with kpi_cols[0]:
        st.metric("매출액", f"{safe_get(latest, '매출액 (백만원)_num'):,.0f}백만원")
    with kpi_cols[1]:
        st.metric("영업이익", f"{safe_get(latest, '영업이익 (백만원)_num'):,.0f}백만원")
    with kpi_cols[2]:
        st.metric("당기순이익", f"{safe_get(latest, '당기손익 (백만원)_num'):,.0f}백만원")

    st.divider()

    # 자산/부채
    asset_cols = st.columns(3)
    with asset_cols[0]:
        st.metric("자산총계", f"{safe_get(latest, '자산총계 (백만원)_num'):,.0f}백만원")
    with asset_cols[1]:
        st.metric("부채총계", f"{safe_get(latest, '부채총계 (백만원)_num'):,.0f}백만원")
    with asset_cols[2]:
        st.metric("자본총계", f"{safe_get(latest, '자본총계 (백만원)_num'):,.0f}백만원")

    st.divider()

    # 상세 테이블 (히스토리)
    st.markdown("### 결산 히스토리")
    display_cols = ["제출일", "매출액 (백만원)", "영업이익 (백만원)", "당기손익 (백만원)"]
    existing_cols = [c for c in display_cols if c in company_data.columns]
    if existing_cols:
        st.dataframe(
            to_display_dataframe(company_data[existing_cols].sort_values("제출일", ascending=False)),
            use_container_width=True,
            hide_index=True,
        )

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
    render_error_state(
        error_message="펀드 데이터를 불러올 수 없습니다.",
        suggestions=[
            "Airtable API 키가 올바른지 확인하세요",
            "테이블 이름이 실제 Airtable 탭과 일치하는지 확인하세요",
            "네트워크 연결 상태를 확인하세요",
        ],
    )
    st.stop()

startup_df = _get_cached_dataframe()
fund_company_map = build_fund_company_map_combined(funds, views["obligations"], startup_df)
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

# 펀드 선택 (검색 가능한 셀렉트박스)
selected_fund = render_fund_selector(
    fund_options=fund_options,
    fund_company_map=fund_company_map,
    include_all=False,
    key="company_view_fund_selector",
)

companies_for_fund = fund_company_map.get(selected_fund, [])
company_search = st.text_input("기업 검색", value="", placeholder="기업명 입력...")

filtered_company_options = companies_for_fund
if company_search:
    filtered_company_options = [
        name for name in companies_for_fund
        if company_search.lower() in name.lower()
    ]

if not filtered_company_options:
    render_empty_state(
        icon="🏢",
        title="연결된 기업 없음",
        description=f"'{selected_fund}' 펀드에 연결된 투자기업이 없습니다. 펀드 테이블의 '투자기업' 컬럼을 확인해주세요.",
    )
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

select_cols = st.columns([3, 1])
with select_cols[0]:
    selected_company = st.selectbox("기업 선택", options=filtered_company_options)
with select_cols[1]:
    st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
    if st.button("상세 보기", use_container_width=True, type="primary"):
        show_company_detail_modal(selected_company, portfolio_all)

# 기업 상세 (최신 제출 기준)
portfolio_company_latest = filter_portfolio_by_companies(portfolio_latest, [selected_company])

st.markdown("### 기업 상세 (최근 제출)")
if portfolio_company_latest.empty:
    render_empty_state(
        icon="📄",
        title="결산 데이터 없음",
        description=f"'{selected_company}'의 최신 결산 데이터가 없습니다.",
    )
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
    display_df = to_display_dataframe(portfolio_company_latest[existing])
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    render_download_button(display_df, f"기업상세_{selected_company}")

# 시계열
st.markdown("### 월별 KPI 추이")

# 필터 옵션
filter_cols = st.columns([2, 2, 1])
with filter_cols[0]:
    compare_companies = st.multiselect(
        "KPI 비교 기업 선택",
        options=companies_for_fund,
        default=[selected_company],
    )
    if not compare_companies:
        compare_companies = [selected_company]

with filter_cols[1]:
    date_range = st.date_input(
        "기간 선택",
        value=[],
        key="kpi_date_range",
        help="시작일과 종료일을 선택하세요",
    )

with filter_cols[2]:
    agg_mode = st.radio("집계", options=["합계", "평균"], horizontal=True)

portfolio_ts = filter_portfolio_by_companies(portfolio_all, compare_companies)

if "제출일" not in portfolio_ts.columns:
    st.info("제출일 컬럼이 없어 월별 추이를 생성할 수 없습니다. (없으면 취합이 필요합니다)")
else:
    portfolio_ts = portfolio_ts.copy()
    portfolio_ts["제출일_dt"] = pd.to_datetime(portfolio_ts["제출일"], errors="coerce")
    portfolio_ts = portfolio_ts.dropna(subset=["제출일_dt"])

    # 날짜 범위 필터 적용
    if date_range and len(date_range) == 2:
        start_date, end_date = date_range
        portfolio_ts = portfolio_ts[
            (portfolio_ts["제출일_dt"].dt.date >= start_date) &
            (portfolio_ts["제출일_dt"].dt.date <= end_date)
        ]

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

                # 동적 차트 높이 계산
                unique_companies = per_company["법인명"].nunique()
                chart_height = calculate_chart_height(unique_companies, min_height=250, max_height=450)

                line = (
                    alt.Chart(per_company)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X("month:T", title="월"),
                        y=alt.Y("value:Q", title=selected_kpi_label),
                        color=alt.Color("법인명:N", legend=alt.Legend(title="기업")),
                        tooltip=["법인명", "month:T", "value:Q"],
                    )
                    .properties(height=chart_height)
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
