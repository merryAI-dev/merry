"""
VC 투자 분석 에이전트 - 홈페이지

실행: streamlit run app.py
"""

import json
import re
from pathlib import Path
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
from shared.team_tasks import TeamTaskStore, STATUS_LABELS, format_remaining_kst, normalize_status
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
            <div class="graph-hero__kicker">메리 안내 데스크</div>
            <h1 class="graph-hero__title">VC 투자 분석 에이전트</h1>
            <p class="graph-hero__desc">
                안녕하세요 사내기업가님. 투자를 도와드리는 메리입니다. 무엇을 도와드릴까요?
                아래 모듈을 살펴보고 혹시 궁금하시면 아래 안내데스크에 문의해주세요!
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
        "title": "협업 허브",
        "summary": "팀 과업·서류·일정을 한 곳에서 관리합니다.",
        "bullets": ["팀 과업 보드/담당자 배정", "필수 서류/Drive 업로드 체크", "AI 협업 브리프 생성"],
        "chips": ["Tasks", "Docs", "Calendar", "Brief"],
        "page": "Collaboration_Hub",
        "cta": "협업 허브 열기",
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
        f"<button class='node-cta' data-page='{node['page']}'>{cta_label}</button>"
        if node.get("page")
        else f"<div class='node-cta is-disabled'>{cta_label}</div>"
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
graph_data = {
    node["id"]: {
        "title": node["title"],
        "summary": node["summary"],
        "bullets": node.get("bullets", []),
        "chips": node.get("chips", []),
        "page": node.get("page", ""),
        "cta": node.get("cta", ""),
        "accent": node.get("accent", "ember"),
    }
    for node in GRAPH_NODES
}
graph_data_json = json.dumps(graph_data, ensure_ascii=False)

graph_html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body {{
    margin: 0;
    padding: 0;
    background: transparent;
    font-family: "Space Grotesk", "Noto Sans KR", sans-serif;
}}

.graph-shell {{
    --graph-bg: #f7f2ea;
    --graph-ink: #1c1914;
    --graph-muted: #5f554b;
    --graph-node-bg: rgba(255, 255, 255, 0.92);
    --graph-border: rgba(28, 25, 20, 0.16);
    --graph-shadow: 0 18px 40px rgba(25, 18, 9, 0.12);
    --accent-ember: #cc3a2b;
    --accent-amber: #d08a2e;
    --accent-teal: #1a8c86;
    position: relative;
    height: 780px;
    border-radius: 32px;
    background: var(--graph-bg);
    overflow: hidden;
    box-shadow: 0 30px 60px rgba(25, 18, 9, 0.08);
    cursor: grab;
}}

.graph-shell.is-dragging {{
    cursor: grabbing;
}}

.graph-shell.theme-dark {{
    --graph-bg: #141210;
    --graph-ink: #f5f2ec;
    --graph-muted: #b2aaa0;
    --graph-node-bg: rgba(30, 27, 22, 0.95);
    --graph-border: rgba(240, 234, 226, 0.12);
    --graph-shadow: 0 18px 40px rgba(0, 0, 0, 0.45);
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

.graph-shell.theme-dark::before {{
    background-image:
        radial-gradient(circle at 15% 10%, rgba(46, 40, 34, 0.9), rgba(46, 40, 34, 0) 40%),
        radial-gradient(circle at 85% 20%, rgba(40, 32, 27, 0.8), rgba(40, 32, 27, 0) 35%),
        repeating-linear-gradient(0deg, rgba(240, 234, 226, 0.08), rgba(240, 234, 226, 0.08) 1px, transparent 1px, transparent 28px),
        repeating-linear-gradient(90deg, rgba(240, 234, 226, 0.08), rgba(240, 234, 226, 0.08) 1px, transparent 1px, transparent 28px);
    opacity: 0.75;
}}

.graph-lines {{
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    z-index: 1;
    pointer-events: none;
}}

.graph-stage {{
    position: absolute;
    inset: 0;
    transform-origin: top left;
    z-index: 2;
}}


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
    transition: border 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}}

.graph-node:hover {{
    border-color: rgba(28, 25, 20, 0.35);
    box-shadow: 0 26px 50px rgba(25, 18, 9, 0.18);
    transform: translate(-50%, -50%) translateY(-4px);
}}

