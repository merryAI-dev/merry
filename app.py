"""
VC 투자 분석 에이전트 - 홈페이지

실행: streamlit run app.py
"""

import streamlit as st

from shared.config import initialize_session_state, inject_custom_css, get_header_image
from shared.auth import check_authentication
from shared.logging_config import setup_logging

# 로깅 초기화 (앱 시작 시 1회)
setup_logging()

# 페이지 설정
st.set_page_config(
    page_title="VC 투자 분석 에이전트",
    page_icon="VC",
    layout="wide",
)

# 초기화
initialize_session_state()
check_authentication()
inject_custom_css()

# ========================================
# 홈 그래프 스타일 (Obsidian 스타일)
# ========================================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

    :root {
        --graph-bg: #f7f2ea;
        --graph-ink: #1c1914;
        --graph-muted: #60554b;
        --graph-node-bg: rgba(255, 255, 255, 0.9);
        --graph-node-border: rgba(28, 25, 20, 0.14);
        --graph-grid: rgba(28, 25, 20, 0.06);
        --graph-accent: #cc3a2b;
        --graph-accent-amber: #d08a2e;
        --graph-accent-teal: #1a8c86;
        --graph-shadow: 0 18px 40px rgba(25, 18, 9, 0.12);
    }

    .stApp {
        background-color: var(--graph-bg);
        background-image:
            radial-gradient(circle at 15% 10%, rgba(255, 247, 236, 0.9), rgba(255, 247, 236, 0) 40%),
            radial-gradient(circle at 85% 20%, rgba(255, 232, 218, 0.7), rgba(255, 232, 218, 0) 35%),
            repeating-linear-gradient(0deg, var(--graph-grid), var(--graph-grid) 1px, transparent 1px, transparent 28px),
            repeating-linear-gradient(90deg, var(--graph-grid), var(--graph-grid) 1px, transparent 1px, transparent 28px);
        background-attachment: fixed;
    }

    html, body, [class*="css"] {
        font-family: "Space Grotesk", "Noto Sans KR", sans-serif;
        color: var(--graph-ink);
    }

    .graph-hero {
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding: 18px 8px 6px 8px;
    }

    .graph-hero__kicker {
        font-family: "IBM Plex Mono", monospace;
        font-size: 12px;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--graph-muted);
    }

    .graph-hero__title {
        font-size: 36px;
        font-weight: 700;
        margin: 0;
    }

    .graph-hero__desc {
        font-size: 16px;
        color: var(--graph-muted);
        max-width: 560px;
        margin: 0;
    }

    .graph-map-title {
        font-family: "IBM Plex Mono", monospace;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.2em;
        color: var(--graph-muted);
        margin: 24px 0 12px 0;
    }

    .graph-row-gap {
        height: 18px;
    }

    .graph-canvas-marker {
        display: none;
    }

    .graph-node-marker {
        display: none;
    }

    div[data-testid="stContainer"]:has(.graph-canvas-marker) {
        position: relative;
        padding: 12px 4px 20px 4px;
        margin-bottom: 12px;
    }

    div[data-testid="stContainer"]:has(.graph-canvas-marker)::after {
        content: "";
        position: absolute;
        inset: -6% -4%;
        background-image:
            radial-gradient(circle, rgba(204, 58, 43, 0.12) 0, rgba(204, 58, 43, 0) 55%),
            radial-gradient(circle, rgba(208, 138, 46, 0.12) 0, rgba(208, 138, 46, 0) 55%),
            radial-gradient(circle, rgba(26, 140, 134, 0.16) 0, rgba(26, 140, 134, 0) 60%);
        background-size: 180px 180px, 220px 220px, 260px 260px;
        background-position: 10% 20%, 85% 15%, 40% 80%;
        opacity: 0.7;
        pointer-events: none;
        animation: drift 18s linear infinite;
        z-index: 0;
    }

    .graph-lines {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: 0;
        opacity: 0.55;
    }

    .graph-lines path {
        stroke: rgba(28, 25, 20, 0.16);
        stroke-width: 2;
        stroke-linecap: round;
        stroke-dasharray: 6 10;
    }

    .graph-lines .graph-dot {
        fill: rgba(28, 25, 20, 0.7);
        animation: pulse 4s ease-in-out infinite;
        transform-origin: center;
    }

    div[data-testid="stContainer"]:has(.graph-node-marker) {
        background: var(--graph-node-bg);
        border: 1px solid var(--graph-node-border);
        border-radius: 18px;
        padding: 18px 18px 12px 18px;
        box-shadow: var(--graph-shadow);
        position: relative;
        overflow: hidden;
        z-index: 2;
        animation: floatNode 7s ease-in-out infinite;
        will-change: transform;
    }

    div[data-testid="stContainer"]:has(.graph-node-marker)::after {
        content: "";
        position: absolute;
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: var(--graph-accent);
        top: 16px;
        right: 16px;
        box-shadow: 0 0 0 6px rgba(204, 58, 43, 0.12);
    }

    div[data-testid="stContainer"]:has(.graph-node-marker[data-accent="amber"])::after {
        background: var(--graph-accent-amber);
        box-shadow: 0 0 0 6px rgba(208, 138, 46, 0.14);
    }

    div[data-testid="stContainer"]:has(.graph-node-marker[data-accent="teal"])::after {
        background: var(--graph-accent-teal);
        box-shadow: 0 0 0 6px rgba(26, 140, 134, 0.14);
    }

    div[data-testid="stContainer"]:has(.graph-node-marker[data-accent="hub"])::after {
        width: 14px;
        height: 14px;
        background: #11100f;
        box-shadow: 0 0 0 8px rgba(17, 16, 15, 0.08);
    }

    div[data-testid="stContainer"]:has(.graph-node-marker[data-accent="amber"]) {
        animation-delay: -1.8s;
    }

    div[data-testid="stContainer"]:has(.graph-node-marker[data-accent="teal"]) {
        animation-delay: -3.2s;
    }

    div[data-testid="stContainer"]:has(.graph-node-marker[data-accent="hub"]) {
        animation-delay: -2.4s;
    }

    .graph-node__summary {
        font-size: 14px;
        color: var(--graph-muted);
        margin-bottom: 8px;
    }

    .graph-node__list {
        padding-left: 18px;
        margin: 0 0 12px 0;
        color: var(--graph-ink);
        font-size: 13px;
        line-height: 1.6;
    }

    .graph-node__chips {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 12px;
    }

    .graph-node__chip {
        font-family: "IBM Plex Mono", monospace;
        font-size: 11px;
        padding: 4px 8px;
        border-radius: 999px;
        border: 1px solid rgba(28, 25, 20, 0.12);
        background: rgba(255, 255, 255, 0.7);
    }

    div[data-testid="stContainer"]:has(.graph-node-marker) .stButton > button {
        border-radius: 999px !important;
        border-color: var(--graph-ink) !important;
        color: var(--graph-ink) !important;
        background: transparent !important;
    }

    div[data-testid="stContainer"]:has(.graph-node-marker) .stButton > button:hover {
        background: rgba(28, 25, 20, 0.06) !important;
    }

    @keyframes floatNode {
        0% { transform: translateY(0px); }
        50% { transform: translateY(-8px); }
        100% { transform: translateY(0px); }
    }

    @keyframes drift {
        0% { transform: translate(0, 0); }
        50% { transform: translate(-30px, 20px); }
        100% { transform: translate(0, 0); }
    }

    @keyframes pulse {
        0% { transform: scale(1); opacity: 0.65; }
        50% { transform: scale(1.25); opacity: 0.35; }
        100% { transform: scale(1); opacity: 0.65; }
    }

    @media (max-width: 900px) {
        .graph-hero__title {
            font-size: 28px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _render_graph_node(
    title: str,
    summary: str,
    bullets: list[str],
    chips: list[str],
    button_label: str,
    page_path: str,
    key: str,
    accent: str = "ember",
) -> None:
    with st.container():
        st.markdown(f'<div class="graph-node-marker" data-accent="{accent}"></div>', unsafe_allow_html=True)
        st.markdown(f"#### {title}")
        st.markdown(f"<p class='graph-node__summary'>{summary}</p>", unsafe_allow_html=True)
        if bullets:
            items = "".join([f"<li>{item}</li>" for item in bullets])
            st.markdown(f"<ul class='graph-node__list'>{items}</ul>", unsafe_allow_html=True)
        if chips:
            chip_html = "".join([f"<span class='graph-node__chip'>{chip}</span>" for chip in chips])
            st.markdown(f"<div class='graph-node__chips'>{chip_html}</div>", unsafe_allow_html=True)
        if st.button(button_label, use_container_width=True, key=key):
            st.switch_page(page_path)


def _render_graph_hub() -> None:
    with st.container():
        st.markdown('<div class="graph-node-marker" data-accent="hub"></div>', unsafe_allow_html=True)
        st.markdown("#### VC 투자 분석 그래프")
        st.markdown(
            "<p class='graph-node__summary'>메리와 대화하며 각 모듈을 연결합니다. "
            "필요한 분석을 선택해 바로 시작하세요.</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='graph-node__chips'>"
            "<span class='graph-node__chip'>Exit</span>"
            "<span class='graph-node__chip'>Peer</span>"
            "<span class='graph-node__chip'>Report</span>"
            "<span class='graph-node__chip'>Contract</span>"
            "<span class='graph-node__chip'>Voice</span>"
            "</div>",
            unsafe_allow_html=True,
        )


hero_cols = st.columns([1, 4, 1])
with hero_cols[0]:
    st.image(get_header_image(), width=140)
with hero_cols[1]:
    st.markdown(
        """
        <div class="graph-hero">
            <div class="graph-hero__kicker">VC Intelligence Graph</div>
            <h1 class="graph-hero__title">VC 투자 분석 에이전트</h1>
            <p class="graph-hero__desc">
                Exit 프로젝션, PER 분석, IRR 계산을 메리와 대화하면서 수행하세요.
                각 모듈은 그래프처럼 연결되어 있고, 클릭 한 번으로 이동합니다.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div class='graph-map-title'>Module Graph</div>", unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="graph-canvas-marker"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <svg class="graph-lines" viewBox="0 0 1000 900" preserveAspectRatio="none" aria-hidden="true">
            <g>
                <path d="M500 90 L250 250" />
                <path d="M500 90 L750 250" />
                <path d="M250 250 L500 430" />
                <path d="M750 250 L500 430" />
                <path d="M500 430 L250 610" />
                <path d="M500 430 L750 610" />
                <path d="M500 430 L500 780" />
            </g>
            <g>
                <circle class="graph-dot" cx="500" cy="90" r="6" />
                <circle class="graph-dot" cx="250" cy="250" r="5" />
                <circle class="graph-dot" cx="750" cy="250" r="5" />
                <circle class="graph-dot" cx="500" cy="430" r="7" />
                <circle class="graph-dot" cx="250" cy="610" r="5" />
                <circle class="graph-dot" cx="750" cy="610" r="5" />
                <circle class="graph-dot" cx="500" cy="780" r="5" />
            </g>
        </svg>
        """,
        unsafe_allow_html=True,
    )

    row1 = st.columns([1, 2, 1])
    with row1[1]:
        _render_graph_node(
            "Exit 프로젝션",
            "투자검토 엑셀 기반 Exit 분석.",
            ["PER 시나리오/IRR/멀티플", "3-Tier 결과 엑셀 생성", "SAFE 전환 시나리오 지원"],
            ["Excel", "Scenario", "IRR"],
            "Exit 프로젝션 시작",
            "pages/1_Exit_Projection.py",
            "graph_exit",
            accent="ember",
        )

    st.markdown("<div class='graph-row-gap'></div>", unsafe_allow_html=True)

    row2 = st.columns([1, 2, 1])
    with row2[0]:
        _render_graph_node(
            "Peer PER 분석",
            "유사 상장 기업 PER 벤치마킹.",
            ["PDF 기반 비즈니스 모델 파악", "Yahoo Finance PER 조회", "매출/목표가치 역산"],
            ["PDF", "Market", "PER"],
            "Peer PER 분석 시작",
            "pages/2_Peer_PER_Analysis.py",
            "graph_peer",
            accent="amber",
        )
    with row2[2]:
        _render_graph_node(
            "투자심사 보고서",
            "인수인의견 스타일 초안 생성.",
            ["시장규모 근거 추출", "보고서 문장 초안", "확인 필요 사항 정리"],
            ["Report", "Evidence", "Draft"],
            "투자심사 보고서 시작",
            "pages/4_Investment_Report.py",
            "graph_report",
            accent="teal",
        )

    st.markdown("<div class='graph-row-gap'></div>", unsafe_allow_html=True)

    row3 = st.columns([1, 2, 1])
    with row3[1]:
        _render_graph_hub()

    st.markdown("<div class='graph-row-gap'></div>", unsafe_allow_html=True)

    row4 = st.columns([1, 2, 1])
    with row4[0]:
        _render_graph_node(
            "기업현황 진단시트",
            "진단시트 기반 컨설턴트 보고서.",
            ["체크리스트 자동 분석", "점수/리포트 초안", "엑셀에 반영/저장"],
            ["Checklist", "Scoring"],
            "기업현황 진단시트 시작",
            "pages/3_Company_Diagnosis.py",
            "graph_diagnosis",
            accent="ember",
        )
    with row4[2]:
        _render_graph_node(
            "계약서 리서치",
            "텀싯/투자계약서 근거 기반 검토.",
            ["PDF·DOCX 텍스트 추출", "핵심 항목/근거 스니펫", "문서 간 일치 여부 점검"],
            ["OCR", "Compare", "Risk"],
            "계약서 리서치 시작",
            "pages/7_Contract_Review.py",
            "graph_contract",
            accent="amber",
        )

    st.markdown("<div class='graph-row-gap'></div>", unsafe_allow_html=True)

    row5 = st.columns([1, 2, 1])
    with row5[1]:
        _render_graph_node(
            "Voice Agent",
            "체크인/원온원 음성 대화.",
            ["Naver CLOVA STT/TTS", "어제 로그 기반 요약", "대화형 체크인 플로우"],
            ["STT/TTS", "Check-in"],
            "Voice Agent 시작",
            "pages/5_Voice_Agent.py",
            "graph_voice",
            accent="teal",
        )
        if st.button("체크인 기록 보기", type="secondary", use_container_width=True, key="start_checkin_review"):
            st.switch_page("pages/6_Checkin_Review.py")

st.divider()

# ========================================
# 사용 가이드
# ========================================
st.markdown("## 사용 가이드")

with st.expander("Exit 프로젝션 워크플로우", expanded=False):
    st.markdown("""
### 1. 엑셀 파일 업로드
사이드바에서 투자검토 엑셀 파일을 업로드합니다.

### 2. 사용자 정보 입력
"홍길동, ABC스타트업" 형식으로 담당자와 기업명을 입력합니다.

### 3. 파일 분석
"파일 분석해줘"로 엑셀에서 투자조건, IS요약, Cap Table을 추출합니다.

### 4. Exit 프로젝션 생성
PER 배수와 목표 연도를 지정하여 프로젝션을 생성합니다.

**지원 분석 레벨:**
| 레벨 | 내용 |
|------|------|
| 기본 | 회사제시/심사역제시 기준 단순 Exit |
| 고급 | 부분 매각 + NPV 할인 |
| 완전 | SAFE 전환 + 콜옵션 + 희석 효과 |
    """)

with st.expander("Peer PER 분석 워크플로우", expanded=False):
    st.markdown("""
### 1. PDF 업로드 (선택)
기업 소개서나 IR 자료를 업로드합니다.

### 2. PDF 분석
"분석해줘"로 비즈니스 모델, 산업, 타겟 고객을 파악합니다.

### 3. Peer 기업 선정
메리가 유사 상장 기업을 제안합니다. 추가/수정 가능합니다.

### 4. PER 조회
Yahoo Finance에서 각 기업의 PER, 매출, 영업이익률을 조회합니다.

### 5. 프로젝션 지원
Peer 데이터 기반으로 매출 프로젝션을 도와드립니다:
- **역산**: 목표 기업가치 → 필요 매출/이익
- **순방향**: 현재 매출 → 연도별 성장 예측
    """)

with st.expander("티커 형식 가이드", expanded=False):
    st.markdown("""
### 미국 주식
- 심볼 그대로 사용: `AAPL`, `MSFT`, `GOOGL`

### 한국 주식
- KOSPI: `005930.KS` (삼성전자)
- KOSDAQ: `035720.KQ` (카카오)

### 예시
```
"Salesforce(CRM), ServiceNow(NOW), Workday(WDAY) PER 비교해줘"
"삼성전자(005930.KS), SK하이닉스(000660.KS) PER 알려줘"
```
    """)

# ========================================
# 푸터
# ========================================
st.divider()
st.markdown(
    """
    <div style="text-align: center; color: #64748b; font-size: 0.875rem;">
        Powered by Claude Opus 4.5 | VC Investment Agent v0.3.0
    </div>
    """,
    unsafe_allow_html=True
)
