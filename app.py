"""
VC 투자 분석 에이전트 - 홈페이지

실행: streamlit run app.py
"""

import re
import streamlit as st

from shared.config import (
    get_avatar_image,
    get_header_image,
    get_user_avatar_image,
    initialize_session_state,
    inject_custom_css,
)
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

    .graph-zones {
        position: absolute;
        inset: 0;
        pointer-events: none;
        z-index: 1;
    }

    .graph-zone {
        position: absolute;
        border: 1px dashed rgba(28, 25, 20, 0.18);
        border-radius: 26px;
        background: rgba(255, 255, 255, 0.45);
        backdrop-filter: blur(4px);
    }

    .graph-zone__label {
        position: absolute;
        top: 12px;
        left: 16px;
        font-family: "IBM Plex Mono", monospace;
        font-size: 11px;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--graph-muted);
        padding: 4px 10px;
        border-radius: 999px;
        border: 1px solid rgba(28, 25, 20, 0.12);
        background: rgba(247, 242, 234, 0.9);
    }

    .graph-zone--analysis {
        top: 2%;
        left: 5%;
        width: 90%;
        height: 42%;
    }

    .graph-zone--governance {
        top: 48%;
        left: 5%;
        width: 90%;
        height: 24%;
    }

    .graph-zone--interaction {
        top: 75%;
        left: 12%;
        width: 76%;
        height: 20%;
    }

    .graph-lines {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: 2;
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
        z-index: 3;
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
        <div class="graph-zones">
            <div class="graph-zone graph-zone--analysis">
                <span class="graph-zone__label">Core Analysis</span>
            </div>
            <div class="graph-zone graph-zone--governance">
                <span class="graph-zone__label">Governance</span>
            </div>
            <div class="graph-zone graph-zone--interaction">
                <span class="graph-zone__label">Interaction</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
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
# 홈 안내 챗봇
# ========================================
st.markdown("## 메리 안내 데스크")
st.caption("필요한 업무를 말하면 해당 모듈로 안내합니다.")

avatar_image = get_avatar_image()
user_avatar_image = get_user_avatar_image()

ROUTE_DEFS = [
    {
        "id": "exit",
        "label": "Exit 프로젝션",
        "page": "pages/1_Exit_Projection.py",
        "summary": "엑셀 기반 Exit/IRR/멀티플 분석 요청에 적합합니다.",
        "next_step": "투자검토 엑셀을 업로드하고 \"파일 분석해줘\"라고 입력하세요.",
        "strong_keywords": ["exit", "프로젝션", "irr", "멀티플"],
        "keywords": [
            "exit", "프로젝션", "irr", "멀티플", "multiple", "valuation",
            "safe", "cap", "captable", "투자조건", "엑셀", "excel", "xlsx", "기업가치",
        ],
    },
    {
        "id": "peer",
        "label": "Peer PER 분석",
        "page": "pages/2_Peer_PER_Analysis.py",
        "summary": "유사 상장기업 PER/벤치마크 비교에 적합합니다.",
        "next_step": "PDF를 업로드하거나 티커를 바로 입력하세요.",
        "strong_keywords": ["peer", "per", "유사기업", "비교기업"],
        "keywords": [
            "peer", "per", "유사", "비교", "벤치", "상장", "티커", "yahoo",
            "comparables", "기업소개서", "ir", "pdf",
        ],
    },
    {
        "id": "diagnosis",
        "label": "기업현황 진단시트",
        "page": "pages/3_Company_Diagnosis.py",
        "summary": "진단시트 기반 컨설턴트 보고서 작성에 적합합니다.",
        "next_step": "진단시트 엑셀을 업로드하고 \"분석해줘\"라고 입력하세요.",
        "strong_keywords": ["진단", "기업현황", "체크리스트"],
        "keywords": [
            "진단", "기업현황", "체크리스트", "자가진단", "컨설턴트", "diagnosis",
            "점수", "reportdraft",
        ],
    },
    {
        "id": "report",
        "label": "투자심사 보고서",
        "page": "pages/4_Investment_Report.py",
        "summary": "시장규모 근거 추출 및 인수인의견 스타일 초안에 적합합니다.",
        "next_step": "기업 자료(PDF/엑셀)를 업로드하고 근거 정리를 요청하세요.",
        "strong_keywords": ["투자심사", "인수인의견", "시장규모", "보고서"],
        "keywords": [
            "투자심사", "인수인의견", "보고서", "시장규모", "근거", "report",
            "증거", "시장", "draft",
        ],
    },
    {
        "id": "voice",
        "label": "Voice Agent",
        "page": "pages/5_Voice_Agent.py",
        "summary": "체크인/원온원 음성 대화에 적합합니다.",
        "next_step": "모드(체크인/원온원)를 선택하고 시작하세요.",
        "strong_keywords": ["체크인", "원온원", "음성"],
        "keywords": [
            "체크인", "원온원", "음성", "voice", "stt", "tts", "1on1",
        ],
    },
    {
        "id": "contract",
        "label": "계약서 리서치",
        "page": "pages/7_Contract_Review.py",
        "summary": "텀싯/투자계약서 검토 및 내용 일치 확인에 적합합니다.",
        "next_step": "텀싯/투자계약서 PDF·DOCX를 업로드하세요.",
        "strong_keywords": ["계약", "계약서", "텀싯", "투자계약"],
        "keywords": [
            "계약", "계약서", "텀싯", "termsheet", "투자계약", "주주간",
            "청산", "희석", "보호", "조항",
        ],
    },
]

ROUTE_MAP = {}
for route in ROUTE_DEFS:
    label_compact = re.sub(r"[\\s\\-_/]+", "", route["label"].lower())
    route["label_compact"] = label_compact
    route["keywords_compact"] = [
        re.sub(r"[\\s\\-_/]+", "", kw.lower()) for kw in route["keywords"] if kw
    ]
    route["strong_keywords_compact"] = [
        re.sub(r"[\\s\\-_/]+", "", kw.lower()) for kw in route.get("strong_keywords", []) if kw
    ]
    ROUTE_MAP[route["id"]] = route


def _compact_text(text: str) -> str:
    return re.sub(r"[\\s\\-_/]+", "", (text or "").lower())


def _resolve_candidate_choice(compact_text: str, candidate_ids: list[str]):
    if compact_text.isdigit():
        idx = int(compact_text) - 1
        if 0 <= idx < len(candidate_ids):
            return ROUTE_MAP.get(candidate_ids[idx])
    for route_id in candidate_ids:
        route = ROUTE_MAP.get(route_id)
        if not route:
            continue
        if route["label_compact"] in compact_text or route_id in compact_text:
            return route
    return None


def _score_routes(compact_text: str) -> list[tuple[int, dict]]:
    scored = []
    for route in ROUTE_DEFS:
        score = 0
        for kw in route.get("strong_keywords_compact", []):
            if kw and kw in compact_text:
                score += 2
        for kw in route.get("keywords_compact", []):
            if kw and kw in compact_text:
                score += 1
        if score:
            scored.append((score, route))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


def _route_message(user_text: str) -> str:
    compact_text = _compact_text(user_text)
    state = st.session_state.home_router_state
    candidates = state.get("candidates", [])

    if candidates:
        selection = _resolve_candidate_choice(compact_text, candidates)
        if selection:
            state["candidates"] = []
            st.session_state.home_route_target = selection["page"]
            st.session_state.home_route_label = selection["label"]
            return (
                f"추천 모듈: {selection['label']}\n\n"
                f"이유: {selection['summary']}\n\n"
                f"다음: {selection['next_step']}\n\n"
                "아래 바로 이동 버튼을 눌러주세요."
            )
        if any(word in compact_text for word in ["아니", "다른", "none", "no"]):
            state["candidates"] = []
            st.session_state.home_route_target = None
            st.session_state.home_route_label = ""
            return "원하는 업무를 한 줄로 다시 알려주세요. 예: \"텀싯 검토\", \"PER 비교\", \"투자심사 보고서\""

    if not compact_text:
        st.session_state.home_route_target = None
        st.session_state.home_route_label = ""
        return "원하는 업무를 한 줄로 알려주세요. 예: \"텀싯 검토\", \"PER 비교\", \"투자심사 보고서\""

    scored = _score_routes(compact_text)
    if not scored:
        st.session_state.home_route_target = None
        st.session_state.home_route_label = ""
        return (
            "아직 어떤 업무인지 파악하기 어려워요.\n\n"
            "예시:\n"
            "- \"투자검토 엑셀 Exit 분석\"\n"
            "- \"유사기업 PER 비교\"\n"
            "- \"투자계약서 내용 일치 확인\"\n"
            "- \"시장규모 근거 정리\""
        )

    top_score = scored[0][0]
    top_routes = [route for score, route in scored if score == top_score]
    if len(top_routes) == 1 or top_score >= 2:
        selection = top_routes[0]
        st.session_state.home_route_target = selection["page"]
        st.session_state.home_route_label = selection["label"]
        st.session_state.home_router_state["candidates"] = []
        return (
            f"추천 모듈: {selection['label']}\n\n"
            f"이유: {selection['summary']}\n\n"
            f"다음: {selection['next_step']}\n\n"
            "아래 바로 이동 버튼을 눌러주세요."
        )

    candidate_ids = [route["id"] for route in top_routes[:3]]
    st.session_state.home_router_state["candidates"] = candidate_ids
    st.session_state.home_route_target = None
    st.session_state.home_route_label = ""
    options = "\n".join(
        [f"{idx + 1}. {ROUTE_MAP[candidate]['label']}" for idx, candidate in enumerate(candidate_ids)]
    )
    return (
        "어떤 업무인지 조금만 더 알려주세요. 아래 중 번호로 선택해 주세요.\n\n"
        f"{options}"
    )


chat_container = st.container(border=True, height=420)
with chat_container:
    chat_area = st.container(height=320)
    with chat_area:
        if not st.session_state.home_messages:
            with st.chat_message("assistant", avatar=avatar_image):
                st.markdown(
                    "안녕하세요. 필요한 업무를 말해주시면 적절한 모듈로 안내하겠습니다.\n\n"
                    "예: \"텀싯 검토\", \"PER 비교\", \"Exit 프로젝션\""
                )

        for msg in st.session_state.home_messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                with st.chat_message("user", avatar=user_avatar_image):
                    st.markdown(content)
            else:
                with st.chat_message("assistant", avatar=avatar_image):
                    st.markdown(content)

    user_input = st.chat_input("필요한 업무를 한 줄로 알려주세요.", key="home_chat_input")

if user_input:
    st.session_state.home_messages.append({"role": "user", "content": user_input})
    response = _route_message(user_input)
    st.session_state.home_messages.append({"role": "assistant", "content": response})
    st.rerun()

route_target = st.session_state.get("home_route_target")
route_label = st.session_state.get("home_route_label")
if route_target and route_label:
    if st.button(f"{route_label} 바로 이동", type="primary", use_container_width=True, key="home_route_jump"):
        st.switch_page(route_target)

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
