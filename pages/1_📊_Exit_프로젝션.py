"""
Exit 프로젝션 페이지
- 투자검토 엑셀 분석
- PER 기반 시나리오 분석
- Exit 프로젝션 엑셀 생성
"""

import streamlit as st
import asyncio
import re
from pathlib import Path
import pandas as pd
import altair as alt

# 공통 모듈 임포트
from shared.config import initialize_session_state, get_avatar_image, initialize_agent
from shared.auth import check_authentication, get_user_email
from shared.sidebar import render_sidebar

# 페이지 설정
st.set_page_config(
    page_title="Exit 프로젝션 | VC 투자 분석",
    page_icon="📊",
    layout="wide",
)

# 초기화
initialize_session_state()
check_authentication()
initialize_agent()

# 아바타 이미지 로드
avatar_image = get_avatar_image()

# 사이드바 렌더링
render_sidebar()


# ========================================
# 헬퍼 함수 정의 (먼저 정의)
# ========================================
def _get_previous_user_message(idx: int) -> str:
    """이전 사용자 메시지 찾기"""
    for i in range(idx-1, -1, -1):
        if st.session_state.exit_messages[i]["role"] == "user":
            return st.session_state.exit_messages[i]["content"]
    return ""


def _render_feedback_buttons(idx: int, msg: dict):
    """피드백 버튼 렌더링"""
    feedback_cols = st.columns([1, 1, 1, 9])
    feedback_key = f"exit_msg_{idx}"

    with feedback_cols[0]:
        if st.button("👍", key=f"exit_thumbs_up_{idx}", use_container_width=True):
            user_msg = _get_previous_user_message(idx)
            st.session_state.agent.feedback.add_feedback(
                user_message=user_msg,
                assistant_response=msg["content"],
                feedback_type="thumbs_up",
                context={"message_index": idx}
            )
            st.session_state.message_feedback[feedback_key] = "thumbs_up"
            st.rerun()

    with feedback_cols[1]:
        if st.button("👎", key=f"exit_thumbs_down_{idx}", use_container_width=True):
            user_msg = _get_previous_user_message(idx)
            st.session_state.agent.feedback.add_feedback(
                user_message=user_msg,
                assistant_response=msg["content"],
                feedback_type="thumbs_down",
                context={"message_index": idx}
            )
            st.session_state.message_feedback[feedback_key] = "thumbs_down"
            st.rerun()

    with feedback_cols[2]:
        if st.button("💬", key=f"exit_feedback_text_btn_{idx}", use_container_width=True, help="텍스트 피드백 추가"):
            if feedback_key not in st.session_state.feedback_input_visible:
                st.session_state.feedback_input_visible[feedback_key] = True
            else:
                st.session_state.feedback_input_visible[feedback_key] = not st.session_state.feedback_input_visible[feedback_key]
            st.rerun()

    # 텍스트 피드백 입력창
    if st.session_state.feedback_input_visible.get(feedback_key, False):
        text_feedback = st.text_area(
            "자세한 피드백을 입력하세요:",
            key=f"exit_feedback_textarea_{idx}",
            placeholder="예: 응답이 너무 길어요...",
            height=80
        )

        submit_cols = st.columns([1, 1, 8])
        with submit_cols[0]:
            if st.button("제출", key=f"exit_submit_feedback_{idx}", type="primary", use_container_width=True):
                if text_feedback.strip():
                    user_msg = _get_previous_user_message(idx)
                    st.session_state.agent.feedback.add_feedback(
                        user_message=user_msg,
                        assistant_response=msg["content"],
                        feedback_type="text_feedback",
                        feedback_value=text_feedback,
                        context={"message_index": idx}
                    )
                    st.session_state.feedback_text[feedback_key] = text_feedback
                    st.session_state.feedback_input_visible[feedback_key] = False
                    st.success("피드백이 저장되었습니다!")
                    st.rerun()
                else:
                    st.warning("피드백을 입력해주세요")

        with submit_cols[1]:
            if st.button("취소", key=f"exit_cancel_feedback_{idx}", use_container_width=True):
                st.session_state.feedback_input_visible[feedback_key] = False
                st.rerun()

    # 피드백 상태 표시
    if feedback_key in st.session_state.message_feedback:
        feedback_status = st.session_state.message_feedback[feedback_key]
        if feedback_status == "thumbs_up":
            st.caption("피드백: 도움이 되었습니다")
        elif feedback_status == "thumbs_down":
            st.caption("피드백: 개선이 필요합니다")

    if feedback_key in st.session_state.feedback_text:
        st.caption(f"상세 피드백: {st.session_state.feedback_text[feedback_key][:50]}...")


# ========================================
# 메인 영역
# ========================================
st.markdown("# 📊 Exit 프로젝션")
st.markdown("투자검토 엑셀 파일을 분석하고 PER 기반 Exit 프로젝션을 생성합니다")

st.divider()

# 빠른 명령어 버튼
if st.session_state.get("uploaded_file_path"):
    file_name = st.session_state.get("uploaded_file_name", "파일")
    quick_cols = st.columns(3)

    with quick_cols[0]:
        if st.button("📄 파일 분석", use_container_width=True, type="primary"):
            st.session_state.quick_command = f"{file_name} 파일을 분석해줘"

    with quick_cols[1]:
        if st.button("📈 Exit 프로젝션 생성", use_container_width=True, type="primary"):
            st.session_state.quick_command = f"{file_name}을 2030년 PER 10,20,30배로 분석하고 Exit 프로젝션 생성해줘"

    with quick_cols[2]:
        if st.button("🔄 고급 분석", use_container_width=True):
            st.session_state.quick_command = f"{file_name}을 고급 분석해줘 (부분매각, NPV 포함)"

    st.divider()

