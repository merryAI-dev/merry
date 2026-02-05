"""
공통 UI 컴포넌트
펀드 대시보드 및 포트폴리오 상세 페이지용 재사용 가능한 UI 컴포넌트
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st


# =============================================================================
# 색상 팔레트 (기존 스타일 시스템 일관성 유지)
# =============================================================================
COLORS = {
    "primary": "#7a5c43",      # 갈색
    "secondary": "#c8b39d",    # 라이트 갈색
    "background": "#f7f4ef",   # 베이지
    "text": "#1f1a14",         # 거의 검은색
    "text_secondary": "#6b5f53",  # 회갈색
    "text_muted": "#9b8f82",   # 옅은 갈색
    "border": "rgba(31, 26, 20, 0.08)",
    "error_bg": "#fef2f2",
    "error_border": "#fecaca",
    "error_text": "#991b1b",
}


# =============================================================================
# 빈 상태 컴포넌트
# =============================================================================
def render_empty_state(
    icon: str,
    title: str,
    description: str,
    action_label: str = None,
    action_key: str = None,
) -> bool:
    """빈 상태 UI 렌더링

    Args:
        icon: 이모지 아이콘
        title: 제목
        description: 설명 텍스트
        action_label: 액션 버튼 라벨 (선택)
        action_key: 버튼 키 (선택)

    Returns:
        액션 버튼이 클릭되었으면 True
    """
    st.markdown(f"""
    <div class="empty-state">
        <div class="empty-icon">{icon}</div>
        <div class="empty-title">{title}</div>
        <div class="empty-description">{description}</div>
    </div>
    <style>
    .empty-state {{
        text-align: center;
        padding: 48px 24px;
        background: linear-gradient(135deg, #ffffff, {COLORS['background']});
        border-radius: 16px;
        border: 2px dashed {COLORS['border']};
        margin: 16px 0;
    }}
    .empty-icon {{
        font-size: 48px;
        margin-bottom: 16px;
        opacity: 0.7;
    }}
    .empty-title {{
        font-size: 18px;
        font-weight: 600;
        color: {COLORS['text']};
        margin-bottom: 8px;
    }}
    .empty-description {{
        font-size: 14px;
        color: {COLORS['text_secondary']};
        max-width: 360px;
        margin: 0 auto;
        line-height: 1.5;
    }}
    </style>
    """, unsafe_allow_html=True)

    if action_label:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            return st.button(
                action_label,
                key=action_key or f"empty_action_{title[:10]}",
                use_container_width=True,
                type="primary"
            )
    return False


# =============================================================================
# 에러 상태 컴포넌트
# =============================================================================
def render_error_state(
    error_message: str,
    suggestions: List[str] = None,
    debug_info: Dict = None,
) -> None:
    """에러 상태 UI 렌더링

    Args:
        error_message: 에러 메시지
        suggestions: 해결책 제안 목록
        debug_info: 디버그 정보 (expander로 표시)
    """
    suggestions_html = ""
    if suggestions:
        suggestions_html = "<ul class='error-suggestions'>" + \
            "".join([f"<li>{s}</li>" for s in suggestions]) + \
            "</ul>"

    st.markdown(f"""
    <div class="error-state">
        <div class="error-header">
            <span class="error-icon">⚠️</span>
            <span class="error-title">문제가 발생했습니다</span>
        </div>
        <div class="error-message">{error_message}</div>
        {suggestions_html}
    </div>
    <style>
    .error-state {{
        background: {COLORS['error_bg']};
        border: 1px solid {COLORS['error_border']};
        border-radius: 12px;
        padding: 16px 20px;
        margin: 16px 0;
    }}
    .error-header {{
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
    }}
    .error-icon {{
        font-size: 18px;
    }}
    .error-title {{
        font-weight: 600;
        color: {COLORS['error_text']};
        font-size: 15px;
    }}
    .error-message {{
        color: #7f1d1d;
        font-size: 14px;
        line-height: 1.5;
    }}
    .error-suggestions {{
        margin-top: 12px;
        padding-left: 20px;
        color: {COLORS['text_secondary']};
        font-size: 13px;
        line-height: 1.6;
    }}
    .error-suggestions li {{
        margin-bottom: 4px;
    }}
    </style>
    """, unsafe_allow_html=True)

    if debug_info:
        with st.expander("디버그 정보", expanded=False):
            st.json(debug_info)


# =============================================================================
# 통합 필터 바
# =============================================================================
def render_filter_bar(
    show_search: bool = True,
    show_date_range: bool = True,
    show_status_filter: bool = False,
    status_options: List[str] = None,
    search_placeholder: str = "펀드/기업명 검색...",
    key_prefix: str = "filter",
) -> Tuple[str, Optional[Tuple[date, date]], List[str]]:
    """통합 필터 바 렌더링

    Args:
        show_search: 검색 입력 표시 여부
        show_date_range: 날짜 범위 필터 표시 여부
        show_status_filter: 상태 필터 표시 여부
        status_options: 상태 옵션 목록
        search_placeholder: 검색 플레이스홀더
        key_prefix: 위젯 키 접두사

    Returns:
        (검색어, 날짜범위 튜플 또는 None, 선택된 상태 목록)
    """
    st.markdown("""
    <style>
    .filter-bar-container {
        background: linear-gradient(135deg, #ffffff, #f7f4ef);
        border-radius: 12px;
        padding: 12px 16px;
        margin-bottom: 16px;
        border: 1px solid rgba(31, 26, 20, 0.08);
    }
    </style>
    """, unsafe_allow_html=True)

    search_query = ""
    date_range = None
    selected_status = []

    # 필터 컬럼 수 계산
    active_filters = sum([show_search, show_date_range, show_status_filter])
    col_widths = [2] * active_filters + [1]  # 마지막은 초기화 버튼

    cols = st.columns(col_widths)
    col_idx = 0

    if show_search:
        with cols[col_idx]:
            search_query = st.text_input(
                "검색",
                placeholder=search_placeholder,
                key=f"{key_prefix}_search",
                label_visibility="collapsed"
            )
        col_idx += 1

    if show_date_range:
        with cols[col_idx]:
            date_input = st.date_input(
                "기간",
                value=[],
                key=f"{key_prefix}_date_range",
                label_visibility="collapsed"
            )
            if isinstance(date_input, tuple) and len(date_input) == 2:
                date_range = date_input
        col_idx += 1

    if show_status_filter and status_options:
        with cols[col_idx]:
            selected_status = st.multiselect(
                "상태",
                options=status_options,
                default=[],
                key=f"{key_prefix}_status",
                label_visibility="collapsed"
            )
        col_idx += 1

    # 초기화 버튼
    with cols[-1]:
        if st.button("초기화", key=f"{key_prefix}_reset", use_container_width=True):
            # 세션 상태 초기화
            for key in [f"{key_prefix}_search", f"{key_prefix}_date_range", f"{key_prefix}_status"]:
                if key in st.session_state:
                    if "search" in key:
                        st.session_state[key] = ""
                    elif "date" in key:
                        st.session_state[key] = []
                    elif "status" in key:
                        st.session_state[key] = []
            st.rerun()

    # 활성 필터 칩 표시
    render_active_filter_chips(search_query, date_range, selected_status)

    return search_query, date_range, selected_status


def render_active_filter_chips(
    search_query: str = "",
    date_range: Optional[Tuple[date, date]] = None,
    selected_status: List[str] = None,
) -> None:
    """활성화된 필터를 칩으로 표시"""
    active_filters = []

    if search_query:
        active_filters.append(f"검색: {search_query}")

    if date_range and len(date_range) == 2:
        active_filters.append(f"기간: {date_range[0]} ~ {date_range[1]}")

    if selected_status:
        active_filters.append(f"상태: {', '.join(selected_status)}")

    if not active_filters:
        return

    chips_html = " ".join([
        f'<span class="filter-chip">{f}</span>' for f in active_filters
    ])

    st.markdown(f"""
    <div class="active-filters">
        {chips_html}
    </div>
    <style>
    .active-filters {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 12px;
    }}
    .filter-chip {{
        display: inline-block;
        padding: 4px 12px;
        background: rgba(122, 92, 67, 0.1);
        border-radius: 999px;
        font-size: 12px;
        color: {COLORS['primary']};
    }}
    </style>
    """, unsafe_allow_html=True)


# =============================================================================
# 다운로드 버튼
# =============================================================================
def render_download_button(
    df: pd.DataFrame,
    filename: str,
    label: str = "CSV 다운로드",
    show_row_count: bool = True,
) -> None:
    """데이터프레임 다운로드 버튼 렌더링

    Args:
        df: 다운로드할 데이터프레임
        filename: 파일명 (확장자 제외)
        label: 버튼 라벨
        show_row_count: 행 수 표시 여부
    """
    if df.empty:
        st.caption("다운로드할 데이터가 없습니다.")
        return

    csv = df.to_csv(index=False, encoding='utf-8-sig')

    col1, col2 = st.columns([1, 4])

    with col1:
        st.download_button(
            label=label,
            data=csv,
            file_name=f"{filename}.csv",
            mime="text/csv",
            use_container_width=True
        )

    if show_row_count:
        with col2:
            st.caption(f"총 {len(df):,}행 데이터")


# =============================================================================
# 차트 높이 계산
# =============================================================================
def calculate_chart_height(
    data_count: int,
    min_height: int = 200,
    max_height: int = 500,
    per_item: int = 35,
) -> int:
    """데이터 수에 따른 동적 차트 높이 계산

    Args:
        data_count: 데이터 항목 수
        min_height: 최소 높이
        max_height: 최대 높이
        per_item: 항목당 추가 높이

    Returns:
        계산된 차트 높이 (픽셀)
    """
    calculated = min_height + (data_count * per_item)
    return min(max_height, max(min_height, calculated))


# =============================================================================
# 퀵 인사이트 카드
# =============================================================================
def render_quick_insights(insights: List[Dict[str, str]]) -> None:
    """퀵 인사이트 카드 렌더링

    Args:
        insights: [{"icon": "emoji", "title": "제목", "content": "내용"}, ...]
    """
    if not insights:
        return

    st.markdown("### 퀵 인사이트")

    cards_html = ""
    for insight in insights:
        cards_html += f"""
        <div class="insight-card">
            <span class="insight-icon">{insight.get('icon', '📊')}</span>
            <div class="insight-content">
                <div class="insight-title">{insight.get('title', '')}</div>
                <div class="insight-text">{insight.get('content', '')}</div>
            </div>
        </div>
        """

    st.markdown(f"""
    <div class="insights-container">
        {cards_html}
    </div>
    <style>
    .insights-container {{
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin-bottom: 16px;
    }}
    .insight-card {{
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 14px 18px;
        background: linear-gradient(135deg, #ffffff, {COLORS['background']});
        border-radius: 14px;
        border: 1px solid {COLORS['border']};
        box-shadow: 0 8px 16px rgba(25, 18, 9, 0.06);
        flex: 1;
        min-width: 200px;
    }}
    .insight-icon {{
        font-size: 28px;
    }}
    .insight-title {{
        font-size: 11px;
        color: {COLORS['text_secondary']};
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 2px;
    }}
    .insight-text {{
        font-size: 14px;
        font-weight: 600;
        color: {COLORS['text']};
    }}
    </style>
    """, unsafe_allow_html=True)


def generate_fund_insights(
    funds: pd.DataFrame,
    portfolio: pd.DataFrame,
) -> List[Dict[str, str]]:
    """펀드/포트폴리오 데이터에서 자동 인사이트 생성

    Args:
        funds: 펀드 데이터프레임
        portfolio: 포트폴리오 데이터프레임

    Returns:
        인사이트 목록
    """
    insights = []

    # 최고 수익배수 펀드
    multiple_col = None
    for col in funds.columns:
        if "multiple" in col.lower() or "수익배수" in col:
            multiple_col = col
            break

    if multiple_col and not funds.empty:
        # 숫자 컬럼 확인
        numeric_col = f"{multiple_col}_num" if f"{multiple_col}_num" in funds.columns else multiple_col
        try:
            funds_sorted = funds.dropna(subset=[numeric_col])
            if not funds_sorted.empty:
                top_fund = funds_sorted.nlargest(1, numeric_col)
                if not top_fund.empty:
                    name = top_fund.iloc[0].get("투자 조합명", "N/A")
                    multiple = top_fund.iloc[0].get(numeric_col, 0)
                    if isinstance(multiple, (int, float)) and multiple > 0:
                        insights.append({
                            "icon": "🏆",
                            "title": "최고 수익배수 펀드",
                            "content": f"{name}: {multiple:.2f}x"
                        })
        except Exception:
            pass

    # 매출 상위 기업
    sales_col = None
    for col in portfolio.columns:
        if "매출" in col and ("num" in col or "백만" in col):
            sales_col = col
            break

    if sales_col and not portfolio.empty:
        try:
            portfolio_sorted = portfolio.dropna(subset=[sales_col])
            if len(portfolio_sorted) >= 3:
                top_companies = portfolio_sorted.nlargest(3, sales_col)
                if "법인명" in top_companies.columns:
                    companies = ", ".join(top_companies["법인명"].tolist()[:3])
                    insights.append({
                        "icon": "📈",
                        "title": "매출 상위 기업",
                        "content": companies
                    })
        except Exception:
            pass

    # 총 펀드 수
    if not funds.empty:
        insights.append({
            "icon": "📁",
            "title": "총 펀드 수",
            "content": f"{len(funds)}개 펀드"
        })

    return insights


# =============================================================================
# 펀드 셀렉터 (검색 가능)
# =============================================================================
def render_fund_selector(
    fund_options: List[str],
    fund_company_map: Dict[str, List[str]],
    include_all: bool = True,
    key: str = "fund_selector",
) -> str:
    """검색 가능한 펀드 셀렉터 렌더링

    Args:
        fund_options: 펀드 옵션 목록
        fund_company_map: 펀드-기업 매핑 딕셔너리
        include_all: "전체" 옵션 포함 여부
        key: 위젯 키

    Returns:
        선택된 펀드명
    """
    options = (["전체"] if include_all else []) + fund_options

    def format_option(x: str) -> str:
        if x == "전체":
            total_companies = sum(len(v) for v in fund_company_map.values())
            return f"전체 ({total_companies}개 기업)"
        company_count = len(fund_company_map.get(x, []))
        return f"{x} ({company_count}개 기업)"

    return st.selectbox(
        "펀드 선택",
        options=options,
        format_func=format_option,
        key=key,
    )