.graph-node.is-active {{
    border-color: rgba(26, 140, 134, 0.55);
    box-shadow: 0 24px 60px rgba(26, 140, 134, 0.18);
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
    color: var(--graph-ink);
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
    color: var(--graph-ink);
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
    color: var(--graph-ink);
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

.node-cta.is-disabled {{
    opacity: 0.7;
}}

.graph-controls {{
    position: absolute;
    top: 18px;
    right: 18px;
    display: flex;
    gap: 8px;
    z-index: 5;
}}

.graph-btn {{
    border-radius: 999px;
    border: 1px solid rgba(28, 25, 20, 0.2);
    background: rgba(255, 255, 255, 0.8);
    color: var(--graph-ink);
    font-size: 12px;
    font-weight: 600;
    padding: 6px 12px;
    cursor: pointer;
}}

.graph-panel {{
    position: absolute;
    right: 24px;
    bottom: 24px;
    width: min(280px, 32vw);
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid rgba(28, 25, 20, 0.12);
    border-radius: 20px;
    padding: 14px;
    box-shadow: 0 16px 36px rgba(25, 18, 9, 0.12);
    z-index: 4;
}}

.graph-shell.theme-dark .graph-panel {{
    background: rgba(24, 21, 18, 0.92);
    border-color: rgba(240, 234, 226, 0.12);
}}

.panel-kicker {{
    font-family: "IBM Plex Mono", monospace;
    font-size: 11px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--graph-muted);
}}

.panel-title {{
    font-size: 16px;
    font-weight: 600;
    margin: 6px 0;
    color: var(--graph-ink);
}}

.panel-summary {{
    font-size: 12.5px;
    color: var(--graph-muted);
    margin-bottom: 10px;
}}

.panel-list {{
    padding-left: 18px;
    margin: 0 0 10px 0;
    font-size: 12px;
    line-height: 1.6;
    color: var(--graph-ink);
}}

.panel-chips {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 10px;
}}

.panel-chip {{
    font-family: "IBM Plex Mono", monospace;
    font-size: 10px;
    padding: 3px 8px;
    border-radius: 999px;
    border: 1px solid rgba(28, 25, 20, 0.12);
    background: rgba(255, 255, 255, 0.8);
}}

.panel-cta {{
    width: 100%;
    border-radius: 999px;
    border: 1px solid rgba(28, 25, 20, 0.2);
    padding: 8px 10px;
    font-size: 12.5px;
    font-weight: 600;
    background: rgba(28, 25, 20, 0.08);
    cursor: pointer;
}}

.panel-cta:disabled {{
    cursor: default;
    opacity: 0.6;
}}

.graph-hint {{
    position: absolute;
    left: 24px;
    bottom: 24px;
    font-size: 11px;
    color: var(--graph-muted);
    z-index: 4;
}}

.graph-shell.is-mobile {{
    height: auto;
    padding: 16px 12px 80px 12px;
    cursor: default;
}}