# 채팅 컨테이너
chat_container = st.container(border=True, height=600)

with chat_container:
    chat_area = st.container(height=520)

    with chat_area:
        # 환영 메시지 (최초 1회만)
        if st.session_state.exit_show_welcome and not st.session_state.exit_user_info_collected:
            with st.chat_message("assistant", avatar=avatar_image):
                st.markdown("""안녕하세요, 메리입니다.

VC 투자 분석을 시작하기 전에 몇 가지 정보를 알려주세요:
- **사내기업가 별명**: 누구신가요?
- **분석 대상 기업**: 어떤 기업을 분석하시나요?

예시: "홍길동, ABC스타트업" 또는 "김철수 / XYZ테크"

이 정보는 세션 ID로 사용되어 나중에 대화를 쉽게 찾을 수 있습니다.""")

            st.session_state.exit_show_welcome = False

        # 메시지 표시
        for idx, msg in enumerate(st.session_state.exit_messages):
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(msg["content"])
            elif msg["role"] == "assistant":
                with st.chat_message("assistant", avatar=avatar_image):
                    st.markdown(msg["content"])

                    # 피드백 버튼
                    _render_feedback_buttons(idx, msg)

            elif msg["role"] == "tool":
                with st.chat_message("assistant", avatar=avatar_image):
                    st.caption(msg["content"])

    # 입력창
    user_input = st.chat_input("메시지를 입력하세요...", key="exit_chat_input")

# ========================================
# 메시지 처리
# ========================================

# 빠른 명령어 처리
if "quick_command" in st.session_state:
    user_input = st.session_state.quick_command
    del st.session_state.quick_command

if user_input:
    user_email = get_user_email()

    # 사용자 정보 수집 (최초 1회)
    if not st.session_state.exit_user_info_collected:
        parsed = re.split(r'[,/]', user_input, maxsplit=1)

        if len(parsed) >= 2:
            nickname = parsed[0].strip()
            company_raw = parsed[1].strip()
            company = re.split(r'\s+(분석|검토|해줘|부탁|요청)', company_raw)[0].strip()

            st.session_state.agent.memory.set_user_info(nickname, company, google_email=user_email)
            st.session_state.exit_user_info_collected = True

            confirmation = f"반갑습니다, **{nickname}**님! **{company}** 투자 분석을 시작하겠습니다.\n\n세션 ID: `{st.session_state.agent.memory.session_id}`"

            st.session_state.exit_messages.append({"role": "user", "content": user_input})
            st.session_state.exit_messages.append({"role": "assistant", "content": confirmation})
            st.rerun()
        else:
            st.session_state.exit_messages.append({"role": "user", "content": user_input})
            st.session_state.exit_messages.append({
                "role": "assistant",
                "content": "정보를 정확히 파악하지 못했습니다. 다음 형식으로 다시 알려주세요:\n\n예시: \"홍길동, ABC스타트업\" 또는 \"김철수 / XYZ테크\""
            })
            st.rerun()
    else:
        # 파일 경로 자동 치환
        if st.session_state.get("uploaded_file_path"):
            file_name = st.session_state.get("uploaded_file_name", "")
            if file_name and file_name in user_input:
                user_input = user_input.replace(file_name, st.session_state.uploaded_file_path)

        st.session_state.exit_messages.append({"role": "user", "content": user_input})

        # 실시간 스트리밍 표시를 위한 placeholder 생성
        with chat_area:
            with st.chat_message("assistant", avatar=avatar_image):
                response_placeholder = st.empty()
                tool_container = st.container()

        # 에이전트 응답 생성 (실시간 스트리밍) - Exit 모드
        async def stream_exit_response_realtime():
            full_response = ""
            tool_messages = []

            async for chunk in st.session_state.agent.chat(user_input, mode="exit"):
                if "**도구:" in chunk:
                    tool_messages.append(chunk.strip())
                    # 도구 메시지도 실시간 표시
                    with tool_container:
                        st.caption(chunk.strip())
                else:
                    full_response += chunk
                    # 실시간으로 응답 업데이트
                    response_placeholder.markdown(full_response + "▌")

            # 최종 응답 (커서 제거)
            response_placeholder.markdown(full_response)
            return full_response, tool_messages

        assistant_response, tool_messages = asyncio.run(stream_exit_response_realtime())

        for tool_msg in tool_messages:
            st.session_state.exit_messages.append({"role": "tool", "content": tool_msg})

        st.session_state.exit_messages.append({"role": "assistant", "content": assistant_response})
        st.rerun()

# ========================================
# Exit 프로젝션 시각화
# ========================================
if st.session_state.projection_data:
    st.divider()
    st.markdown("## Exit 프로젝션 시각화")

    df = st.session_state.projection_data

    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("PER:O", title="PER 배수"),
            y=alt.Y("IRR:Q", title="IRR (%)"),
            color=alt.Color("PER:N", legend=None),
            tooltip=["PER", "IRR", "Multiple"]
        )
        .properties(height=300)
    )

    st.altair_chart(chart, use_container_width=True)
