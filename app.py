"""
VC 투자 분석 에이전트 - 홈페이지

실행: streamlit run app.py
"""

import json
import re
import streamlit as st
import streamlit.components.v1 as components

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
        min-height: 760px;
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
        height: 38%;
    }

    .graph-zone--governance {
        top: 42%;
        left: 10%;
        width: 80%;
        height: 22%;
    }

    .graph-zone--interaction {
        top: 67%;
        left: 5%;
        width: 90%;
        height: 28%;
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
        stroke: rgba(28, 25, 20, 0.28);
        stroke-width: 2.2;
        stroke-linecap: round;
        stroke-dasharray: 10 14;
        animation: dash 10s linear infinite;
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
        transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease;
        max-width: 360px;
        width: 100%;
        margin: 0 auto;
        min-height: 250px;
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
        border-color: rgba(28, 25, 20, 0.45) !important;
        color: var(--graph-ink) !important;
        background: rgba(255, 255, 255, 0.7) !important;
        min-height: 44px;
        font-weight: 600;
        letter-spacing: 0.02em;
        transition: transform 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
    }

    div[data-testid="stContainer"]:has(.graph-node-marker) .stButton > button:hover {
        background: rgba(28, 25, 20, 0.08) !important;
        box-shadow: 0 8px 16px rgba(25, 18, 9, 0.15);
        transform: translateY(-2px);
    }

    div[data-testid="stContainer"]:has(.graph-node-marker):hover {
        transform: translateY(-10px);
        box-shadow: 0 24px 50px rgba(25, 18, 9, 0.18);
        border-color: rgba(28, 25, 20, 0.28);
        animation-play-state: paused;
    }

    div[data-testid="stContainer"]:has(.graph-node-marker):hover::after {
        box-shadow: 0 0 0 8px rgba(204, 58, 43, 0.2);
    }

    @keyframes floatNode {
        0% { transform: translateY(0px); }
        50% { transform: translateY(-10px); }
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

    @keyframes dash {
        from { stroke-dashoffset: 0; }
        to { stroke-dashoffset: -120; }
    }

    @media (prefers-reduced-motion: reduce) {
        .graph-lines path,
        div[data-testid="stContainer"]:has(.graph-node-marker),
        div[data-testid="stContainer"]:has(.graph-canvas-marker)::after {
            animation: none !important;
        }
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

GRAPH_NODES = [
    {
        "id": "exit",
        "title": "Exit 프로젝션",
        "summary": "투자검토 엑셀 기반 Exit 분석.",
        "bullets": ["PER 시나리오/IRR/멀티플", "3-Tier 결과 엑셀 생성", "SAFE 전환 시나리오 지원"],
        "chips": ["Excel", "Scenario", "IRR"],
        "page": "Exit_Projection",
        "cta": "Exit 프로젝션 시작",
        "accent": "ember",
        "x": 50,
        "y": 12,
    },
    {
        "id": "peer",
        "title": "Peer PER 분석",
        "summary": "유사 상장 기업 PER 벤치마킹.",
        "bullets": ["PDF 기반 비즈니스 모델 파악", "Yahoo Finance PER 조회", "매출/목표가치 역산"],
        "chips": ["PDF", "Market", "PER"],
        "page": "Peer_PER_Analysis",
        "cta": "Peer PER 분석 시작",
        "accent": "amber",
        "x": 20,
        "y": 33,
    },
    {
        "id": "report",
        "title": "투자심사 보고서",
        "summary": "인수인의견 스타일 초안 생성.",
        "bullets": ["시장규모 근거 추출", "보고서 문장 초안", "확인 필요 사항 정리"],
        "chips": ["Report", "Evidence", "Draft"],
        "page": "Investment_Report",
        "cta": "투자심사 보고서 시작",
        "accent": "teal",
        "x": 80,
        "y": 33,
    },
    {
        "id": "hub",
        "title": "VC 투자 분석 그래프",
        "summary": "메리와 대화하며 각 모듈을 연결합니다.",
        "bullets": ["필요한 분석을 선택해 바로 시작", "각 모듈은 업무 흐름으로 연결"],
        "chips": ["Exit", "Peer", "Report", "Contract"],
        "page": "",
        "cta": "허브 노드",
        "accent": "hub",
        "x": 50,
        "y": 55,
    },
    {
        "id": "diagnosis",
        "title": "기업현황 진단시트",
        "summary": "진단시트 기반 컨설턴트 보고서.",
        "bullets": ["체크리스트 자동 분석", "점수/리포트 초안", "엑셀에 반영/저장"],
        "chips": ["Checklist", "Scoring"],
        "page": "Company_Diagnosis",
        "cta": "기업현황 진단시트 시작",
        "accent": "ember",
        "x": 22,
        "y": 80,
    },
    {
        "id": "contract",
        "title": "계약서 리서치",
        "summary": "텀싯/투자계약서 근거 기반 검토.",
        "bullets": ["PDF·DOCX 텍스트 추출", "핵심 항목/근거 스니펫", "문서 간 일치 여부 점검"],
        "chips": ["OCR", "Compare", "Risk"],
        "page": "Contract_Review",
        "cta": "계약서 리서치 시작",
        "accent": "amber",
        "x": 78,
        "y": 80,
    },
]

nodes_html = []
for node in GRAPH_NODES:
    bullet_html = "".join([f"<li>{item}</li>" for item in node.get("bullets", [])])
    chip_html = "".join([f"<span class='node-chip'>{chip}</span>" for chip in node.get("chips", [])])
    cta_label = node.get("cta", "시작")
    cta_html = (
        f"<button class='node-cta'>{cta_label}</button>"
        if node.get("page")
        else f"<div class='node-cta hub'>{cta_label}</div>"
    )
    nodes_html.append(
        f"""
        <div class="graph-node accent-{node['accent']}" data-node="{node['id']}" data-page="{node['page']}"
             style="--x:{node['x']};--y:{node['y']};">
            <div class="node-title">{node['title']}</div>
            <div class="node-summary">{node['summary']}</div>
            <ul class="node-list">{bullet_html}</ul>
            <div class="node-chips">{chip_html}</div>
            {cta_html}
        </div>
        """
    )

graph_nodes_markup = "\n".join(nodes_html)
page_slugs = [node["page"] for node in GRAPH_NODES if node.get("page")]

graph_html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {{
    --graph-bg: #f7f2ea;
    --graph-ink: #1c1914;
    --graph-muted: #5f554b;
    --graph-node-bg: rgba(255, 255, 255, 0.92);
    --graph-border: rgba(28, 25, 20, 0.16);
    --graph-shadow: 0 18px 40px rgba(25, 18, 9, 0.12);
    --accent-ember: #cc3a2b;
    --accent-amber: #d08a2e;
    --accent-teal: #1a8c86;
}}

html, body {{
    margin: 0;
    padding: 0;
    background: transparent;
    font-family: "Space Grotesk", "Noto Sans KR", sans-serif;
}}

.graph-shell {{
    position: relative;
    height: 760px;
    border-radius: 32px;
    background: var(--graph-bg);
    overflow: hidden;
    box-shadow: 0 30px 60px rgba(25, 18, 9, 0.08);
}}

.graph-shell::before {{
    content: "";
    position: absolute;
    inset: 0;
    background-image:
        radial-gradient(circle at 15% 10%, rgba(255, 247, 236, 0.9), rgba(255, 247, 236, 0) 40%),
        radial-gradient(circle at 85% 20%, rgba(255, 232, 218, 0.7), rgba(255, 232, 218, 0) 35%),
        repeating-linear-gradient(0deg, rgba(28, 25, 20, 0.06), rgba(28, 25, 20, 0.06) 1px, transparent 1px, transparent 28px),
        repeating-linear-gradient(90deg, rgba(28, 25, 20, 0.06), rgba(28, 25, 20, 0.06) 1px, transparent 1px, transparent 28px);
    opacity: 0.9;
    animation: haze 16s ease-in-out infinite;
    z-index: 0;
}}

.graph-lines {{
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    z-index: 1;
}}

.graph-zones {{
    position: absolute;
    inset: 0;
    z-index: 2;
    pointer-events: none;
}}

.graph-zone {{
    position: absolute;
    border: 1px dashed rgba(28, 25, 20, 0.2);
    border-radius: 28px;
    background: rgba(255, 255, 255, 0.45);
    backdrop-filter: blur(4px);
}}

.graph-zone span {{
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
    background: rgba(247, 242, 234, 0.95);
}}

.zone-analysis {{ top: 4%; left: 6%; width: 88%; height: 36%; }}
.zone-hub {{ top: 44%; left: 12%; width: 76%; height: 20%; }}
.zone-diligence {{ top: 68%; left: 6%; width: 88%; height: 26%; }}

.graph-node {{
    position: absolute;
    left: calc(var(--x) * 1%);
    top: calc(var(--y) * 1%);
    transform: translate(-50%, -50%);
    width: min(330px, 34vw);
    min-width: 240px;
    max-width: 360px;
    background: var(--graph-node-bg);
    border: 1px solid var(--graph-border);
    border-radius: 20px;
    padding: 16px 16px 12px 16px;
    box-shadow: var(--graph-shadow);
    z-index: 3;
    cursor: pointer;
    transition: border 0.2s ease, box-shadow 0.2s ease;
}}

.graph-node:hover {{
    border-color: rgba(28, 25, 20, 0.35);
    box-shadow: 0 26px 50px rgba(25, 18, 9, 0.18);
}}

.graph-node::after {{
    content: "";
    position: absolute;
    top: 16px;
    right: 16px;
    width: 10px;
    height: 10px;
    border-radius: 999px;
    box-shadow: 0 0 0 6px rgba(204, 58, 43, 0.14);
}}

.graph-node.accent-amber::after {{
    background: var(--accent-amber);
    box-shadow: 0 0 0 6px rgba(208, 138, 46, 0.16);
}}

.graph-node.accent-teal::after {{
    background: var(--accent-teal);
    box-shadow: 0 0 0 6px rgba(26, 140, 134, 0.16);
}}

.graph-node.accent-ember::after {{
    background: var(--accent-ember);
    box-shadow: 0 0 0 6px rgba(204, 58, 43, 0.16);
}}

.graph-node.accent-hub::after {{
    width: 14px;
    height: 14px;
    background: #11100f;
    box-shadow: 0 0 0 8px rgba(17, 16, 15, 0.1);
}}

.node-title {{
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 6px;
}}

.node-summary {{
    font-size: 13px;
    color: var(--graph-muted);
    margin-bottom: 10px;
}}

.node-list {{
    padding-left: 18px;
    margin: 0 0 10px 0;
    font-size: 12.5px;
    line-height: 1.6;
}}

.node-chips {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 10px;
}}

.node-chip {{
    font-family: "IBM Plex Mono", monospace;
    font-size: 10.5px;
    padding: 3px 8px;
    border-radius: 999px;
    border: 1px solid rgba(28, 25, 20, 0.12);
    background: rgba(255, 255, 255, 0.8);
}}

.node-cta {{
    display: block;
    width: 100%;
    text-align: center;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.02em;
    padding: 10px 12px;
    border-radius: 999px;
    border: none;
    background: rgba(28, 25, 20, 0.1);
    color: var(--graph-ink);
}}

.graph-node .node-cta {{
    cursor: pointer;
}}

.graph-node.accent-ember .node-cta {{
    background: rgba(204, 58, 43, 0.12);
}}

.graph-node.accent-amber .node-cta {{
    background: rgba(208, 138, 46, 0.12);
}}

.graph-node.accent-teal .node-cta {{
    background: rgba(26, 140, 134, 0.12);
}}

.graph-node.accent-hub .node-cta {{
    background: rgba(17, 16, 15, 0.08);
    cursor: default;
}}

.graph-shell.is-mobile {{
    height: auto;
    padding: 16px 12px 24px 12px;
}}

.graph-shell.is-mobile .graph-lines,
.graph-shell.is-mobile .graph-zones {{
    display: none;
}}

.graph-shell.is-mobile .graph-node {{
    position: relative;
    left: auto;
    top: auto;
    transform: none !important;
    margin: 14px auto;
    width: min(420px, 92%);
}}

@keyframes haze {{
    0% {{ filter: hue-rotate(0deg); opacity: 0.9; }}
    50% {{ filter: hue-rotate(8deg); opacity: 0.75; }}
    100% {{ filter: hue-rotate(0deg); opacity: 0.9; }}
}}
</style>
</head>
<body>
<div class="graph-shell" id="graph-shell">
    <canvas class="graph-lines" id="graph-lines"></canvas>
    <div class="graph-zones">
        <div class="graph-zone zone-analysis"><span>핵심 분석</span></div>
        <div class="graph-zone zone-hub"><span>인사이트 허브</span></div>
        <div class="graph-zone zone-diligence"><span>딜리전스</span></div>
    </div>
    {graph_nodes_markup}
</div>
<script>
const graph = document.getElementById("graph-shell");
const canvas = document.getElementById("graph-lines");
const ctx = canvas.getContext("2d");
const nodes = Array.from(document.querySelectorAll(".graph-node"));
const nodeMap = {{}};
const pageSlugs = {json.dumps(page_slugs, ensure_ascii=False)};
nodes.forEach((node) => {{
    nodeMap[node.dataset.node] = node;
}});

const edges = [
    ["exit", "peer"],
    ["exit", "report"],
    ["peer", "hub"],
    ["report", "hub"],
    ["hub", "diagnosis"],
    ["hub", "contract"],
];

let activeNode = null;

function resizeCanvas() {{
    const rect = graph.getBoundingClientRect();
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
    ctx.setTransform(window.devicePixelRatio, 0, 0, window.devicePixelRatio, 0, 0);
}}

function getCenter(node) {{
    const rect = node.getBoundingClientRect();
    const parent = graph.getBoundingClientRect();
    return {{
        x: rect.left - parent.left + rect.width / 2,
        y: rect.top - parent.top + rect.height / 2,
    }};
}}

function navigate(page) {{
    if (!page) return;
    const url = new URL(window.location.href);
    if (url.searchParams.has("page")) {{
        url.searchParams.set("page", page);
        window.location.href = url.toString();
        return;
    }}
    const segments = url.pathname.split("/").filter(Boolean);
    const last = segments.length ? segments[segments.length - 1] : "";
    const baseSegments = pageSlugs.includes(last) ? segments.slice(0, -1) : segments;
    const basePath = baseSegments.length ? `/${{baseSegments.join("/")}}` : "";
    window.location.href = `${{url.origin}}${{basePath}}/${{page}}`;
}}

nodes.forEach((node) => {{
    const page = node.dataset.page;
    if (!page) {{
        node.style.cursor = "default";
    }} else {{
        node.addEventListener("click", () => navigate(page));
    }}
    node.addEventListener("mouseenter", () => {{
        activeNode = node.dataset.node;
    }});
    node.addEventListener("mouseleave", () => {{
        activeNode = null;
    }});
}});

function updateLayout() {{
    const isMobile = graph.clientWidth < 900;
    graph.classList.toggle("is-mobile", isMobile);
    resizeCanvas();
}}

function drawLines(time) {{
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const dashOffset = -time * 0.05;

    edges.forEach(([from, to]) => {{
        const startNode = nodeMap[from];
        const endNode = nodeMap[to];
        if (!startNode || !endNode) return;
        const start = getCenter(startNode);
        const end = getCenter(endNode);
        const isActive = activeNode && (activeNode === from || activeNode === to);
        ctx.beginPath();
        ctx.setLineDash([10, 12]);
        ctx.lineDashOffset = dashOffset;
        ctx.strokeStyle = isActive ? "rgba(26, 140, 134, 0.65)" : "rgba(28, 25, 20, 0.28)";
        ctx.lineWidth = isActive ? 2.4 : 2.0;
        ctx.moveTo(start.x, start.y);
        ctx.lineTo(end.x, end.y);
        ctx.stroke();

        ctx.beginPath();
        ctx.setLineDash([]);
        ctx.fillStyle = isActive ? "rgba(26, 140, 134, 0.9)" : "rgba(28, 25, 20, 0.6)";
        ctx.arc(start.x, start.y, 4.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.arc(end.x, end.y, 4.5, 0, Math.PI * 2);
        ctx.fill();
    }});
}}

function animate(time) {{
    if (!graph.classList.contains("is-mobile")) {{
        nodes.forEach((node, idx) => {{
            const dx = Math.sin(time * 0.001 + idx) * 6;
            const dy = Math.cos(time * 0.0012 + idx) * 5;
            node.style.transform = `translate(-50%, -50%) translate(${{dx}}px, ${{dy}}px)`;
        }});
    }} else {{
        nodes.forEach((node) => {{
            node.style.transform = "";
        }});
    }}
    drawLines(time);
    requestAnimationFrame(animate);
}}

window.addEventListener("resize", updateLayout);
updateLayout();
requestAnimationFrame(animate);
</script>
</body>
</html>
"""

components.html(graph_html, height=780, scrolling=False)

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
