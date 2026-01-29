"""
인증 로직 모듈
- Claude API Key 기반 인증
- API 키가 유효하면 사용 가능
- 동일 API 키 사용자끼리 세션/피드백 공유
"""

import streamlit as st
import hashlib
from pathlib import Path
from anthropic import Anthropic


TEAM_OPTIONS = {
    "CIC 봄날": "team_1",
    "CIC 스템": "team_2",
    "CIC 썬": "team_3",
    "CIC 모모": "team_4",
    "LS그룹": "team_5",
    "CI그룹": "team_6",
    "대표이사실": "team_7",
}


def get_user_id_from_api_key(api_key: str) -> str:
    """
    API 키에서 고유 사용자 ID 생성 (해시)
    동일한 API 키는 동일한 user_id를 가짐
    """
    if not api_key:
        return "anonymous"
    # API 키의 SHA256 해시 앞 12자리를 user_id로 사용
    return hashlib.sha256(api_key.encode()).hexdigest()[:12]


def _get_team_sessions(team_id: str) -> list[dict]:
    if not team_id:
        return []

    try:
        from agent.supabase_storage import SupabaseStorage
        storage = SupabaseStorage(user_id=team_id)
        if storage.available:
            return storage.get_recent_sessions(limit=10)
    except Exception:
        pass

    # 로컬 fallback (chat_history/<team_id>/session_*.json)
    storage_dir = Path("chat_history") / team_id
    if not storage_dir.exists():
        return []

    sessions = []
    for path in sorted(storage_dir.glob("session_*.json"), reverse=True)[:10]:
        session_id = path.stem.replace("session_", "")
        try:
            sessions.append({
                "session_id": session_id,
                "message_count": 0,
                "created_at": path.stat().st_mtime,
            })
        except OSError:
            continue
    return sessions


def validate_api_key(api_key: str) -> bool:
    """
    Claude API 키 유효성 검증
    간단한 API 호출로 키가 유효한지 확인
    """
    if not api_key or len(api_key) < 10:
        return False

    try:
        client = Anthropic(api_key=api_key)
        # 최소 비용으로 키 검증 (짧은 메시지)
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        return True
    except Exception as e:
        return False


