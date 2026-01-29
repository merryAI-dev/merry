"""
VC 투자 분석 에이전트 - Claude Code 스타일

실행: streamlit run app.py
"""

import asyncio
from pathlib import Path
from typing import Optional
import streamlit as st

from shared.config import (
    get_avatar_image,
    get_user_avatar_image,
    initialize_session_state,
    initialize_agent,
)
from shared.auth import check_authentication
from shared.file_utils import (
    ALLOWED_EXTENSIONS_PDF,
    ALLOWED_EXTENSIONS_EXCEL,
    cleanup_user_temp_files,
    get_secure_upload_path,
    validate_upload,
)
from shared.logging_config import setup_logging

# 로깅 초기화
setup_logging()

# 페이지 설정
st.set_page_config(
    page_title="메리 | VC 에이전트",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"  # 사이드바 숨김
)

# 초기화 및 인증
initialize_session_state()
check_authentication()  # 인증되지 않으면 여기서 멈춤

# ========================================
# Claude Code 스타일 CSS
# ========================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

/* 전역 스타일 */
:root {
    --bg-primary: #ffffff;
    --bg-secondary: #f9fafb;
    --border-color: #e5e7eb;
    --text-primary: #111827;
    --text-secondary: #6b7280;
    --accent: #2563eb;
    --accent-hover: #1d4ed8;
    --tool-bg: #f3f4f6;
    --tool-border: #d1d5db;
    --success: #10b981;
    --warning: #f59e0b;
}

html, body, [class*="css"] {
    font-family: 'Inter', 'Noto Sans KR', sans-serif;
    color: var(--text-primary);
}

/* 사이드바 완전히 숨김 */
[data-testid="stSidebar"] {
    display: none !important;
}

/* 메인 컨테이너 */
.stApp {
    background-color: var(--bg-primary);
}

.main .block-container {
    max-width: 900px;
    padding-top: 2rem;
    padding-bottom: 6rem;
}

/* 헤더 */
.claude-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 0;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 2rem;
}

.claude-header__logo {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-primary);
}

.claude-header__badge {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    background: var(--bg-secondary);
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text-secondary);
    border: 1px solid var(--border-color);
}

/* Welcome 화면 */
.welcome-screen {
    text-align: center;
    padding: 4rem 2rem;
    max-width: 600px;
    margin: 0 auto;
}

.welcome-screen__title {
    font-size: 1.875rem;
    font-weight: 600;
    margin-bottom: 0.75rem;
}

.welcome-screen__subtitle {
    font-size: 1rem;
    color: var(--text-secondary);
    margin-bottom: 3rem;
}

.capability-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    justify-content: center;
    margin-bottom: 2rem;
}

/* Tool Use 카드 (Claude Code 스타일) */
.tool-card {
    margin: 1rem 0;
    border: 1px solid var(--tool-border);
    border-radius: 0.5rem;
    background: var(--tool-bg);
    overflow: hidden;
}

.tool-card__header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    background: var(--bg-primary);
    border-bottom: 1px solid var(--tool-border);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.875rem;
    font-weight: 500;
}

.tool-card__body {
    padding: 1rem;
    font-size: 0.875rem;
    line-height: 1.5;
}

.tool-card--running {
    border-color: var(--accent);
}

.tool-card--success {
    border-color: var(--success);
}

.tool-card--error {
    border-color: var(--warning);
}

