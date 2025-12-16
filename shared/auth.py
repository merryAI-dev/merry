"""
인증 로직 모듈
- Claude API Key 기반 인증
- API 키가 유효하면 사용 가능
- 동일 API 키 사용자끼리 세션/피드백 공유
"""

import streamlit as st
import hashlib
from anthropic import Anthropic


def get_user_id_from_api_key(api_key: str) -> str:
    """
    API 키에서 고유 사용자 ID 생성 (해시)
    동일한 API 키는 동일한 user_id를 가짐
    """
    if not api_key:
        return "anonymous"
    # API 키의 SHA256 해시 앞 12자리를 user_id로 사용
    return hashlib.sha256(api_key.encode()).hexdigest()[:12]


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
    st.markdown("## MYSC VC 투자 분석 에이전트")
    st.markdown("Claude API 키를 입력하여 사용하세요.")
    st.markdown("---")

    # API 키 입력
    api_key = st.text_input(
        "Claude API Key",
        type="password",
        placeholder="sk-ant-api03-...",
        help="Anthropic Console에서 발급받은 API 키를 입력하세요"
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        login_clicked = st.button("시작하기", type="primary", use_container_width=True)

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
                    st.session_state.user_id = get_user_id_from_api_key(api_key)
                    st.success("인증 성공!")
                    st.rerun()
                else:
                    st.error("유효하지 않은 API 키입니다.")

    st.markdown("---")
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
