"""
투자심사 보고서 작성 페이지
- 기업 자료에서 시장규모 근거 추출
- 인수인의견 스타일 초안 작성
"""

import asyncio

import streamlit as st

from shared.auth import check_authentication
from shared.config import (
    get_avatar_image,
    initialize_agent,
    initialize_session_state,
    inject_custom_css,
)
from shared.file_utils import (
    ALLOWED_EXTENSIONS_EXCEL,
    ALLOWED_EXTENSIONS_PDF,
    cleanup_user_temp_files,
    get_secure_upload_path,
    validate_upload,
)
from shared.sidebar import render_sidebar


st.set_page_config(
    page_title="투자심사 보고서 | VC 투자 분석",
    page_icon="VC",
    layout="wide",
)

initialize_session_state()
check_authentication()
initialize_agent()
inject_custom_css()

avatar_image = get_avatar_image()
render_sidebar(mode="report")

st.markdown("# 투자심사 보고서 작성")
st.markdown("시장규모 근거를 추출하고 인수인의견 스타일 초안을 작성합니다")
st.divider()

# 업로드 영역
st.markdown("### 기업 자료 업로드")
upload_cols = st.columns([2, 1])

with upload_cols[0]:
    report_file = st.file_uploader(
        "기업 자료 (PDF/엑셀)",
        type=["pdf", "xlsx", "xls"],
        key="report_file_uploader",
        help="시장규모 근거가 포함된 기업 자료를 업로드하세요",
    )

with upload_cols[1]:
    if report_file:
        allowed = ALLOWED_EXTENSIONS_EXCEL + ALLOWED_EXTENSIONS_PDF
        is_valid, error = validate_upload(
            filename=report_file.name,
            file_size=report_file.size,
            allowed_extensions=allowed,
        )
        if not is_valid:
            st.error(error)
        else:
            user_id = st.session_state.get("user_id", "anonymous")
            secure_path = get_secure_upload_path(user_id=user_id, original_filename=report_file.name)
            with open(secure_path, "wb") as f:
                f.write(report_file.getbuffer())

            cleanup_user_temp_files(user_id, max_files=10)
            st.session_state.report_file_path = str(secure_path)
            st.session_state.report_file_name = report_file.name
            st.success(f"업로드 완료: {report_file.name}")

st.divider()

# 빠른 명령어
if st.session_state.get("report_file_path"):
    file_name = st.session_state.get("report_file_name", "파일")
    quick_cols = st.columns(3)

    with quick_cols[0]:
        if st.button("시장규모 근거 추출", use_container_width=True, type="primary", key="report_quick_market"):
            st.session_state.report_quick_command = f"{file_name} 파일을 분석하고 시장규모 근거를 정리해줘"

    with quick_cols[1]:
        if st.button("인수인의견 초안", use_container_width=True, type="primary", key="report_quick_draft"):
            st.session_state.report_quick_command = (
                f"{file_name} 파일을 분석하고 인수인의견 스타일로 초안을 작성해줘. "
                "시장규모 근거와 확인 필요 항목도 포함해줘."
            )

    with quick_cols[2]:
        if st.button("시장규모 + 초안", use_container_width=True, key="report_quick_full"):
            st.session_state.report_quick_command = (
                f"{file_name} 파일을 분석하고 시장규모 근거를 추출한 뒤 "
                "인수인의견 스타일로 보고서 초안을 작성해줘."
            )

    st.divider()

# 채팅 컨테이너
chat_container = st.container(border=True, height=550)

with chat_container:
    chat_area = st.container(height=470)

    with chat_area:
        if not st.session_state.report_messages:
            with st.chat_message("assistant", avatar=avatar_image):
                st.markdown("""**투자심사 보고서 작성 모드**입니다.

기업 자료에서 **시장규모 근거**를 추출하고, 인수인의견 스타일의 초안을 작성합니다.

---
### 시작하기
1. 상단에 **기업 자료(PDF/엑셀)**를 업로드하세요
2. 아래 입력창에 **"시장규모 근거 정리해줘"**라고 입력하세요
---
출력은 근거 → 패턴 → 초안 → 확인 필요 순서로 정리됩니다.
""")

        for idx, msg in enumerate(st.session_state.report_messages):
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user":
                with st.chat_message("user"):
                    st.markdown(content)
            elif role == "assistant":
                with st.chat_message("assistant", avatar=avatar_image):
                    st.markdown(content)

                    tool_logs = msg.get("tool_logs") or []
                    if tool_logs:
                        with st.expander("실행 로그", expanded=False):
                            for line in tool_logs:
                                st.caption(line)

    user_input = st.chat_input("보고서 작성 관련 질문...", key="report_chat_input")


if st.session_state.get("report_quick_command"):
    user_input = st.session_state.report_quick_command
    st.session_state.report_quick_command = None


if user_input:
    if st.session_state.get("report_file_path"):
        file_path = st.session_state.report_file_path
        if file_path not in user_input:
            lowered = user_input.lower()
            if any(keyword in lowered for keyword in ["분석", "시장", "보고서", "초안", "근거"]):
                user_input = f"{file_path} 파일을 " + user_input

    st.session_state.report_messages.append({"role": "user", "content": user_input})

    with chat_area:
        with st.chat_message("assistant", avatar=avatar_image):
            response_placeholder = st.empty()
            tool_container = st.container()

    async def stream_report_response_realtime():
        full_response = ""
        tool_messages = []
        tool_status = None

        async for chunk in st.session_state.agent.chat(user_input, mode="report"):
            if "**도구:" in chunk:
                tool_messages.append(chunk.strip())
                with tool_container:
                    if tool_status is None:
                        tool_status = st.status("도구 실행 중...", expanded=True, state="running")
                    tool_status.write(chunk.strip())
            else:
                full_response += chunk
                response_placeholder.markdown(full_response + "▌")

        response_placeholder.markdown(full_response)
        if tool_status is not None:
            final_state = "error" if any("실패" in m for m in tool_messages) else "complete"
            tool_status.update(label="도구 실행 완료", state=final_state, expanded=False)
        return full_response, tool_messages

    assistant_response, tool_messages = asyncio.run(stream_report_response_realtime())

    st.session_state.report_messages.append({
        "role": "assistant",
        "content": assistant_response,
        "tool_logs": tool_messages
    })

    st.rerun()

st.divider()
st.markdown(
    """
    <div style="text-align: center; color: #64748b; font-size: 0.875rem;">
        Powered by Claude Opus 4.5 | VC Investment Agent v0.3.0
    </div>
    """,
    unsafe_allow_html=True
)
