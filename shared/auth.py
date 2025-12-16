"""
인증 로직 모듈
- Streamlit Cloud SSO 지원
- @mysc.co.kr 도메인 검증
"""

import streamlit as st

ALLOWED_DOMAIN = "mysc.co.kr"


def verify_email_domain(email: str) -> bool:
    """@mysc.co.kr 도메인 검증"""
    if not email:
        return False
    domain = email.split("@")[-1].lower()
    return domain == ALLOWED_DOMAIN


def check_authentication() -> bool:
    """
    인증 확인 - 각 페이지 시작 시 호출

    Returns:
        True if authenticated, otherwise st.stop() is called
    """
    user_email = None

    # 방법 1: Streamlit Cloud SSO (experimental_user)
    try:
        if hasattr(st, 'experimental_user'):
            email = st.experimental_user.email
            if email:
                user_email = email
    except (AttributeError, KeyError):
        pass

    # 방법 2: 로컬 개발 환경에서만 test_email 사용 (배포 환경에서는 비활성화)
    # 보안 주의: test_email은 로컬 테스트용으로만 사용해야 함
    # Streamlit Cloud에서는 반드시 SSO를 통해 인증받아야 함
    # if not user_email:
    #     try:
    #         if 'test_email' in st.secrets:
    #             user_email = st.secrets['test_email']
    #     except Exception:
    #         pass

    # 인증되지 않은 경우
    if not user_email:
        st.warning("이 앱은 MYSC 임직원 전용입니다.")
        st.markdown("""
### Streamlit Cloud 인증 설정 필요

이 앱은 **Streamlit Cloud SSO**를 통해 Google 인증을 사용합니다.

**설정 방법:**
1. Streamlit Cloud → App Settings → Sharing
2. "Who can view this app" → **Only specific people**
3. Viewer emails에 `@mysc.co.kr` 도메인 사용자 추가
4. 또는 Secrets에 `test_email = "your@mysc.co.kr"` 추가하여 테스트
        """)
        st.stop()

    # 도메인 검증
    if not verify_email_domain(user_email):
        st.error(f"접근이 거부되었습니다.")
        st.markdown(f"현재 로그인: **{user_email}**")
        st.markdown("@mysc.co.kr 도메인만 접근이 허용됩니다.")
        st.stop()

    # 세션에 이메일 저장
    st.session_state.user_email = user_email
    return True


def get_user_email() -> str:
    """현재 로그인한 사용자 이메일 반환"""
    return st.session_state.get("user_email", "Unknown")
