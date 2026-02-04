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
    page_icon="M",
    layout="wide",
    initial_sidebar_state="collapsed"  # 사이드바 숨김
)

# 초기화 및 인증
initialize_session_state()
check_authentication()  # 인증되지 않으면 여기서 멈춤

# ========================================
# 포트폴리오 데이터 사전 로드 (백그라운드 캐싱)
# ========================================
from shared.airtable_portfolio import _get_cached_dataframe

# 앱 시작 시 DataFrame 미리 로드 (첫 검색부터 빠르게)
# @st.cache_data로 캐싱되므로 한 번만 실행됨
try:
    with st.spinner("📊 투자 데이터 로딩 중..."):
        df = _get_cached_dataframe()
        portfolio_size = len(df)

        st.session_state["portfolio_preloaded"] = True
        st.session_state["portfolio_size"] = portfolio_size

        # 성공 메시지 (2초 후 사라짐)
        success_container = st.empty()
        success_container.success(f"✅ 투자 데이터 로딩 완료! ({portfolio_size}개 기업)")
        import time
        time.sleep(2)
        success_container.empty()

except Exception as e:
    st.session_state["portfolio_preloaded"] = False
    st.session_state["portfolio_error"] = str(e)
    st.error(f"❌ 데이터 로딩 실패: {str(e)}")

# ========================================
# Claude Code 스타일 CSS
# ========================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

/* 전역 스타일 - 다크 테마 */
:root {
    --bg-primary: #0f0f0f;
    --bg-secondary: #1a1a1a;
    --border-color: #2a2a2a;
    --text-primary: #e4e4e7;
    --text-secondary: #a1a1aa;
    --accent: #3b82f6;
    --accent-hover: #2563eb;
    --tool-bg: #1a1a1a;
    --tool-border: #2a2a2a;
    --success: #10b981;
    --warning: #f59e0b;
}

html, body, [class*="css"] {
    font-family: 'Inter', 'Noto Sans KR', sans-serif;
    color: var(--text-primary);
    background-color: var(--bg-primary) !important;
}

/* 사이드바 완전히 숨김 */
[data-testid="stSidebar"] {
    display: none !important;
}