def check_authentication() -> bool:
    """
    API 키 기반 인증 확인

    Returns:
        True if authenticated, otherwise st.stop() is called
    """
    # 이미 인증된 경우
    if st.session_state.get("api_key_validated"):
        return True

    # BoltStyle CSS
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

        :root {
            --graph-bg: #0f0f0f;
            --graph-ink: #e4e4e7;
            --graph-muted: #a1a1aa;
            --graph-node-bg: rgba(26, 26, 26, 0.9);
            --graph-node-border: rgba(42, 42, 42, 0.8);
            --graph-accent-teal: #10b981;
            --graph-accent-amber: #f59e0b;
        }

        .stApp {
            background-color: var(--graph-bg) !important;
            background-image:
                radial-gradient(circle at 15% 10%, rgba(26, 26, 26, 0.5), rgba(26, 26, 26, 0) 40%),
                radial-gradient(circle at 85% 20%, rgba(42, 42, 42, 0.3), rgba(42, 42, 42, 0) 35%);
            background-attachment: fixed;
        }

        html, body, [class*="css"] {
            font-family: "Space Grotesk", "Noto Sans KR", sans-serif;
            color: var(--graph-ink);
            background-color: var(--graph-bg) !important;
        }

        .auth-welcome-container {
            text-align: center;
            padding: 32px 24px 16px 24px;
            max-width: 800px;
            margin: 0 auto;
        }

        .auth-header {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            margin-bottom: 12px;
        }

        .auth-header h1 {
            font-size: 32px;
            font-weight: 700;
            margin: 0;
            color: var(--graph-ink);
        }

        .auth-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            border-radius: 999px;
            background: linear-gradient(135deg, rgba(26, 140, 134, 0.15), rgba(208, 138, 46, 0.15));
            font-size: 11px;
            font-weight: 500;
            color: var(--graph-muted);
        }

        .auth-badge::before {
            content: "";
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: var(--graph-accent-teal);
            animation: pulse-dot 2s ease-in-out infinite;
        }

        @keyframes pulse-dot {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.2); }
        }

        .auth-subtitle {
            font-size: 15px;
            color: var(--graph-muted);
            margin-bottom: 24px;
        }

        .auth-capability-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            margin: 24px auto 32px auto;
            max-width: 600px;
        }

        .auth-capability-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
            padding: 16px;
            background: rgba(26, 26, 26, 0.8);
            border-radius: 12px;
            border: 1px solid var(--graph-node-border);
        }

        .auth-capability-item__icon {
            font-size: 24px;
        }

        .auth-capability-item__label {
            font-size: 12px;
            font-weight: 500;
            color: var(--graph-ink);
        }

        .auth-login-card {
            background: var(--graph-node-bg);
            border: 1px solid var(--graph-node-border);
            border-radius: 18px;
            padding: 28px 36px;
            max-width: 520px;
            margin: 0 auto 24px auto;
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.5);
        }

        .auth-section-title {
            font-size: 13px;
            font-weight: 600;
            color: var(--graph-ink);
            margin: 16px 0 8px 0;
        }

        .auth-section-title:first-child {
            margin-top: 0;
        }

        div[data-testid="stTextInput"] input,
        div[data-testid="stSelectbox"] > div {
            border-radius: 10px !important;
            border: 1px solid var(--graph-node-border) !important;
            background: #1a1a1a !important;
            color: var(--graph-ink) !important;
        }

        div[data-testid="stButton"] button[kind="primary"] {
            background: linear-gradient(135deg, #10b981, #059669) !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            padding: 10px 24px !important;
            color: white !important;
        }

        div[data-testid="stButton"] button[kind="primary"]:hover {
            background: linear-gradient(135deg, #059669, #047857) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 헤더
    st.markdown("""
    <div class="auth-welcome-container">
        <div class="auth-header">
            <h1>메리 VC 에이전트</h1>
            <span class="auth-badge">AI 활성</span>
        </div>
        <div class="auth-subtitle">
            투자를 도와드리는 메리입니다. 오늘 어떤 분석을 시작할까요?
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Capability Grid
    st.markdown("""
    <div class="auth-capability-grid">
        <div class="auth-capability-item">
            <span class="auth-capability-item__label">Exit 프로젝션</span>
        </div>
        <div class="auth-capability-item">
            <span class="auth-capability-item__label">Peer 분석</span>
        </div>
        <div class="auth-capability-item">
            <span class="auth-capability-item__label">포트폴리오</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 로그인 카드
    st.markdown('<div class="auth-login-card">', unsafe_allow_html=True)

    st.markdown('<div class="auth-section-title">팀 선택</div>', unsafe_allow_html=True)
    team_options = list(TEAM_OPTIONS.keys())
    stored_team_label = st.session_state.get("team_label")
    team_index = team_options.index(stored_team_label) if stored_team_label in team_options else 0
    team_label = st.selectbox(
        "Team",
        options=team_options,
        index=team_index,
        label_visibility="collapsed"
    )
    team_id = TEAM_OPTIONS.get(team_label)
    st.session_state.team_id = team_id
    st.session_state.team_label = team_label

    st.markdown('<div class="auth-section-title">닉네임</div>', unsafe_allow_html=True)
    member_name = st.text_input(
        "닉네임",
        value=st.session_state.get("member_name", ""),
        placeholder="이름 또는 닉네임",
        label_visibility="collapsed"
    )
    st.session_state.member_name = member_name

    # 최근 팀 세션
    sessions = _get_team_sessions(team_id)
    if sessions:
        st.markdown('<div class="auth-section-title">최근 팀 세션</div>', unsafe_allow_html=True)
        session_options = [
            f"{s['session_id']} ({s.get('message_count', 0)}개 메시지)"
            for s in sessions
        ]
        selected_session = st.selectbox(
            "세션 선택",
            options=["새 세션 시작"] + session_options,
            index=0,
            label_visibility="collapsed"
        )
        if selected_session != "새 세션 시작":
            st.session_state.pending_session_id = selected_session.split(" ")[0]
        else:
            st.session_state.pending_session_id = None
        st.caption("선택한 세션은 로그인 후 자동으로 불러옵니다.")

    st.markdown('<div class="auth-section-title">Claude API Key</div>', unsafe_allow_html=True)
    api_key = st.text_input(
        "Claude API Key",
        type="password",
        placeholder="sk-ant-api03-...",
        help="Anthropic Console에서 발급받은 API 키를 입력하세요",
        label_visibility="collapsed"
    )

    st.markdown("</div>", unsafe_allow_html=True)

    # 버튼
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        login_clicked = st.button("메리와 시작하기", type="primary", use_container_width=True)

    if login_clicked:
        if not api_key:
            st.error("API 키를 입력하세요.")
        elif not api_key.startswith("sk-"):
            st.error("올바른 API 키 형식이 아닙니다. (sk-로 시작)")
        else:
            with st.spinner("API 키 확인 중..."):
                if validate_api_key(api_key):
                    st.session_state.api_key_validated = True
                    st.session_state.user_api_key = api_key
                    st.session_state.member_id = get_user_id_from_api_key(api_key)
                    st.session_state.user_id = st.session_state.get("team_id") or "team_1"
                    st.success("인증 성공!")
                    st.rerun()
                else:
                    st.error("유효하지 않은 API 키입니다.")

    # 하단 안내
    st.markdown("")
    cols = st.columns([1, 3, 1])
    with cols[1]:
        st.caption("**메리의 역할**: Exit 프로젝션, Peer PER 분석, 계약서 검토")
        st.caption("API 키는 세션 동안만 사용됩니다.")
        st.caption("[Anthropic Console](https://console.anthropic.com/)에서 API 키를 발급받을 수 있습니다.")

    st.stop()


def get_user_api_key() -> str:
    """현재 사용자의 API 키 반환"""
    return st.session_state.get("user_api_key", "")


def get_user_id() -> str:
    """현재 사용자의 고유 ID 반환 (API 키 해시)"""
    return st.session_state.get("user_id", "anonymous")


def get_user_email() -> str:
    """현재 로그인한 사용자 이메일 반환 (호환성)"""
    user_id = get_user_id()
    return f"user_{user_id}"
