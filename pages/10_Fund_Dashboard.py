"""
펀드/포트폴리오/컴플라이언스 대시보드
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

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
    render_quick_insights,
    generate_fund_insights,
    render_fund_selector,
    calculate_chart_height,
)
from shared.fund_dashboard_data import (
    load_dashboard_tables,
    prepare_dashboard_views,
    DEFAULT_TABLE_MAP,
    get_dashboard_table_map,
    normalize_table_map,
    get_airtable_debug,
    build_fund_company_map_combined,
    filter_portfolio_by_companies,
    to_display_dataframe,
    filter_company_df,
)
from shared.airtable_multi import airtable_enabled
from shared.airtable_portfolio import _get_cached_dataframe


PROJECT_ROOT = Path(__file__).resolve().parent.parent


st.set_page_config(
    page_title="펀드 대시보드 | 메리",
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
    .fund-hero {
        padding: 6px 0 10px 0;
    }
    .fund-hero h1 {
        font-size: 30px;
        margin: 0;
        letter-spacing: -0.2px;
    }
    .fund-hero p {
        color: #6b5f53;
        font-size: 14px;
        margin-top: 6px;
    }
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
    }
    .kpi-card {
        background: linear-gradient(135deg, #ffffff, #f7f4ef);
        border-radius: 16px;
        border: 1px solid rgba(31, 26, 20, 0.08);
        padding: 14px 16px;
        box-shadow: 0 10px 22px rgba(25, 18, 9, 0.08);
        min-height: 96px;
    }
    .kpi-label {
        font-size: 12px;
        color: #6b5f53;
        margin-bottom: 6px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    .kpi-value {
        font-size: 22px;
        font-weight: 600;
        color: #1f1a14;
    }
    .kpi-sub {
        font-size: 12px;
        color: #9b8f82;
        margin-top: 6px;
    }
    .section-card {
        border-radius: 16px;
        border: 1px solid rgba(31, 26, 20, 0.08);
        padding: 12px 14px;
        background: rgba(255, 255, 255, 0.9);
        box-shadow: 0 12px 24px rgba(25, 18, 9, 0.06);
    }
    .fund-overview button {
        width: 100%;
        text-align: left;
        background: linear-gradient(135deg, #ffffff, #f7f4ef);
        border-radius: 16px;
        border: 1px solid rgba(31, 26, 20, 0.08);
        padding: 14px 16px;
        box-shadow: 0 12px 24px rgba(25, 18, 9, 0.06);
        font-size: 16px;
        font-weight: 600;
        color: #1f1a14;
    }
    .fund-overview button:hover {
        border-color: rgba(122, 92, 67, 0.5);
    }
    @keyframes swoosh {
        0% { opacity: 0; transform: translateY(14px) scale(0.98); }
        100% { opacity: 1; transform: translateY(0) scale(1); }
    }
    .reveal {
        animation: swoosh 0.6s ease-out both;
    }
    .kpi-card {
        animation: swoosh 0.6s ease-out both;
    }
    .kpi-card:nth-child(2) { animation-delay: 0.05s; }
    .kpi-card:nth-child(3) { animation-delay: 0.1s; }
    .kpi-card:nth-child(4) { animation-delay: 0.15s; }
    </style>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    """
    <div class="fund-hero">
        <h1>펀드/포트폴리오 대시보드</h1>
        <p>펀드 KPI, 의무투자 컴플라이언스, 포폴사 결산 데이터를 한 화면에서 요약합니다.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


default_index = 1 if airtable_enabled() else 0
source_choice = st.sidebar.radio(
    "데이터 소스",
    options=["CSV", "Airtable"],
    index=default_index,
    horizontal=True,
)

source = "airtable" if source_choice == "Airtable" else "csv"
if source == "airtable" and not airtable_enabled():
    st.warning("Airtable 설정이 없어 CSV로 대체합니다.")
    source = "csv"

table_map = get_dashboard_table_map(DEFAULT_TABLE_MAP)
if source == "airtable":
    with st.sidebar.expander("Airtable 테이블 설정", expanded=False):
        table_map["funds"] = st.text_input("펀드 테이블", value=table_map["funds"])
        table_map["obligations"] = st.text_input("의무투자 테이블", value=table_map["obligations"])
        table_map["portfolio"] = st.text_input("포폴 결산 테이블", value=table_map["portfolio"])
        st.caption("테이블명이 실제 Airtable 탭과 정확히 일치해야 합니다.")
        st.caption("secrets.toml 키: AIRTABLE_*_TABLE_ID / AIRTABLE_*_TABLE / AIRTABLE_*_TABLE_NAME")
        st.caption("URL을 붙여넣으면 table ID로 자동 인식됩니다.")