/* 메인 컨테이너 */
.stApp {
    background-color: var(--bg-primary) !important;
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

/* 하단 고정 파일 영역 */
.fixed-file-area {
    max-width: 900px;
    margin: 0 auto 0.5rem auto;
    padding: 0.5rem 0;
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

/* 게임 로딩 팁 배너 */
.loading-tips-banner {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: linear-gradient(90deg, #1a1a1a 0%, #2a2a2a 50%, #1a1a1a 100%);
    border-top: 1px solid var(--border-color);
    padding: 0.75rem 1rem;
    z-index: 999;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
}

.loading-tips-banner__icon {
    color: var(--success);
    font-size: 1rem;
    animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.loading-tips-banner__text {
    color: var(--text-secondary);
    font-size: 0.8125rem;
    max-width: 800px;
    text-align: center;
    transition: opacity 0.5s ease-in-out;
}

/* 시스템 메시지 (요약) 스타일 */
.system-message {
    background: rgba(59, 130, 246, 0.1);
    border-left: 3px solid var(--accent);
    padding: 0.75rem 1rem;
    border-radius: 0.5rem;
    margin: 1rem 0;
    font-size: 0.875rem;
}
</style>
""", unsafe_allow_html=True)

# ========================================
# 헤더
# ========================================
# 헤더: 3컬럼 레이아웃 (제목, 팀 선택, 새 대화 버튼)
col_left, col_mid, col_right = st.columns([3, 2, 1])

with col_left:
    st.markdown("""
    <div class="claude-header">
        <div class="claude-header__logo">
            <span>Merry</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_mid:
    # 팀 드롭다운
    team_options = [
        "CIC 봄날",
        "CIC 스템",
        "CIC 썬",
        "CIC 모모",
        "LS그룹",
        "CI그룹",
        "대표이사실"
    ]
    current_team = st.session_state.get("current_team", "CIC 봄날")
    selected_team = st.selectbox(
        "팀 선택",
        options=team_options,
        index=team_options.index(current_team) if current_team in team_options else 0,
        key="team_selector",
        label_visibility="collapsed"
    )
    if selected_team != current_team:
        st.session_state.current_team = selected_team
        st.rerun()

with col_right:
    if st.button("새 대화", key="new_chat", help="대화 초기화"):
        st.session_state.unified_messages = []
        st.session_state.unified_files = []
        st.rerun()

# 빠른 페이지 이동 (사이드바 숨김 보완)
st.markdown("### 바로가기")
nav_cols = st.columns(4)
with nav_cols[0]:
    st.page_link("pages/10_Fund_Dashboard.py", label="펀드 대시보드", icon="📊")
with nav_cols[1]:
    st.page_link("pages/0_Collaboration_Hub.py", label="협업 허브", icon="🧭")
with nav_cols[2]:
    st.page_link("pages/8_Startup_Discovery.py", label="스타트업 발굴", icon="🔍")
with nav_cols[3]:
    st.page_link("pages/11_Fund_Company_View.py", label="펀드/기업 상세", icon="🏷️")

# ========================================
# 대화 기록 불러오기
# ========================================
from shared.conversation_history import list_conversations, load_conversation, save_conversation

current_team = st.session_state.get("current_team", "CIC 봄날")

# 대화 ID 초기화
if "current_conversation_id" not in st.session_state:
    st.session_state.current_conversation_id = None

# 대화 기록 expander
with st.expander("📚 대화 기록", expanded=False):
    conversations = list_conversations(current_team, limit=10)

    if conversations:
        st.caption(f"최근 {len(conversations)}개 대화")

        for conv in conversations:
            conv_id = conv["conversation_id"]
            preview = conv["preview"]
            msg_count = conv["message_count"]
            created = conv["created_at"][:16]  # YYYY-MM-DD HH:MM

            col1, col2 = st.columns([4, 1])
            with col1:
                if st.button(
                    f"💬 {preview} ({msg_count}개)",
                    key=f"load_{conv_id}",
                    help=f"생성: {created}",
                    use_container_width=True
                ):
                    # 대화 불러오기
                    messages, metadata = load_conversation(current_team, conv_id)
                    if messages:
                        st.session_state.unified_messages = messages
                        st.session_state.current_conversation_id = conv_id
                        st.toast(f"✅ 대화 불러오기 완료 ({msg_count}개 메시지)")
                        st.rerun()
            with col2:
                st.caption(f"{created[5:]}")  # MM-DD HH:MM
    else:
        st.info("저장된 대화 기록이 없습니다")

st.markdown("---")

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
    all_extensions = set(ALLOWED_EXTENSIONS_PDF) | set(ALLOWED_EXTENSIONS_EXCEL) | {".docx", ".doc"}

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


def compact_conversation(messages: list, api_key: str) -> tuple[list, bool]:
    """
    대화 히스토리를 요약하여 컴팩트

    Args:
        messages: 현재 메시지 리스트
        api_key: Claude API 키

    Returns:
        (컴팩트된 메시지 리스트, 컴팩션 성공 여부)
    """
    COMPACTION_TRIGGER = 15
    COMPACTION_TARGET = 10

    if len(messages) < COMPACTION_TRIGGER:
        return messages, False

    # 요약할 메시지 (첫 10개)
    to_compact = messages[:COMPACTION_TARGET]
    remaining = messages[COMPACTION_TARGET:]

    # 요약 생성
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)

        # 대화 내용을 텍스트로 변환 (system 메시지는 제외)
        conversation_text = "\n\n".join([
            f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content'][:500]}"  # 긴 응답 잘라내기
            for msg in to_compact
            if msg['role'] != 'system'
        ])

        # Claude에게 요약 요청
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",  # 빠르고 저렴한 모델
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": f"""다음은 VC 투자 분석 대화의 일부입니다.
이 대화를 간결하게 요약해주세요. 핵심 정보만 포함하고, 3-5문장으로 작성해주세요.

{conversation_text}

요약:"""
            }]
        )

        summary = response.content[0].text.strip()

        # 요약을 시스템 메시지로 추가
        compacted = [{
            "role": "system",
            "content": f"[이전 대화 요약]\n{summary}"
        }]

        # 나머지 메시지 추가
        compacted.extend(remaining)

        return compacted, True

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"대화 컴팩션 실패: {e}")
        # 요약 실패 시 기존 방식 (단순 삭제)
        return messages[-COMPACTION_TRIGGER:], False


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
        if st.button("Exit 프로젝션", key="pill_exit", use_container_width=True):
            st.session_state.quick_cmd = "투자검토 엑셀 파일을 분석해서 Exit 프로젝션을 만들어줘"
            st.rerun()

    with col2:
        if st.button("Peer PER 분석", key="pill_peer", use_container_width=True):
            st.session_state.quick_cmd = "유사기업 PER을 비교 분석해줘"
            st.rerun()

    with col3:
        if st.button("기업 진단", key="pill_diagnosis", use_container_width=True):
            st.session_state.quick_cmd = "진단시트를 분석하고 컨설턴트 보고서를 작성해줘"
            st.rerun()

    col4, col5, col6 = st.columns(3)
    with col4:
        if st.button("투자보고서", key="pill_report", use_container_width=True):
            st.session_state.quick_cmd = "PDF에서 시장 근거를 추출하고 투자보고서를 써줘"
            st.rerun()

    with col5:
        if st.button("스타트업 발굴", key="pill_discovery", use_container_width=True):
            st.session_state.quick_cmd = "정책 PDF를 분석해서 유망 산업을 추천해줘"
            st.rerun()

    with col6:
        if st.button("계약서 검토", key="pill_contract", use_container_width=True):
            st.session_state.quick_cmd = "계약서를 분석하고 주요 조항을 검토해줘"
            st.rerun()

    col7, col8 = st.columns(2)
    with col7:
        if st.button("팀 협업", key="pill_collab", use_container_width=True):
            st.session_state.quick_cmd = "팀 과업 현황을 보여줘"
            st.rerun()

    with col8:
        if st.button("공공입찰 검색", key="pill_bid", use_container_width=True):
            st.session_state.quick_cmd = "나라장터에서 관련 입찰 공고를 찾아줘"
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

        elif role == "system":
            # 시스템 메시지 (대화 요약)
            st.markdown(f"""
            <div class="system-message">
                <strong>📝 {content.split(']')[0]}]</strong>
                <div style="margin-top: 0.5rem; color: var(--text-secondary);">
                    {content.split(']', 1)[1] if ']' in content else content}
                </div>
            </div>
            """, unsafe_allow_html=True)

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
                                    {tool_name}
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

# Auto-scroll to bottom
if st.session_state.unified_messages:
    st.markdown("""
    <script>
    window.scrollTo(0, document.body.scrollHeight);
    </script>
    """, unsafe_allow_html=True)

# ========================================
# 하단 고정 영역: 파일 첨부 + 채팅 입력
# ========================================

# 첨부된 파일 표시 (하단 고정)
if st.session_state.unified_files:
    st.markdown('<div class="fixed-file-area">', unsafe_allow_html=True)
    for i, fpath in enumerate(st.session_state.unified_files):
        fname = Path(fpath).name
        col1, col2 = st.columns([5, 1])
        with col1:
            st.markdown(f"""
            <div class="file-chip">
                {fname}
            </div>
            """, unsafe_allow_html=True)
        with col2:
            if st.button("×", key=f"remove_{i}", help="제거"):
                st.session_state.unified_files.pop(i)
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# 파일 첨부 버튼
with st.expander("파일 첨부", expanded=False):
    uploaded_files = st.file_uploader(
        "분석할 파일을 선택하세요 (PDF, 엑셀, DOCX)",
        type=["pdf", "xlsx", "xls", "docx", "doc"],
        accept_multiple_files=True,
        key="unified_file_uploader",
        help="투자검토 엑셀, 기업소개서 PDF, 진단시트, 계약서 등 모든 파일을 지원합니다"
    )

    if uploaded_files:
        for uploaded_file in uploaded_files:
            # PDF 파일인 경우 로딩바 표시
            if uploaded_file.name.lower().endswith('.pdf'):
                import time

                # 로딩바 표시
                progress_bar = st.progress(0)
                status_text = st.empty()

                status_text.text(f"📄 {uploaded_file.name} 업로드 중...")

                # 30초 동안 진행
                for percent in range(101):
                    time.sleep(0.3)  # 30초 = 100 * 0.3
                    progress_bar.progress(percent)
                    if percent < 100:
                        status_text.text(f"📄 {uploaded_file.name} 업로드 중... {percent}%")

                # 파일 저장
                file_path = save_uploaded_file(uploaded_file)

                if file_path and file_path not in st.session_state.unified_files:
                    st.session_state.unified_files.append(file_path)
                    progress_bar.empty()
                    status_text.empty()

                    # 완료 토스트
                    st.toast(f"✅ {uploaded_file.name} 업로드 완료", icon="✅")

                    # 주의 문구 표시
                    st.warning(f"⚠️ **{uploaded_file.name}** 업로드가 완료되었습니다. 이제 파일 분석을 요청하실 수 있습니다.", icon="⚠️")
                    time.sleep(2)  # 2초간 표시
            else:
                # PDF가 아닌 파일은 즉시 업로드
                file_path = save_uploaded_file(uploaded_file)
                if file_path and file_path not in st.session_state.unified_files:
                    st.session_state.unified_files.append(file_path)
                    st.toast(f"{uploaded_file.name} 업로드 완료")

# 채팅 입력
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
            try:
                # 대화 히스토리 컴팩션: 15개 이상 시 요약하여 컨텍스트 유지
                if len(st.session_state.unified_messages) >= 15:
                    # 컴팩션 중 명확한 시각적 피드백
                    with st.status("📝 대화 내용 요약 중...", expanded=True) as status:
                        status.write("💬 15개 이상의 메시지를 압축하고 있습니다.")
                        status.write("⏳ Claude Haiku API로 이전 대화를 요약하는 중입니다...")
                        status.write("🔒 잠시만 기다려주세요. (중복 요청 방지)")

                        api_key = st.session_state.get("user_api_key", "")
                        compacted_messages, success = compact_conversation(
                            st.session_state.unified_messages,
                            api_key
                        )
                        st.session_state.unified_messages = compacted_messages

                        if success:
                            status.update(label="✅ 대화 요약 완료!", state="complete", expanded=False)
                            st.toast("대화가 길어져 이전 내용을 요약했습니다", icon="📝")
                        else:
                            status.update(label="⚠️ 요약 실패 (기존 방식 사용)", state="error", expanded=False)

                # 응답 생성 중 표시
                with st.spinner("🤖 생각 중..."):
                    # 동기 chat 메서드 사용 (returns string)
                    full_response = agent.chat_sync(full_message, mode="unified")
                    tool_logs = []  # chat_sync doesn't return tool logs
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

            # 대화 자동 저장 (백그라운드)
            try:
                current_team = st.session_state.get("current_team", "CIC 봄날")
                current_conv_id = st.session_state.get("current_conversation_id")
                new_conv_id = save_conversation(
                    current_team,
                    st.session_state.unified_messages,
                    conversation_id=current_conv_id
                )
                if not current_conv_id and new_conv_id:
                    # 첫 저장
                    st.session_state.current_conversation_id = new_conv_id
            except Exception as e:
                logger.warning(f"대화 자동 저장 실패: {e}")

    st.rerun()

# ========================================
# 팁 로테이션 배너
# ========================================
st.markdown("""
<div class="loading-tips-banner">
    <span class="loading-tips-banner__icon">💡</span>
    <div class="loading-tips-banner__text"></div>
</div>

<script>
// 팁 목록
const tips = [
    "💡 200개 한 번에 출력해달라고 하지 마세요. 최근 3-4개의 대화를 기억하고 있어서 최대 20만 토큰까지만 응답이 가능합니다.",
    "📁 파일을 먼저 업로드한 후 분석을 요청하면 더 정확한 결과를 얻을 수 있습니다.",
    "🎯 복잡한 요청은 단계별로 나누어 주시면 더 빠르게 처리할 수 있습니다.",
    "🔍 포트폴리오 조회 시 구체적인 키워드를 사용하면 검색 정확도가 높아집니다.",
    "📊 Exit 프로젝션은 투자검토 엑셀 파일이 필요합니다.",
    "🏢 Peer 분석은 기업소개서 PDF를 첨부해주세요.",
    "💬 최근 대화만 기억하므로, 이전 내용을 참조하려면 다시 언급해주세요.",
    "⚡ 대화가 15개 이상 쌓이면 자동으로 이전 내용을 요약합니다.",
    "🎨 '새 대화' 버튼으로 언제든 대화를 초기화할 수 있습니다."
];

let currentTipIndex = 0;

function rotateTips() {
    const tipElement = document.querySelector('.loading-tips-banner__text');
    if (tipElement) {
        // Fade out
        tipElement.style.opacity = '0';

        setTimeout(() => {
            // Change text
            tipElement.textContent = tips[currentTipIndex];
            currentTipIndex = (currentTipIndex + 1) % tips.length;

            // Fade in
            tipElement.style.opacity = '1';
        }, 500);
    }
}

// 페이지 로드 시 즉시 첫 번째 팁 표시
setTimeout(() => {
    const tipElement = document.querySelector('.loading-tips-banner__text');
    if (tipElement) {
        tipElement.textContent = tips[0];
        tipElement.style.opacity = '1';
        currentTipIndex = 1;
    }
}, 100);

// 7초마다 팁 변경
setInterval(rotateTips, 7000);
</script>
""", unsafe_allow_html=True)

# ========================================
# 푸터
# ========================================
st.markdown("""
<div style="text-align: center; color: #9ca3af; font-size: 0.75rem; margin-top: 4rem; padding: 2rem 0; margin-bottom: 3rem;">
    Powered by Claude Opus 4.5 | 메리 VC 에이전트 v2.0
</div>
""", unsafe_allow_html=True)