.graph-shell.is-mobile .graph-lines,
.graph-shell.is-mobile .graph-panel,
.graph-shell.is-mobile .graph-hint {{
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
    <div class="graph-stage" id="graph-stage">
        {graph_nodes_markup}
    </div>
    <div class="graph-panel" id="graph-panel">
        <div class="panel-kicker">Module Preview</div>
        <div class="panel-title" id="panel-title"></div>
        <div class="panel-summary" id="panel-summary"></div>
        <ul class="panel-list" id="panel-list"></ul>
        <div class="panel-chips" id="panel-chips"></div>
        <button class="panel-cta" id="panel-cta">이동</button>
    </div>
    <div class="graph-controls">
        <button class="graph-btn" id="reset-view">Reset</button>
        <button class="graph-btn" id="theme-toggle">Dark</button>
    </div>
    <div class="graph-hint">Drag to pan · Scroll to zoom · Double click to center</div>
</div>
<script>
const graph = document.getElementById("graph-shell");
const stage = document.getElementById("graph-stage");
const canvas = document.getElementById("graph-lines");
const ctx = canvas.getContext("2d");
const nodes = Array.from(document.querySelectorAll(".graph-node"));
const panelTitle = document.getElementById("panel-title");
const panelSummary = document.getElementById("panel-summary");
const panelList = document.getElementById("panel-list");
const panelChips = document.getElementById("panel-chips");
const panelCta = document.getElementById("panel-cta");
const resetBtn = document.getElementById("reset-view");
const themeToggle = document.getElementById("theme-toggle");
const nodeData = {graph_data_json};
const pageSlugs = {json.dumps(page_slugs, ensure_ascii=False)};
const nodeMap = {{}};
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

const state = {{ panX: 0, panY: 0, zoom: 1 }};
let hoverNodeId = null;
let activeNodeId = "hub";
let draggingNode = null;
let draggingGraph = false;
let dragMoved = false;
let dragOffset = {{ x: 0, y: 0 }};
let dragPointer = {{ x: 0, y: 0 }};

function clamp(value, min, max) {{
    return Math.min(Math.max(value, min), max);
}}

function updateTheme() {{
    const current = graph.classList.contains("theme-dark");
    themeToggle.textContent = current ? "Light" : "Dark";
}}

function setTheme(mode) {{
    graph.classList.toggle("theme-dark", mode === "dark");
    localStorage.setItem("graphTheme", mode);
    updateTheme();
}}

const storedTheme = localStorage.getItem("graphTheme") || "light";
setTheme(storedTheme);

themeToggle.addEventListener("click", () => {{
    const next = graph.classList.contains("theme-dark") ? "light" : "dark";
    setTheme(next);
}});

function applyTransform() {{
    stage.style.transform = `translate(${{state.panX}}px, ${{state.panY}}px) scale(${{state.zoom}})`;
}}

function resetView() {{
    state.panX = 0;
    state.panY = 0;
    state.zoom = 1;
    applyTransform();
}}

resetBtn.addEventListener("click", resetView);
graph.addEventListener("dblclick", resetView);

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

function toGraphPoint(clientX, clientY) {{
    const rect = graph.getBoundingClientRect();
    return {{
        x: (clientX - rect.left - state.panX) / state.zoom,
        y: (clientY - rect.top - state.panY) / state.zoom,
    }};
}}

function buildTarget(page) {{
    const url = new URL(window.location.href);
    const segments = url.pathname.split("/").filter(Boolean);
    const last = segments.length ? segments[segments.length - 1] : "";
    const baseSegments = pageSlugs.includes(last) ? segments.slice(0, -1) : segments;
    const basePath = baseSegments.length ? `/${{baseSegments.join("/")}}` : "";
    return `${{url.origin}}${{basePath}}/?page=${{page}}`;
}}

function navigate(page) {{
    if (!page) return;
    const target = buildTarget(page);
    const attempts = [
        () => window.top.location.assign(target),
        () => window.parent.location.assign(target),
        () => window.open(target, "_top"),
        () => window.open(target, "_self"),
    ];
    for (const attempt of attempts) {{
        try {{
            attempt();
            return;
        }} catch (err) {{
            continue;
        }}
    }}
    window.location.href = target;
}}

function renderPanel(nodeId) {{
    const data = nodeData[nodeId] || nodeData.hub;
    panelTitle.textContent = data.title || "";
    panelSummary.textContent = data.summary || "";
    panelList.innerHTML = (data.bullets || []).map((item) => `<li>${{item}}</li>`).join("");
    panelChips.innerHTML = (data.chips || []).map((item) => `<span class="panel-chip">${{item}}</span>`).join("");
    panelCta.textContent = data.page ? (data.cta || "이동") : "그래프 허브";
    panelCta.disabled = !data.page;
    panelCta.dataset.page = data.page || "";
    nodes.forEach((node) => {{
        node.classList.toggle("is-active", node.dataset.node === nodeId);
    }});
}}

panelCta.addEventListener("click", (event) => {{
    const page = event.currentTarget.dataset.page;
    if (page) {{
        navigate(page);
    }}
}});

nodes.forEach((node, index) => {{
    const nodeId = node.dataset.node;
    const page = node.dataset.page;
    const cta = node.querySelector(".node-cta");

    node.addEventListener("mouseenter", () => {{
        hoverNodeId = nodeId;
        renderPanel(nodeId);
    }});
    node.addEventListener("mouseleave", () => {{
        hoverNodeId = null;
    }});
    node.addEventListener("click", (event) => {{
        if (node.dataset.dragging === "true") {{
            node.dataset.dragging = "false";
            return;
        }}
        activeNodeId = nodeId;
        renderPanel(nodeId);
    }});
    node.addEventListener("dblclick", () => {{
        if (page) {{
            navigate(page);
        }}
    }});
    if (cta) {{
        cta.addEventListener("click", (event) => {{
            event.stopPropagation();
            if (page) {{
                navigate(page);
            }}
        }});
    }}

    node.addEventListener("pointerdown", (event) => {{
        if (event.target.closest(".node-cta")) {{
            return;
        }}
        draggingNode = node;
        dragMoved = false;
        node.dataset.dragging = "false";
        node.setPointerCapture(event.pointerId);
        dragPointer = toGraphPoint(event.clientX, event.clientY);
        const rect = graph.getBoundingClientRect();
        const nodeX = parseFloat(node.style.getPropertyValue("--x") || node.dataset.x || 50) / 100 * rect.width;
        const nodeY = parseFloat(node.style.getPropertyValue("--y") || node.dataset.y || 50) / 100 * rect.height;
        dragOffset = {{ x: dragPointer.x - nodeX, y: dragPointer.y - nodeY }};
    }});
}});

graph.addEventListener("pointerdown", (event) => {{
    if (event.target.closest(".graph-node") || event.target.closest(".graph-panel") || event.target.closest(".graph-controls")) {{
        return;
    }}
    draggingGraph = true;
    graph.classList.add("is-dragging");
    dragPointer = {{ x: event.clientX - state.panX, y: event.clientY - state.panY }};
}});

graph.addEventListener("pointermove", (event) => {{
    if (draggingNode) {{
        const rect = graph.getBoundingClientRect();
        const point = toGraphPoint(event.clientX, event.clientY);
        const newX = clamp(((point.x - dragOffset.x) / rect.width) * 100, 8, 92);
        const newY = clamp(((point.y - dragOffset.y) / rect.height) * 100, 8, 92);
        draggingNode.style.setProperty("--x", newX.toFixed(2));
        draggingNode.style.setProperty("--y", newY.toFixed(2));
        draggingNode.dataset.dragging = "true";
        dragMoved = true;
        return;
    }}
    if (draggingGraph) {{
        state.panX = event.clientX - dragPointer.x;
        state.panY = event.clientY - dragPointer.y;
        applyTransform();
    }}
}});

graph.addEventListener("pointerup", () => {{
    draggingNode = null;
    draggingGraph = false;
    graph.classList.remove("is-dragging");
}});

graph.addEventListener("pointerleave", () => {{
    draggingNode = null;
    draggingGraph = false;
    graph.classList.remove("is-dragging");
}});

graph.addEventListener("wheel", (event) => {{
    event.preventDefault();
    const rect = graph.getBoundingClientRect();
    const pointerX = event.clientX - rect.left;
    const pointerY = event.clientY - rect.top;
    const worldX = (pointerX - state.panX) / state.zoom;
    const worldY = (pointerY - state.panY) / state.zoom;
    const zoomFactor = event.deltaY < 0 ? 1.08 : 0.92;
    const nextZoom = clamp(state.zoom * zoomFactor, 0.7, 1.6);
    state.panX = pointerX - worldX * nextZoom;
    state.panY = pointerY - worldY * nextZoom;
    state.zoom = nextZoom;
    applyTransform();
}}, {{ passive: false }});

function drawLines(time) {{
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const dashOffset = -time * 0.06;
    const highlight = hoverNodeId || activeNodeId;

    edges.forEach(([from, to]) => {{
        const startNode = nodeMap[from];
        const endNode = nodeMap[to];
        if (!startNode || !endNode) return;
        const start = getCenter(startNode);
        const end = getCenter(endNode);
        const isActive = highlight && (highlight === from || highlight === to);
        ctx.beginPath();
        ctx.setLineDash([10, 12]);
        ctx.lineDashOffset = dashOffset;
        ctx.strokeStyle = isActive ? "rgba(26, 140, 134, 0.65)" : "rgba(28, 25, 20, 0.3)";
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
            if (node === draggingNode) {{
                return;
            }}
            const dx = Math.sin(time * 0.001 + idx) * 5;
            const dy = Math.cos(time * 0.0012 + idx) * 4;
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

function updateLayout() {{
    const isMobile = graph.clientWidth < 900;
    graph.classList.toggle("is-mobile", isMobile);
    resizeCanvas();
}}

window.addEventListener("resize", updateLayout);
updateLayout();
renderPanel(activeNodeId);
applyTransform();
requestAnimationFrame(animate);
</script>
</body>
</html>
"""

components.html(graph_html, height=780, scrolling=False)

st.divider()

# ========================================
# 팀 과업 요약
# ========================================
st.markdown("## 팀 과업 요약")
team_id = st.session_state.get("team_id") or st.session_state.get("user_id")
task_store = TeamTaskStore(team_id=team_id)
team_tasks = task_store.list_tasks(include_done=True, limit=24)

status_groups = {"todo": [], "in_progress": [], "done": []}
for task in team_tasks:
    status_key = normalize_status(task.get("status", "todo"))
    status_groups.setdefault(status_key, []).append(task)

cols = st.columns(3)
for col, key in zip(cols, ["todo", "in_progress", "done"]):
    with col:
        st.markdown(f"### {STATUS_LABELS.get(key, key)}")
        tasks = status_groups.get(key, [])
        if not tasks:
            st.caption("비어 있음")
        else:
            for task in tasks[:4]:
                title = task.get("title", "")
                owner = task.get("owner") or "담당 미정"
                due_date = task.get("due_date", "")
                remaining = format_remaining_kst(due_date)
                with st.container(border=True):
                    st.markdown(f"**{title}**")
                    st.caption(f"담당: {owner}")
                    if due_date:
                        if remaining:
                            st.caption(f"마감: {due_date} · {remaining}")
                        else:
                            st.caption(f"마감: {due_date}")
                    else:
                        st.caption("마감: 미설정")
        if len(status_groups.get(key, [])) > 4:
            st.caption("더 많은 과업은 Voice Agent에서 확인하세요.")

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
        "id": "collab",
        "label": "협업 허브",
        "page": "pages/0_Collaboration_Hub.py",
        "summary": "팀 과업, 서류, 일정, 코멘트를 통합 관리합니다.",
        "next_step": "협업 허브로 이동해 팀 상태를 확인하세요.",
        "strong_keywords": ["협업", "허브", "팀", "과업", "캘린더"],
        "keywords": [
            "협업", "허브", "팀", "과업", "업무", "일정", "캘린더", "코멘트",
            "docs", "문서", "체크리스트", "drive", "업로드", "collab", "hub",
        ],
    },
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
        "strong_keywords": ["투자심사", "인수인의견", "시장규모", "보고서", "DART", "증권신고서"],
        "keywords": [
            "투자심사", "인수인의견", "보고서", "시장규모", "근거", "report",
            "증거", "시장", "draft",
            "dart", "공시", "증권신고서", "수요예측", "공모", "underwriter",
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


def _looks_like_dart_query(text: str) -> bool:
    lowered = (text or "").lower()
    dart_keywords = [
        "dart", "공시", "증권신고서", "인수의견", "인수인의견",
        "underwriter", "수요예측", "공모", "상장",
    ]
    return any(keyword in lowered for keyword in dart_keywords)


def _detect_dart_category(text: str) -> str | None:
    lowered = (text or "").lower()
    if any(k in lowered for k in ["시장규모", "시장 규모", "tam", "sam", "som", "cagr", "성장률"]):
        return "market_size"
    if any(k in lowered for k in ["비교기업", "유사기업", "comparables", "peer"]):
        return "comparables"
    if any(k in lowered for k in ["공모가", "공모가격", "per", "pbr", "psr", "ev/ebitda", "valuation", "밸류"]):
        return "valuation"
    if any(k in lowered for k in ["수요예측", "수요 예측"]):
        return "demand_forecast"
    if any(k in lowered for k in ["리스크", "위험", "불확실", "불확실성"]):
        return "risk"
    return None


def _dart_status_message(path: str | None, error: str | None = None) -> str:
    if error:
        return (
            "DART 인수인의견 데이터셋을 찾지 못했습니다.\n\n"
            f"사유: {error}\n\n"
            "해결 방법:\n"
            "- `python scripts/dart_extract_underwriter_opinion.py --out temp/dart_underwriter_opinion_latest` 실행\n"
            "- 또는 `UNDERWRITER_DATA_PATH` 환경변수로 JSONL 경로 지정\n"
            "- temp/ 하위에 `underwriter_opinion.jsonl` 파일이 있어야 합니다."
        )
    if not path:
        return (
            "DART 인수인의견 데이터셋을 찾지 못했습니다.\n\n"
            "해결 방법:\n"
            "- `python scripts/dart_extract_underwriter_opinion.py --out temp/dart_underwriter_opinion_latest` 실행\n"
            "- 또는 `UNDERWRITER_DATA_PATH` 환경변수로 JSONL 경로 지정"
        )
    try:
        size_mb = Path(path).stat().st_size / (1024 * 1024)
        size_text = f"{size_mb:.1f}MB"
    except OSError:
        size_text = "알 수 없음"
    return (
        "DART 인수인의견 데이터셋이 준비되어 있습니다.\n\n"
        f"- 경로: {path}\n"
        f"- 파일 크기: {size_text}\n\n"
        "원하시는 키워드를 알려주시면 해당 문장을 바로 찾아드릴게요. "
        "예: \"시장규모 근거\", \"비교기업 선정\", \"수요예측\""
    )


def _handle_dart_query(user_text: str) -> str:
    try:
        from agent.tools import _resolve_underwriter_data_path, execute_search_underwriter_opinion_similar
    except Exception:
        return (
            "DART 인수인의견 검색 모듈을 불러오지 못했습니다.\n\n"
            "투자심사 보고서 모듈에서 다시 시도해 주세요."
        )

    resolved_path, resolve_error = _resolve_underwriter_data_path(None)
    lowered = (user_text or "").lower()
    status_only = any(token in lowered for token in ["데이터", "데이터셋", "dataset", "어디", "파일", "경로"])
    wants_snippet = any(token in lowered for token in ["근거", "문장", "찾", "검색", "인용", "요약"])

    if not resolved_path or resolve_error:
        st.session_state.home_route_target = "pages/4_Investment_Report.py"
        st.session_state.home_route_label = "투자심사 보고서"
        return _dart_status_message(resolved_path, resolve_error)

    if status_only and not wants_snippet:
        st.session_state.home_route_target = "pages/4_Investment_Report.py"
        st.session_state.home_route_label = "투자심사 보고서"
        return _dart_status_message(resolved_path, None)

    category = _detect_dart_category(user_text)
    result = execute_search_underwriter_opinion_similar(
        query=user_text,
        category=category,
        top_k=3,
        max_chars=420,
        min_score=0.08,
        return_patterns=True,
    )

    if not result.get("success"):
        st.session_state.home_route_target = "pages/4_Investment_Report.py"
        st.session_state.home_route_label = "투자심사 보고서"
        return _dart_status_message(resolved_path, result.get("error"))

    results = result.get("results", [])
    patterns = result.get("patterns", [])
    if not results:
        st.session_state.home_route_target = "pages/4_Investment_Report.py"
        st.session_state.home_route_label = "투자심사 보고서"
        return (
            "DART 인수인의견 데이터셋에서 관련 문장을 찾지 못했습니다.\n\n"
            "다른 키워드로 다시 요청해 주세요. "
            "예: \"시장규모 근거\", \"비교기업 선정\", \"수요예측\""
        )

    lines = ["DART 인수인의견 데이터셋에서 관련 근거를 찾았습니다.\n"]
    for idx, item in enumerate(results, 1):
        corp = item.get("corp_name", "미상")
        report = item.get("report_nm", "")
        title = item.get("section_title", "")
        snippet = (item.get("snippet") or "").strip()
        lines.append(f"{idx}. {corp} | {report} | {title}")
        if snippet:
            lines.append(f"   - {snippet}")

    if patterns:
        lines.append("\n일반화 패턴:")
        for pattern in patterns[:3]:
            lines.append(f"- {pattern}")

    st.session_state.home_route_target = "pages/4_Investment_Report.py"
    st.session_state.home_route_label = "투자심사 보고서"
    lines.append("\n더 정밀한 분석은 아래 버튼으로 이동해 진행할 수 있습니다.")
    return "\n".join(lines)


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

    if _looks_like_dart_query(user_text):
        return _handle_dart_query(user_text)

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
            "- \"팀 과업/서류 관리\"\n"
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
    if _looks_like_dart_query(user_input):
        with st.spinner("DART 인수인의견 데이터셋 검색 중..."):
            response = _route_message(user_input)
    else:
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

with st.expander("협업 허브 워크플로우", expanded=False):
    st.markdown("""
### 1. 팀 상태 확인
협업 허브에서 과업/문서/일정을 한 화면에서 확인합니다.

### 2. 과업 관리
담당자, 상태(진행 전/중/완료), 마감일을 지정합니다.

### 3. 필수 서류 체크
Drive 업로드 여부를 체크하고 누락 문서를 정리합니다.

### 4. 메리 협업 브리프
Claude 기반 요약으로 오늘의 집중 포인트를 정리합니다.
    """)

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