table_map_used = normalize_table_map(table_map)

data = load_dashboard_tables(source=source, table_map=table_map_used)
airtable_debug = None
if airtable_enabled():
    airtable_debug = get_airtable_debug(table_map_used)
if source == "csv" and data.funds.empty and airtable_enabled():
    st.warning("CSV 데이터가 비어 있어 Airtable로 전환합니다.")
    data = load_dashboard_tables(source="airtable", table_map=table_map_used)
    source = "airtable"
if source == "airtable" and data.funds.empty:
    st.warning("Airtable 데이터가 비어 있어 CSV로 전환합니다.")
    data = load_dashboard_tables(source="csv", table_map=table_map_used)
    source = "csv"
views = prepare_dashboard_views(data)

funds = views["funds"]
obligations = views["obligations"]
funds_with_compliance = views["funds_with_compliance"]
compliance_summary = views["compliance_summary"]
portfolio_latest = views["portfolio_latest"]

startup_df = _get_cached_dataframe()
fund_company_map = build_fund_company_map_combined(funds, obligations, startup_df)
fund_company_options = sorted({name for companies in fund_company_map.values() for name in companies})

fund_name_col = "투자 조합명" if "투자 조합명" in funds.columns else None
fund_options = []
if fund_name_col:
    fund_options = sorted([name for name in funds[fund_name_col].unique() if str(name).strip()])
elif "펀드명" in compliance_summary.columns:
    fund_options = sorted([name for name in compliance_summary["펀드명"].unique() if str(name).strip()])

# 펀드 선택 (검색 가능한 셀렉트박스)
selector_cols = st.columns([2, 3])
with selector_cols[0]:
    selected_fund = render_fund_selector(
        fund_options=fund_options,
        fund_company_map=fund_company_map,
        include_all=True,
        key="dashboard_fund_selector",
    )
    st.session_state.selected_fund = selected_fund
with selector_cols[1]:
    st.caption(f"펀드 수 {len(fund_options)}개 · 데이터 소스: {data.source.upper()}")

if selected_fund != "전체" and fund_name_col:
    funds_filtered = funds[funds[fund_name_col] == selected_fund]
    funds_with_compliance = funds_with_compliance[funds_with_compliance[fund_name_col] == selected_fund]
else:
    funds_filtered = funds

if selected_fund != "전체" and "펀드명" in obligations.columns:
    obligations = obligations[obligations["펀드명"].str.contains(selected_fund, na=False)]

if selected_fund != "전체" and "펀드명" in compliance_summary.columns:
    compliance_summary = compliance_summary[compliance_summary["펀드명"].str.contains(selected_fund, na=False)]

if selected_fund != "전체" and "포폴사-투자사 연계" in portfolio_latest.columns:
    portfolio_latest = portfolio_latest[
        portfolio_latest["포폴사-투자사 연계"].astype(str).str.contains(selected_fund, na=False)
    ]

if funds.empty:
    render_error_state(
        error_message="펀드 데이터를 불러올 수 없습니다.",
        suggestions=[
            f"현재 데이터 소스: {source.upper()}",
            f"펀드 테이블명 확인: {table_map_used['funds']}",
            "Airtable API 키가 올바른지 확인하세요",
            "테이블 이름이 실제 Airtable 탭과 일치하는지 확인하세요",
        ],
        debug_info={"source_debug": data.debug, "airtable_debug": airtable_debug},
    )
    st.stop()