/* 스피너 (실행 중) */
.tool-spinner {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 2px solid var(--tool-border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* 파일 칩 */
.file-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.375rem 0.75rem;
    border-radius: 0.375rem;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    font-size: 0.875rem;
    margin: 0.25rem;
}

/* Streamlit 기본 버튼 스타일 */
div[data-testid="stButton"] button {
    background: var(--bg-secondary) !important;
    border: 1px solid var(--border-color) !important;
    color: var(--text-primary) !important;
    border-radius: 0.5rem !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    padding: 0.5rem 1rem !important;
}

div[data-testid="stButton"] button:hover {
    background: var(--bg-primary) !important;
    border-color: var(--accent) !important;
    color: var(--accent) !important;
}
</style>
""", unsafe_allow_html=True)

# ========================================
# 헤더
# ========================================
st.markdown("""
<div class="claude-header">
    <div class="claude-header__logo">
        <span>🤖</span>
        <span>메리 VC 에이전트</span>
        <span class="claude-header__badge">
            <span style="width: 6px; height: 6px; background: #10b981; border-radius: 50%; display: inline-block;"></span>
            Claude Opus 4.5
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

# ========================================
# 에이전트 초기화
# ========================================
initialize_agent()

avatar_image = get_avatar_image()
user_avatar_image = get_user_avatar_image()

# 세션 상태 초기화
if "unified_messages" not in st.session_state:
    st.session_state.unified_messages = []
if "unified_files" not in st.session_state:
    st.session_state.unified_files = []


def save_uploaded_file(uploaded_file) -> str:
    """업로드된 파일을 temp 디렉토리에 저장"""
    user_id = st.session_state.get("user_id", "anonymous")
    all_extensions = ALLOWED_EXTENSIONS_PDF | ALLOWED_EXTENSIONS_EXCEL | {".docx", ".doc"}

    is_valid, error = validate_upload(
        filename=uploaded_file.name,
        file_size=uploaded_file.size,
        allowed_extensions=all_extensions,
    )
    if not is_valid:
        st.error(error)
        return None

    file_path = get_secure_upload_path(user_id=user_id, original_filename=uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    cleanup_user_temp_files(user_id, max_files=10)
    return str(file_path)


# ========================================
# Welcome 화면 (메시지가 없을 때만 표시)
# ========================================
if not st.session_state.unified_messages:
    st.markdown("""
    <div class="welcome-screen">
        <div class="welcome-screen__title">무엇을 도와드릴까요?</div>
        <div class="welcome-screen__subtitle">
            투자 분석, 기업 진단, 계약서 검토 등 다양한 기능을 자연스러운 대화로 이용하세요
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 기능 Pills
    st.markdown("### 주요 기능")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📊 Exit 프로젝션", key="pill_exit", use_container_width=True):
            st.session_state.quick_cmd = "투자검토 엑셀 파일을 분석해서 Exit 프로젝션을 만들어줘"
            st.rerun()

    with col2:
        if st.button("🏢 Peer PER 분석", key="pill_peer", use_container_width=True):
            st.session_state.quick_cmd = "유사기업 PER을 비교 분석해줘"
            st.rerun()

    with col3:
        if st.button("📋 기업 진단", key="pill_diagnosis", use_container_width=True):
            st.session_state.quick_cmd = "진단시트를 분석하고 컨설턴트 보고서를 작성해줘"
            st.rerun()

    col4, col5, col6 = st.columns(3)
    with col4:
        if st.button("📄 투자보고서", key="pill_report", use_container_width=True):
            st.session_state.quick_cmd = "PDF에서 시장 근거를 추출하고 투자보고서를 써줘"
            st.rerun()

    with col5:
        if st.button("🚀 스타트업 발굴", key="pill_discovery", use_container_width=True):
            st.session_state.quick_cmd = "정책 PDF를 분석해서 유망 산업을 추천해줘"
            st.rerun()

    with col6:
        if st.button("📝 계약서 검토", key="pill_contract", use_container_width=True):
            st.session_state.quick_cmd = "계약서를 분석하고 주요 조항을 검토해줘"
            st.rerun()

    col7, col8 = st.columns(2)
    with col7:
        if st.button("🤝 팀 협업", key="pill_collab", use_container_width=True):
            st.session_state.quick_cmd = "팀 과업 현황을 보여줘"
            st.rerun()

    with col8:
        if st.button("🔍 공공입찰 검색", key="pill_bid", use_container_width=True):
            st.session_state.quick_cmd = "나라장터에서 관련 입찰 공고를 찾아줘"
            st.rerun()

# ========================================
# 파일 업로드 (Expander)
# ========================================
with st.expander("📎 파일 첨부", expanded=False):
    uploaded_files = st.file_uploader(
        "분석할 파일을 선택하세요 (PDF, 엑셀, DOCX)",
        type=["pdf", "xlsx", "xls", "docx", "doc"],
        accept_multiple_files=True,
        key="unified_file_uploader",
        help="투자검토 엑셀, 기업소개서 PDF, 진단시트, 계약서 등 모든 파일을 지원합니다"
    )

    if uploaded_files:
        for uploaded_file in uploaded_files:
            file_path = save_uploaded_file(uploaded_file)
            if file_path and file_path not in st.session_state.unified_files:
                st.session_state.unified_files.append(file_path)
                st.toast(f"✅ {uploaded_file.name} 업로드 완료", icon="📎")

# 첨부된 파일 표시
if st.session_state.unified_files:
    st.markdown("**업로드된 파일**")
    for i, fpath in enumerate(st.session_state.unified_files):
        fname = Path(fpath).name
        ext = Path(fpath).suffix.lower()
        icon = "📊" if ext in [".xlsx", ".xls"] else "📄" if ext == ".pdf" else "📝"

        col1, col2 = st.columns([5, 1])
        with col1:
            st.markdown(f"""
            <div class="file-chip">
                {icon} {fname}
            </div>
            """, unsafe_allow_html=True)
        with col2:
            if st.button("×", key=f"remove_{i}", help="제거"):
                st.session_state.unified_files.pop(i)
                st.rerun()

# ========================================
# 대화 영역
# ========================================
chat_container = st.container()

with chat_container:
    for msg in st.session_state.unified_messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        tool_logs = msg.get("tool_logs", [])

        if role == "user":
            with st.chat_message("user", avatar=user_avatar_image):
                st.markdown(content)

        elif role == "assistant":
            with st.chat_message("assistant", avatar=avatar_image):
                # Tool logs 표시
                if tool_logs:
                    for log in tool_logs:
                        if log.startswith("**도구:"):
                            # Tool execution 카드
                            tool_name = log.replace("**도구:", "").replace("**", "").strip()
                            st.markdown(f"""
                            <div class="tool-card tool-card--running">
                                <div class="tool-card__header">
                                    🔧 {tool_name}
                                    <div class="tool-spinner"></div>
                                </div>
                                <div class="tool-card__body">
                                    실행 중...
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                st.markdown(content)

                # Tool logs expander
                if tool_logs:
                    with st.expander("실행 로그", expanded=False):
                        for line in tool_logs:
                            st.caption(line)

# ========================================
# 채팅 입력
# ========================================
user_input = st.chat_input("메시지를 입력하세요...", key="unified_chat_input")

# 빠른 명령어 처리
if "quick_cmd" in st.session_state:
    user_input = st.session_state.quick_cmd
    del st.session_state.quick_cmd

# 메시지 처리
if user_input:
    # 파일 컨텍스트 추가
    context_info = ""
    if st.session_state.unified_files:
        paths_str = ", ".join(st.session_state.unified_files)
        if "파일" not in user_input and "분석" not in user_input:
            context_info = f"\n[업로드된 파일: {paths_str}]"

    full_message = user_input + context_info
    st.session_state.unified_messages.append({"role": "user", "content": user_input})

    with chat_container:
        with st.chat_message("assistant", avatar=avatar_image):
            response_placeholder = st.empty()

            # VCAgent 동기 호출 (간단 버전)
            agent = st.session_state.agent

            # 간단한 응답 생성
            with st.spinner("생각 중..."):
                try:
                    # 동기 chat 메서드 사용
                    response = agent.chat_sync(full_message, mode="unified")
                    full_response = response.get("content", "응답을 생성할 수 없습니다.")
                    tool_logs = response.get("tool_logs", [])
                except Exception as e:
                    full_response = f"오류가 발생했습니다: {str(e)}"
                    tool_logs = []

            response_placeholder.markdown(full_response)

            # 응답 저장
            st.session_state.unified_messages.append({
                "role": "assistant",
                "content": full_response,
                "tool_logs": tool_logs
            })

    st.rerun()

# ========================================
# 푸터
# ========================================
st.markdown("""
<div style="text-align: center; color: #9ca3af; font-size: 0.75rem; margin-top: 4rem; padding: 2rem 0;">
    Powered by Claude Opus 4.5 | 메리 VC 에이전트 v2.0
</div>
""", unsafe_allow_html=True)
