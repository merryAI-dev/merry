"""
펀드 브랜딩 뉴스레터 페이지
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

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
    build_fund_company_map,
    filter_portfolio_by_companies,
    filter_company_df,
)
from shared.airtable_multi import airtable_enabled
from shared.airtable_portfolio import _get_cached_dataframe

PROJECT_ROOT = Path(__file__).resolve().parent.parent

st.set_page_config(
    page_title="펀드 뉴스레터 | 메리",
    page_icon="image-removebg-preview-5.png",
    layout="wide",
)

initialize_session_state()
check_authentication()
initialize_agent()
inject_custom_css()
render_sidebar(mode="collab")


def _theme_for_fund(name: str) -> Dict[str, str]:
    palette = [
        {"primary": "#7a5c43", "accent": "#c8b39d", "bg": "#f8f4ef"},
        {"primary": "#2f4f4f", "accent": "#a9c4c4", "bg": "#f0f6f6"},
        {"primary": "#3b4a6b", "accent": "#b3c0de", "bg": "#f2f4f9"},
        {"primary": "#4e2f2f", "accent": "#d3b2b2", "bg": "#faf3f3"},
        {"primary": "#2f4f38", "accent": "#b4d0be", "bg": "#f2f7f3"},
    ]
    idx = abs(hash(name)) % len(palette)
    return palette[idx]


def _format_number(value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.0f}"


def _format_kpi(value: Optional[float]) -> str:
    return _format_number(value)


def _truncate(text: str, limit: int = 140) -> str:
    if not text:
        return ""
    compact = " ".join(str(text).split())
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def _format_kpi(value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.0f}"


source = "airtable" if airtable_enabled() else "csv"
_table_map = normalize_table_map(get_dashboard_table_map(DEFAULT_TABLE_MAP))

data = load_dashboard_tables(source=source, table_map=_table_map)
views = prepare_dashboard_views(data)

funds = views["funds"]
portfolio_latest = views["portfolio_latest"]
portfolio_all = views.get("portfolio_all", data.portfolio)

if funds.empty:
    st.error("펀드 데이터가 비어 있습니다. Airtable 설정을 확인해 주세요.")
    st.stop()

fund_company_map = build_fund_company_map(funds)
fund_options = sorted(fund_company_map.keys())
if not fund_options and "투자 조합명" in funds.columns:
    fund_options = sorted([str(v).strip() for v in funds["투자 조합명"].unique() if str(v).strip()])

selected_fund = st.selectbox("펀드 선택", options=fund_options)

theme = _theme_for_fund(selected_fund)
st.markdown(
    f"""
    <style>
    :root {{
        --fund-primary: {theme['primary']};
        --fund-accent: {theme['accent']};
        --fund-bg: {theme['bg']};
    }}
    .newsletter-hero {{
        background: linear-gradient(135deg, var(--fund-bg), #ffffff);
        border: 1px solid rgba(31, 26, 20, 0.08);
        padding: 18px 20px;
        border-radius: 20px;
        box-shadow: 0 18px 30px rgba(31, 26, 20, 0.08);
        margin-bottom: 18px;
    }}
    .hero-title {{
        font-size: 28px;
        font-weight: 700;
        color: var(--fund-primary);
        margin-bottom: 6px;
    }}
    .hero-sub {{
        color: #6b5f53;
        font-size: 14px;
    }}
    .summary-grid {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
        margin-bottom: 16px;
    }}
    .summary-card {{
        background: #fff;
        border-radius: 14px;
        border: 1px solid rgba(31, 26, 20, 0.08);
        padding: 12px 14px;
        box-shadow: 0 10px 20px rgba(31, 26, 20, 0.06);
    }}
    .summary-label {{
        font-size: 12px;
        color: #6b5f53;
        margin-bottom: 6px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }}
    .summary-value {{
        font-size: 20px;
        font-weight: 600;
        color: #1f1a14;
    }}
    .company-card {{
        border-radius: 16px;
        border: 1px solid rgba(31, 26, 20, 0.08);
        padding: 14px 16px;
        background: #ffffff;
        box-shadow: 0 12px 24px rgba(31, 26, 20, 0.06);
        margin-bottom: 12px;
    }}
    .company-title {{
        font-size: 18px;
        font-weight: 600;
        color: var(--fund-primary);
        margin-bottom: 6px;
    }}
    .company-meta {{
        font-size: 12px;
        color: #6b5f53;
        margin-bottom: 8px;
    }}
    .badge-row {{
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 8px;
    }}
    .kpi-badge {{
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 4px 8px;
        border-radius: 999px;
        background: #f3efe9;
        font-size: 11px;
        color: #1f1a14;
        border: 1px solid rgba(31, 26, 20, 0.08);
    }}
    .kpi-badge--positive {{
        background: #e8f5e9;
        color: #1b5e20;
        border-color: rgba(27, 94, 32, 0.2);
    }}
    .kpi-badge--negative {{
        background: #ffebee;
        color: #b71c1c;
        border-color: rgba(183, 28, 28, 0.2);
    }}
    .highlight-card {{
        border-radius: 16px;
        border: 1px solid rgba(31, 26, 20, 0.08);
        padding: 14px 16px;
        background: #ffffff;
        box-shadow: 0 12px 24px rgba(31, 26, 20, 0.06);
        margin-bottom: 12px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

fund_companies = fund_company_map.get(selected_fund, [])
portfolio_fund_latest = filter_portfolio_by_companies(portfolio_latest, fund_companies)
portfolio_fund_all = filter_portfolio_by_companies(portfolio_all, fund_companies)

startup_df = _get_cached_dataframe()
startup_name_col = "기업명" if "기업명" in startup_df.columns else None
fund_startups_df = startup_df
if startup_name_col and fund_companies:
    fund_startups_df = filter_company_df(startup_df, startup_name_col, fund_companies)

st.markdown(
    f"""
    <div class="newsletter-hero">
        <div class="hero-title">{selected_fund} 뉴스레터</div>
        <div class="hero-sub">펀드 내 포트폴리오의 최신 현황과 핵심 투자 포인트를 요약했습니다.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

company_count = len(fund_companies)
report_count = len(portfolio_fund_latest) if not portfolio_fund_latest.empty else 0
latest_date = None
if not portfolio_fund_latest.empty and "제출일" in portfolio_fund_latest.columns:
    latest_date = pd.to_datetime(portfolio_fund_latest["제출일"], errors="coerce").max()

summary_html = "<div class=\"summary-grid\">"
summary_html += f"<div class=\"summary-card\"><div class=\"summary-label\">포트폴리오 기업</div><div class=\"summary-value\">{company_count}개</div></div>"
summary_html += f"<div class=\"summary-card\"><div class=\"summary-label\">결산 데이터 보유</div><div class=\"summary-value\">{report_count}개</div></div>"
summary_html += f"<div class=\"summary-card\"><div class=\"summary-label\">최신 제출</div><div class=\"summary-value\">{latest_date.date().isoformat() if latest_date is not pd.NaT else '-'} </div></div>"
summary_html += f"<div class=\"summary-card\"><div class=\"summary-label\">데이터 소스</div><div class=\"summary-value\">{data.source.upper()}</div></div>"
summary_html += "</div>"
st.markdown(summary_html, unsafe_allow_html=True)

if fund_companies:
    st.markdown("### 이달의 하이라이트")
    if portfolio_fund_latest.empty:
        st.info("하이라이트를 생성할 결산 데이터가 없습니다. (없으면 취합이 필요합니다)")
    else:
        highlight_blocks = []
        if "매출액 (백만원)_num" in portfolio_fund_latest.columns:
            top_sales = portfolio_fund_latest.sort_values("매출액 (백만원)_num", ascending=False).head(1)
            if not top_sales.empty:
                row = top_sales.iloc[0]
                highlight_blocks.append(
                    f"<div class=\"highlight-card\"><strong>매출 Top</strong><br>{row.get('법인명', '-')}: {_format_kpi(row.get('매출액 (백만원)_num'))} (백만원)</div>"
                )
        if "영업이익 (백만원)_num" in portfolio_fund_latest.columns:
            top_profit = portfolio_fund_latest.sort_values("영업이익 (백만원)_num", ascending=False).head(1)
            if not top_profit.empty:
                row = top_profit.iloc[0]
                highlight_blocks.append(
                    f"<div class=\"highlight-card\"><strong>영업이익 Top</strong><br>{row.get('법인명', '-')}: {_format_kpi(row.get('영업이익 (백만원)_num'))} (백만원)</div>"
                )
        if "자산총계 (백만원)_num" in portfolio_fund_latest.columns:
            top_assets = portfolio_fund_latest.sort_values("자산총계 (백만원)_num", ascending=False).head(1)
            if not top_assets.empty:
                row = top_assets.iloc[0]
                highlight_blocks.append(
                    f"<div class=\"highlight-card\"><strong>자산규모 Top</strong><br>{row.get('법인명', '-')}: {_format_kpi(row.get('자산총계 (백만원)_num'))} (백만원)</div>"
                )
        if highlight_blocks:
            st.markdown("".join(highlight_blocks), unsafe_allow_html=True)
        else:
            st.info("하이라이트를 생성할 수 있는 KPI 컬럼이 없습니다.")

    st.markdown("### 포트폴리오 하이라이트")
    for company in fund_companies:
        company_row = None
        if not fund_startups_df.empty and startup_name_col:
            match = filter_company_df(fund_startups_df, startup_name_col, [company])
            if not match.empty:
                company_row = match.iloc[0]

        kpi_row = None
        if not portfolio_fund_latest.empty and "법인명" in portfolio_fund_latest.columns:
            match = filter_portfolio_by_companies(portfolio_fund_latest, [company])
            if not match.empty:
                kpi_row = match.iloc[0]

        investment_point = None
        if company_row is not None:
            for col in ["투자포인트", "Investment Summary", "제품/서비스"]:
                if col in company_row and str(company_row.get(col, "")).strip():
                    investment_point = str(company_row.get(col)).strip()
                    break

        status_note = None
        if kpi_row is not None:
            for col in ["사업 운영 현황 및 이슈", "사후관리현황", "영업 현황_올해까지의 현황"]:
                if col in kpi_row and str(kpi_row.get(col, "")).strip():
                    status_note = str(kpi_row.get(col)).strip()
                    break

        kpi_badges = []
        if kpi_row is not None:
            sales = kpi_row.get("매출액 (백만원)_num") if "매출액 (백만원)_num" in kpi_row else None
            op_profit = kpi_row.get("영업이익 (백만원)_num") if "영업이익 (백만원)_num" in kpi_row else None
            net_profit = kpi_row.get("당기손익 (백만원)_num") if "당기손익 (백만원)_num" in kpi_row else None
            if sales is not None:
                kpi_badges.append(f"<span class='kpi-badge'>매출 {_format_kpi(sales)}</span>")
            if op_profit is not None:
                badge_class = "kpi-badge--positive" if op_profit >= 0 else "kpi-badge--negative"
                kpi_badges.append(f"<span class='kpi-badge {badge_class}'>영업이익 {_format_kpi(op_profit)}</span>")
            if net_profit is not None:
                badge_class = "kpi-badge--positive" if net_profit >= 0 else "kpi-badge--negative"
                kpi_badges.append(f"<span class='kpi-badge {badge_class}'>당기손익 {_format_kpi(net_profit)}</span>")

        st.markdown(
            f"""
            <div class=\"company-card\">
                <div class=\"company-title\">{company}</div>
                <div class=\"company-meta\">투자포인트: {_truncate(investment_point) if investment_point else '데이터 없음'}</div>
                <div class=\"company-meta\">현황: {_truncate(status_note) if status_note else '업데이트 대기'}</div>
                <div class=\"badge-row\">{''.join(kpi_badges) if kpi_badges else ''}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### 펀드 포트폴리오 요약")
    if not portfolio_fund_latest.empty:
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
        existing = [col for col in summary_cols if col in portfolio_fund_latest.columns]
        st.dataframe(portfolio_fund_latest[existing], use_container_width=True, hide_index=True)
    else:
        st.info("포트폴리오 결산 데이터가 없습니다. (없으면 취합이 필요합니다)")
else:
    st.info("펀드에 연결된 스타트업 목록이 없습니다. 펀드 탭의 투자기업 컬럼을 확인해 주세요.")

st.caption(f"펀드: {selected_fund} · 데이터 소스: {data.source.upper()}")

st.markdown("### 템플릿 출력")
email_template = f"""
[펀드 뉴스레터] {selected_fund}

- 포트폴리오 기업 수: {company_count}개
- 결산 데이터 보유: {report_count}개
- 최신 제출: {latest_date.date().isoformat() if latest_date is not pd.NaT else '-'}

[이달의 하이라이트]
{_truncate(' / '.join([row.get('법인명', '') for _, row in portfolio_fund_latest.head(3).iterrows()]) if not portfolio_fund_latest.empty else '없음', 120)}

[포트폴리오 요약]
"""

pdf_template = f"""
{selected_fund} Fund Newsletter

1. Summary
- Portfolio companies: {company_count}
- Reports available: {report_count}
- Latest submission: {latest_date.date().isoformat() if latest_date is not pd.NaT else '-'}

2. Highlights
- Top sales / profit / assets

3. Portfolio Snapshots
(Include KPI table and notes)
"""

col_email, col_pdf = st.columns(2)
with col_email:
    st.text_area("메일 템플릿", value=email_template, height=240)
    st.download_button(
        "메일 템플릿 다운로드",
        data=email_template,
        file_name=f"{selected_fund}_newsletter_email.txt",
    )
with col_pdf:
    st.text_area("PDF 템플릿", value=pdf_template, height=240)
    st.download_button(
        "PDF 템플릿 다운로드",
        data=pdf_template,
        file_name=f"{selected_fund}_newsletter_pdf.txt",
    )