def _format_amount(value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return "-"
    value = float(value)
    if abs(value) >= 100_000_000:
        return f"{value/100_000_000:,.1f}억"
    if abs(value) >= 10_000:
        return f"{value/10_000:,.0f}만"
    return f"{value:,.0f}"


def _format_percent(value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{value:.1f}%"


def _render_kpi_cards(kpis: list[Dict[str, str]]):
    cards_html = """<div class="kpi-grid">"""
    for kpi in kpis:
        cards_html += (
            "<div class=\"kpi-card\">"
            f"<div class=\"kpi-label\">{kpi['label']}</div>"
            f"<div class=\"kpi-value\">{kpi['value']}</div>"
            f"<div class=\"kpi-sub\">{kpi.get('sub', '')}</div>"
            "</div>"
        )
    cards_html += "</div>"
    st.markdown(cards_html, unsafe_allow_html=True)


def _format_currency_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    display = df.copy()
    for col in columns:
        if col in display.columns:
            display[col] = pd.to_numeric(display[col], errors="coerce").map(
                lambda x: f"{x:,.0f}" if pd.notna(x) else ""
            )
    return display


fund_count = len(funds_filtered)
commit_total = funds_filtered.get("약정총액_num", pd.Series(dtype=float)).sum()
invest_total = funds_filtered.get("총 투자금액(누적)_num", pd.Series(dtype=float)).sum()
return_total = funds_filtered.get("회수수익_num", pd.Series(dtype=float)).sum()
multiple_avg = funds_filtered.get("multiple(x) (투자수익배수)_num", pd.Series(dtype=float)).mean()

st.markdown("<div class='fund-overview'>", unsafe_allow_html=True)
if st.button(
    f"펀드 수 {fund_count}개 · 데이터 소스: {data.source.upper()} → 펀드 상세 보기",
    key="fund_overview_card",
):
    try:
        st.switch_page("pages/11_Fund_Company_View.py")
    except Exception:
        st.info("펀드/기업 상세 페이지로 이동해 주세요.")
st.markdown("</div>", unsafe_allow_html=True)

compliance_rate = None
if not compliance_summary.empty:
    achieved = (compliance_summary["compliance_status"] == "달성").sum()
    compliance_rate = achieved / len(compliance_summary) * 100 if len(compliance_summary) else None

kpis = [
    {"label": "펀드 수", "value": f"{fund_count}개", "sub": f"데이터 소스: {data.source.upper()}"},
    {"label": "약정총액", "value": _format_amount(commit_total), "sub": "합계"},
    {"label": "총 투자금액", "value": _format_amount(invest_total), "sub": "누적"},
    {"label": "평균 투자수익배수", "value": f"{multiple_avg:.2f}x" if multiple_avg else "-", "sub": "multiple"},
]
if compliance_rate is not None:
    kpis.append({"label": "컴플라이언스 달성", "value": _format_percent(compliance_rate), "sub": "펀드 기준"})

_render_kpi_cards(kpis[:4])
if len(kpis) > 4:
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    _render_kpi_cards(kpis[4:])

# 퀵 인사이트
insights = generate_fund_insights(funds_filtered, portfolio_latest)
if insights:
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    render_quick_insights(insights)

# 스타트업 전체/펀드 현황 요약
startup_name_col = "기업명" if "기업명" in startup_df.columns else None
startup_amount_col = None
for col in ["투자금액", "투자금액(누적)", "투자금액 누적"]:
    if col in startup_df.columns:
        startup_amount_col = col
        break

def _parse_amount_series(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("(", "-", regex=False)
        .str.replace(")", "", regex=False)
        .str.replace(r"[^0-9\-.]", "", regex=True)
        .replace("", pd.NA)
        .astype(float)
    )

overall_count = len(startup_df)
overall_amount = None
if startup_amount_col:
    overall_amount = _parse_amount_series(startup_df[startup_amount_col]).sum()

fund_companies = fund_company_map.get(selected_fund, []) if selected_fund != "전체" else []
fund_startup_df = startup_df
if startup_name_col and fund_companies:
    fund_startup_df = filter_company_df(startup_df, startup_name_col, fund_companies)
fund_count_startups = len(fund_startup_df) if fund_companies else 0
fund_amount = None
if startup_amount_col and fund_companies:
    fund_amount = _parse_amount_series(fund_startup_df[startup_amount_col]).sum()

st.markdown("### 스타트업 현황")
startup_cards = [
    {"label": "전체 스타트업", "value": f"{overall_count}개", "sub": "투자기업 전체"},
]
if overall_amount is not None:
    startup_cards.append({"label": "전체 투자금액", "value": _format_amount(overall_amount), "sub": "합계"})
if selected_fund != "전체":
    startup_cards.append({"label": f"{selected_fund} 스타트업", "value": f"{fund_count_startups}개", "sub": "펀드 기준"})
    if fund_amount is not None:
        startup_cards.append({"label": f"{selected_fund} 투자금액", "value": _format_amount(fund_amount), "sub": "합계"})

_render_kpi_cards(startup_cards[:4])


st.divider()


tabs = st.tabs(["펀드 요약", "의무투자 컴플라이언스", "포폴사 결산"])

with tabs[0]:
    st.markdown("### 펀드 투자/회수 흐름")
    chart_df = funds_filtered[["투자 조합명", "총 투자금액(누적)_num", "회수수익_num"]].copy()
    chart_df = chart_df.rename(columns={
        "총 투자금액(누적)_num": "총 투자금액",
        "회수수익_num": "회수수익",
    })
    chart_df = chart_df.dropna(subset=["투자 조합명"]).fillna(0)
    melted = chart_df.melt("투자 조합명", var_name="구분", value_name="금액")

    fund_chart = (
        alt.Chart(melted)
        .mark_bar()
        .encode(
            y=alt.Y("투자 조합명:N", sort="-x", title=None),
            x=alt.X("금액:Q", title="금액", axis=alt.Axis(format=",")),
            color=alt.Color("구분:N", scale=alt.Scale(range=["#c8b39d", "#7a5c43"])),
            tooltip=[
                "투자 조합명",
                "구분",
                alt.Tooltip("금액:Q", format=","),
            ],
        )
        .properties(height=320)
    )
    st.markdown("<div class='reveal'>", unsafe_allow_html=True)
    st.altair_chart(fund_chart, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### 투자수익배수 분포")
    if "multiple(x) (투자수익배수)_num" in funds_filtered.columns:
        dist_data = funds_filtered[["multiple(x) (투자수익배수)_num"]].copy()
        dist_data["multiple(x) (투자수익배수)_num"] = pd.to_numeric(
            dist_data["multiple(x) (투자수익배수)_num"], errors="coerce"
        )
        dist_data = dist_data.dropna()
        dist_chart = (
            alt.Chart(dist_data)
            .mark_bar(color="#7a5c43")
            .encode(
                x=alt.X("multiple(x) (투자수익배수)_num:Q", bin=alt.Bin(maxbins=10), title="multiple(x)"),
                y=alt.Y("count():Q", title="펀드 수"),
                tooltip=["count()"],
            )
            .properties(height=200)
        )
        st.markdown("<div class='reveal'>", unsafe_allow_html=True)
        st.altair_chart(dist_chart, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("multiple(x) 컬럼이 없어 분포를 표시할 수 없습니다.")

    with st.expander("펀드 상세 테이블 (필요 시 열기)", expanded=False):
        fund_search = st.text_input("펀드 검색", value=selected_fund if selected_fund != "전체" else "")
        if fund_search:
            funds_with_compliance = funds_with_compliance[
                funds_with_compliance["투자 조합명"].astype(str).str.contains(fund_search, na=False)
            ]
        funds_display = to_display_dataframe(funds_with_compliance)
        funds_display = _format_currency_columns(
            funds_display,
            ["약정총액", "총 투자금액(누적)", "회수원금", "회수수익", "투자가용금액"],
        )
        st.dataframe(funds_display, use_container_width=True, hide_index=True)

with tabs[1]:
    if obligations.empty:
        render_empty_state(
            icon="📋",
            title="의무투자 데이터 없음",
            description="의무투자 테이블에 데이터가 없습니다. Airtable에서 '의무 투자' 테이블을 확인해주세요.",
        )
    else:
        st.markdown("### 컴플라이언스 상태 요약")
        status_counts = obligations["compliance_status"].value_counts().reset_index()
        status_counts.columns = ["상태", "건수"]
        status_chart = (
            alt.Chart(status_counts)
            .mark_bar()
            .encode(
                x=alt.X("상태:N", sort="-y"),
                y=alt.Y("건수:Q"),
                color=alt.Color("상태:N", scale=alt.Scale(range=["#7a5c43", "#c8b39d", "#e3d5c5", "#b0a091"])),
                tooltip=["상태", "건수"],
            )
            .properties(height=200)
        )
        st.markdown("<div class='reveal'>", unsafe_allow_html=True)
        st.altair_chart(status_chart, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("### 펀드별 달성율")
        if not compliance_summary.empty and "최소_달성율" in compliance_summary.columns:
            name_field = "펀드명" if "펀드명" in compliance_summary.columns else "join_key"
            rate_chart = (
                alt.Chart(compliance_summary)
                .mark_bar(color="#7a5c43")
                .encode(
                    x=alt.X(f"{name_field}:N", sort="-y", title="펀드", axis=alt.Axis(labelAngle=-30)),
                    y=alt.Y("최소_달성율:Q", title="최소 달성율(%)"),
                    tooltip=[name_field, "최소_달성율", "compliance_status"],
                )
                .properties(height=320)
            )
            st.markdown("<div class='reveal'>", unsafe_allow_html=True)
            st.altair_chart(rate_chart, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("달성율 데이터가 없어 차트를 표시할 수 없습니다.")

        st.markdown("### 의무투자 상세")
        obligation_search = st.text_input("의무투자 검색", value=selected_fund if selected_fund != "전체" else "")
        if obligation_search and "펀드명" in obligations.columns:
            obligations = obligations[
                obligations["펀드명"].astype(str).str.contains(obligation_search, na=False)
            ]
        obligations_display = to_display_dataframe(obligations)
        obligations_display = _format_currency_columns(
            obligations_display,
            ["기준 금액", "투자금액", "미달성 금액(-는 달성완료임)"],
        )
        st.dataframe(obligations_display, use_container_width=True, hide_index=True)
        render_download_button(obligations_display, f"의무투자_{selected_fund}")

with tabs[2]:
    if portfolio_latest.empty:
        render_empty_state(
            icon="📊",
            title="포폴사 결산 데이터 없음",
            description="포트폴리오 결산 데이터가 없습니다. Airtable에서 '포폴사 결산 자료' 테이블을 확인해주세요.",
        )
    else:
        st.markdown("### 포폴사 결산 요약 (최근 제출 기준)")
        if selected_fund != "전체":
            companies_for_fund = fund_company_map.get(selected_fund, [])
            if not companies_for_fund:
                st.info("선택한 펀드의 투자기업 목록이 없어 전체 포폴을 표시합니다.")
            else:
                selected_companies = st.multiselect(
                    "펀드 투자기업 선택",
                    options=companies_for_fund,
                    default=companies_for_fund,
                )
                if selected_companies:
                    portfolio_latest = filter_portfolio_by_companies(portfolio_latest, selected_companies)
        else:
            if fund_company_options:
                selected_companies = st.multiselect(
                    "투자기업 선택(선택 시 필터링)",
                    options=fund_company_options,
                    default=[],
                )
                if selected_companies:
                    portfolio_latest = filter_portfolio_by_companies(portfolio_latest, selected_companies)

        portfolio_search = st.text_input("포폴 검색", value="")
        if portfolio_search and "법인명" in portfolio_latest.columns:
            portfolio_latest = portfolio_latest[
                portfolio_latest["법인명"].astype(str).str.contains(portfolio_search, na=False)
            ]
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
        existing_cols = [col for col in summary_cols if col in portfolio_latest.columns]
        portfolio_display = to_display_dataframe(portfolio_latest[existing_cols])
        portfolio_display = _format_currency_columns(
            portfolio_display,
            [
                "매출액 (백만원)",
                "영업이익 (백만원)",
                "당기손익 (백만원)",
                "자산총계 (백만원)",
                "부채총계 (백만원)",
                "자본총계 (백만원)",
            ],
        )
        st.dataframe(portfolio_display, use_container_width=True, hide_index=True)
        render_download_button(portfolio_display, f"포폴사_결산_{selected_fund}")

        if "매출액 (백만원)_num" in portfolio_latest.columns:
            top_sales = portfolio_latest.sort_values("매출액 (백만원)_num", ascending=False).head(10)
            sales_data = top_sales[["법인명", "매출액 (백만원)_num"]].copy()
            orientation = st.radio("기업 레이블 위치", options=["왼쪽(가독성)", "아래(전통)"], horizontal=True)
            if orientation.startswith("아래"):
                sales_chart = (
                    alt.Chart(sales_data)
                    .mark_bar(color="#7a5c43")
                    .encode(
                        x=alt.X("법인명:N", sort="-y", title=None, axis=alt.Axis(labelAngle=-30)),
                        y=alt.Y("매출액 (백만원)_num:Q", title="매출액(백만원)", axis=alt.Axis(format=",")),
                        tooltip=["법인명", alt.Tooltip("매출액 (백만원)_num:Q", format=",")],
                    )
                    .properties(height=320)
                )
            else:
                sales_chart = (
                    alt.Chart(sales_data)
                    .mark_bar(color="#7a5c43")
                    .encode(
                        y=alt.Y("법인명:N", sort="-x", title=None),
                        x=alt.X("매출액 (백만원)_num:Q", title="매출액(백만원)", axis=alt.Axis(format=",")),
                        tooltip=["법인명", alt.Tooltip("매출액 (백만원)_num:Q", format=",")],
                    )
                    .properties(height=300)
                )
            st.markdown("<div class='reveal'>", unsafe_allow_html=True)
            st.altair_chart(sales_chart, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        if fund_company_map:
            st.caption("현재 펀드 탭의 `투자기업` 목록 기준으로 포폴 결산을 매칭합니다.")
        else:
            st.info("펀드-포트폴리오 연결 키가 없어서 펀드별 집계가 제한됩니다. (펀드 탭에 `투자기업` 컬럼 필요)")


st.caption(
    f"데이터 소스: {data.source.upper()} · Airtable 테이블: {', '.join(DEFAULT_TABLE_MAP.values())}"
)
