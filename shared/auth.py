"""
인증 로직 모듈
- Streamlit 1.42+ st.login/st.logout 기반 Google OAuth
- @mysc.co.kr 도메인 검증 + allowed_emails 허용
"""

import streamlit as st
import traceback

ALLOWED_DOMAIN = "mysc.co.kr"

# 디버그 모드
DEBUG_AUTH = True


def verify_email_domain(email: str) -> bool:
    """
    이메일 검증: @mysc.co.kr 도메인 또는 allowed_emails 목록
    """
    if not email:
        return False

    # 1. allowed_emails에 있으면 허용
    try:
        allowed_emails = st.secrets.get("allowed_emails", [])
        if email.lower() in [e.lower() for e in allowed_emails]:
            return True
    except Exception:
        pass

    # 2. @mysc.co.kr 도메인이면 허용
    domain = email.split("@")[-1].lower()
    return domain == ALLOWED_DOMAIN


def check_authentication() -> bool:
    """
    인증 확인 - 각 페이지 시작 시 호출
    Streamlit 1.42+ 새로운 인증 API (st.login/st.logout) 사용

    Returns:
        True if authenticated, otherwise st.stop() is called
    """
    # 디버그 정보 표시
    if DEBUG_AUTH:
        with st.expander("🔧 Debug Info", expanded=False):
            st.write(f"Streamlit version: {st.__version__}")
            st.write(f"hasattr(st, 'user'): {hasattr(st, 'user')}")
            st.write(f"hasattr(st, 'login'): {hasattr(st, 'login')}")
            st.write(f"hasattr(st, 'logout'): {hasattr(st, 'logout')}")

            if hasattr(st, 'user'):
                st.write(f"st.user type: {type(st.user)}")
                st.write(f"st.user: {st.user}")
                try:
                    st.write(f"st.user.is_logged_in: {st.user.is_logged_in}")
                except Exception as e:
                    st.write(f"st.user.is_logged_in error: {e}")

            # secrets 확인
            try:
                auth_config = st.secrets.get("auth", {})
                st.write(f"auth config keys: {list(auth_config.keys()) if auth_config else 'None'}")
            except Exception as e:
                st.write(f"secrets error: {e}")

    # 새로운 st.user API 사용 (Streamlit 1.42+)
    if hasattr(st, 'user') and hasattr(st.user, 'is_logged_in'):
        # 로그인되지 않은 경우
        if not st.user.is_logged_in:
            # 로그인 버튼 클릭 상태 확인
            if st.session_state.get("trigger_login", False):
                st.session_state.trigger_login = False

                # 디버깅: st.login 호출 전 상태 표시
                st.info("🔄 st.login() 호출 중...")

                # st.login 함수 시그니처 확인
                import inspect
                try:
                    sig = inspect.signature(st.login)
                    st.write(f"st.login signature: {sig}")
                    st.write(f"st.login parameters: {list(sig.parameters.keys())}")
                except Exception as e:
                    st.write(f"signature error: {e}")

                # auth secrets 상세 확인
                try:
                    auth = st.secrets.get("auth", {})
                    st.write("Auth config:")
                    for key in auth.keys():
                        if key == "client_secret" or key == "cookie_secret":
                            st.write(f"  {key}: ***hidden***")
                        else:
                            st.write(f"  {key}: {auth[key]}")
                except Exception as e:
                    st.write(f"Auth config error: {e}")

                # st.login 호출
                try:
                    result = st.login()
                    st.write(f"st.login() returned: {result}")
                except TypeError as e:
                    st.error(f"TypeError: {e}")
                    st.code(traceback.format_exc())
                    # provider 인자가 필요할 수 있음
                    st.info("Trying st.login('google')...")
                    try:
                        result = st.login("google")
                        st.write(f"st.login('google') returned: {result}")
                    except Exception as e2:
                        st.error(f"st.login('google') error: {e2}")
                        st.code(traceback.format_exc())
                except Exception as e:
                    st.error(f"로그인 에러: {type(e).__name__}: {e}")
                    st.code(traceback.format_exc())

            st.markdown("## 🔐 MYSC VC 투자 분석 에이전트")
            st.markdown("이 앱은 MYSC 임직원 전용입니다.")
            st.markdown("---")

            # 버튼 클릭 시 세션 상태 설정 후 rerun
            if st.button("🔑 Google 계정으로 로그인", type="primary", use_container_width=True):
                st.session_state.trigger_login = True
                st.rerun()

            st.caption("@mysc.co.kr 또는 승인된 이메일만 접근 가능합니다.")
            st.stop()

        # 로그인된 경우: 이메일 확인
        user_email = None
        try:
            user_email = st.user.email
        except (AttributeError, KeyError):
            try:
                user_email = st.user.get("email")
            except Exception:
                pass

        if not user_email:
            st.error("이메일 정보를 가져올 수 없습니다.")
            if st.button("다시 로그인"):
                st.logout()
            st.stop()

        # 도메인/허용목록 검증
        if not verify_email_domain(user_email):
            st.error("접근이 거부되었습니다.")
            st.markdown(f"현재 로그인: **{user_email}**")
            st.markdown("@mysc.co.kr 도메인 또는 승인된 이메일만 접근이 허용됩니다.")
            if st.button("다른 계정으로 로그인"):
                st.logout()
            st.stop()

        # 인증 성공
        st.session_state.user_email = user_email
        return True

    # Fallback: 이전 experimental_user API (Streamlit < 1.42)
    user_email = None
    try:
        if hasattr(st, 'experimental_user'):
            exp_user = st.experimental_user
            if exp_user is not None:
                if hasattr(exp_user, 'email'):
                    user_email = exp_user.email
                elif isinstance(exp_user, dict) and 'email' in exp_user:
                    user_email = exp_user['email']
    except (AttributeError, KeyError, TypeError):
        pass

    # 인증되지 않은 경우
    if not user_email:
        st.warning("이 앱은 MYSC 임직원 전용입니다.")
        st.markdown("""
### 인증 설정 필요

이 앱은 Google OAuth 인증이 필요합니다.

**Secrets.toml 설정이 필요합니다:**
```toml
[auth]
redirect_uri = "https://your-app.streamlit.app/oauth2callback"
cookie_secret = "랜덤_시크릿_문자열"
client_id = "구글_클라이언트_ID"
client_secret = "구글_클라이언트_시크릿"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```
        """)
        st.stop()

    # 도메인 검증
    if not verify_email_domain(user_email):
        st.error("접근이 거부되었습니다.")
        st.markdown(f"현재 로그인: **{user_email}**")
        st.markdown("@mysc.co.kr 도메인만 접근이 허용됩니다.")
        st.stop()

    # 세션에 이메일 저장
    st.session_state.user_email = user_email
    return True


def get_user_email() -> str:
    """현재 로그인한 사용자 이메일 반환"""
    return st.session_state.get("user_email", "Unknown")
