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
    "Team 1": "team_1",
    "Team 2": "team_2",
    "Team 3": "team_3",
    "Team 4": "team_4",
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

    # 로그인 UI 표시
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

        :root {
            --merry-bg: #fbf4ea;
            --merry-ink: #1f1a14;
            --merry-muted: #6b5f53;
            --merry-accent: #c7422f;
            --merry-card: rgba(255, 255, 255, 0.86);
        }

        .merry-login {
            padding: 24px 28px;
            border-radius: 22px;
            background: var(--merry-card);
            border: 1px solid rgba(31, 26, 20, 0.08);
            box-shadow: 0 24px 50px rgba(25, 18, 9, 0.08);
        }

        .merry-kicker {
            font-family: "IBM Plex Mono", monospace;
            font-size: 11px;
            letter-spacing: 0.2em;
            text-transform: uppercase;
            color: var(--merry-muted);
        }

        .merry-title {
            font-family: "Space Grotesk", "Noto Sans KR", sans-serif;
            font-size: 28px;
            font-weight: 700;
            margin: 6px 0 8px 0;
            color: var(--merry-ink);
        }

        .merry-subtitle {
            font-family: "Space Grotesk", "Noto Sans KR", sans-serif;
            font-size: 15px;
            color: var(--merry-muted);
            margin-bottom: 12px;
        }

        .merry-note {
            font-size: 12px;
            color: var(--merry-muted);
            margin-top: 8px;
        }

        div[data-testid="stTextInput"] input {
            border-radius: 12px !important;
            border: 1px solid rgba(31, 26, 20, 0.16) !important;
            background: #fffaf3 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns([1.2, 1])
    with cols[0]:
        st.markdown(
            """
            <div class="merry-login">
                <div class="merry-kicker">Merry VC Agent</div>
                <div class="merry-title">안녕하세요 사내기업가님.</div>
                <div class="merry-subtitle">
                    투자를 도와드리는 메리입니다. 오늘 어떤 분석을 시작할까요?
                    아래에서 모듈을 고르거나 안내데스크에 요청해 주세요.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.markdown("#### 팀 선택")
        team_options = list(TEAM_OPTIONS.keys())
        stored_team_label = st.session_state.get("team_label")
        team_index = team_options.index(stored_team_label) if stored_team_label in team_options else 0
        team_label = st.selectbox(
            "Team",
            options=team_options,
            index=team_index,
        )
        team_id = TEAM_OPTIONS.get(team_label)
        st.session_state.team_id = team_id
        st.session_state.team_label = team_label

        member_name = st.text_input(
            "닉네임",
            value=st.session_state.get("member_name", ""),
            placeholder="이름 또는 닉네임",
        )
        st.session_state.member_name = member_name

        st.markdown("#### 최근 팀 세션")
        sessions = _get_team_sessions(team_id)
        if sessions:
            session_options = [
                f"{s['session_id']} ({s.get('message_count', 0)}개 메시지)"
                for s in sessions
            ]
            selected_session = st.selectbox(
                "세션 선택",
                options=["새 세션 시작"] + session_options,
                index=0,
            )
            if selected_session != "새 세션 시작":
                st.session_state.pending_session_id = selected_session.split(" ")[0]
            else:
                st.session_state.pending_session_id = None
            st.caption("선택한 세션은 로그인 후 자동으로 불러옵니다.")
        else:
            st.caption("팀 세션이 없습니다. 새 세션으로 시작합니다.")

        st.markdown("#### 메리의 역할")
        st.markdown(
            """
            - Exit 프로젝션, IRR, 멀티플 계산 지원
            - Peer PER 및 시장 근거 정리
            - 계약서 핵심 조항/일치성 검토
            """
        )
        st.markdown("#### 시작 준비")
        st.caption("Claude API 키를 입력하면 메리가 바로 준비됩니다.")

    # API 키 입력
    api_key = st.text_input(
        "Claude API Key",
        type="password",
        placeholder="sk-ant-api03-...",
        help="Anthropic Console에서 발급받은 API 키를 입력하세요"
    )

    col1, col2 = st.columns([1, 3])
    with col1:
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

    st.markdown("---")
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
