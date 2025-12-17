"""
기업현황 진단시트 페이지
- 기업현황 진단시트 분석
- 컨설턴트용 분석보고서 초안 작성/엑셀 반영
"""

import asyncio
from pathlib import Path

import pandas as pd
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
    cleanup_user_temp_files,
    get_secure_upload_path,
    validate_upload,
)
from shared.sidebar import render_sidebar


def _sync_diagnosis_analysis_from_memory():
    """최근 analyze_company_diagnosis_sheet 결과를 세션 상태에 반영"""
    agent = st.session_state.get("agent")
    if not agent or not hasattr(agent, "memory"):
        return

    messages = agent.memory.session_metadata.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") != "tool":
            continue
        meta = msg.get("metadata") or {}
        if meta.get("tool_name") != "analyze_company_diagnosis_sheet":
            continue

        result = meta.get("result")
        if isinstance(result, dict):
            st.session_state.diagnosis_analysis_result = result if result.get("success") else None
        break


# 페이지 설정
st.set_page_config(
    page_title="기업현황 진단시트 | VC 투자 분석",
    page_icon="VC",
    layout="wide",
)

# 초기화
initialize_session_state()
check_authentication()
initialize_agent()
inject_custom_css()

avatar_image = get_avatar_image()
render_sidebar(mode="diagnosis")

_sync_diagnosis_analysis_from_memory()

# ========================================
# 메인 영역
# ========================================
st.markdown("# 기업현황 진단시트")
st.markdown("진단시트를 분석하고 컨설턴트용 분석보고서를 대화로 완성합니다")
st.divider()

# 업로드
st.markdown("### 진단시트 업로드")
upload_cols = st.columns([2, 1])

with upload_cols[0]:
    diagnosis_file = st.file_uploader(
        "기업현황 진단시트 (xlsx)",
        type=["xlsx", "xls"],
        key="diagnosis_excel_uploader",
        help="기업현황 진단시트 템플릿 파일을 업로드하세요",
    )

with upload_cols[1]:
    if diagnosis_file:
        is_valid, error = validate_upload(
            filename=diagnosis_file.name,
            file_size=diagnosis_file.size,
            allowed_extensions=ALLOWED_EXTENSIONS_EXCEL,
        )
        if not is_valid:
            st.error(error)
        else:
            user_id = st.session_state.get("user_id", "anonymous")
            secure_path = get_secure_upload_path(user_id=user_id, original_filename=diagnosis_file.name)
            with open(secure_path, "wb") as f:
                f.write(diagnosis_file.getbuffer())

            cleanup_user_temp_files(user_id, max_files=10)
            st.session_state.diagnosis_excel_path = str(secure_path)
            st.session_state.diagnosis_excel_name = diagnosis_file.name
            st.success(f"업로드 완료: {diagnosis_file.name}")

st.divider()

# 빠른 명령어
if st.session_state.get("diagnosis_excel_path"):
    file_name = st.session_state.get("diagnosis_excel_name", "파일")
    quick_cols = st.columns(3)

    with quick_cols[0]:
        if st.button("시트 분석", use_container_width=True, type="primary", key="diag_quick_analyze"):
            st.session_state.diagnosis_quick_command = f"{file_name} 파일을 분석해줘"

    with quick_cols[1]:
        if st.button("보고서 초안", use_container_width=True, type="primary", key="diag_quick_draft"):
            st.session_state.diagnosis_quick_command = (
                f"{file_name} 파일을 분석하고 컨설턴트용 분석보고서 초안을 작성해줘. "
                "점수(문제/솔루션/사업화/자금조달/팀/조직/임팩트)와 근거도 제시해줘."
            )

    with quick_cols[2]:
        if st.button("엑셀 반영", use_container_width=True, key="diag_quick_write"):
            st.session_state.diagnosis_quick_command = (
                f"{file_name} 파일을 분석하고 컨설턴트용 분석보고서 초안을 작성해줘. "
                "내가 '반영해줘'라고 확인하면 엑셀에 반영해서 새 파일로 저장해줘."
            )

    st.divider()

# 분석 요약 패널
if st.session_state.get("diagnosis_analysis_result"):
    result = st.session_state.diagnosis_analysis_result
    company_name = (result.get("company_info") or {}).get("company_name") or "N/A"

    st.markdown("### 분석 요약")
    st.caption(f"기업명: {company_name}")

    scores = result.get("scores") or {}
    if scores:
        rows = []
        for category, s in scores.items():
            rows.append(
                {
                    "항목": category,
                    "점수": s.get("score"),
                    "가중치": s.get("weight"),
                    "예/전체": f"{s.get('yes', 0)}/{s.get('total', 0)}",
                    "예 비율": f"{s.get('yes_rate_pct')}%" if s.get("yes_rate_pct") is not None else "N/A",
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    gaps = ((result.get("checklist") or {}).get("gaps") or [])
    if gaps:
        with st.expander(f"미충족(아니오) 항목 {len(gaps)}개", expanded=False):
            for g in gaps[:20]:
                st.caption(f"- [{g.get('module')}] {g.get('question')}")

    st.divider()

# 채팅 컨테이너
chat_container = st.container(border=True, height=600)

with chat_container:
    chat_area = st.container(height=520)

    with chat_area:
        if st.session_state.diagnosis_show_welcome and not st.session_state.diagnosis_messages:
            with st.chat_message("assistant", avatar=avatar_image):
                st.markdown(
                    """기업현황 진단시트를 기반으로 컨설턴트용 분석보고서를 작성합니다.

### 시작하기
1. 위에서 **진단시트 엑셀**을 업로드하세요
2. 아래 입력창에 **\"보고서 초안\"** 또는 **\"엑셀 반영\"**을 요청하세요

예시:
- \"보고서 초안 만들어줘\"
- \"개선 필요사항을 더 구체적으로 써줘\"
- \"이대로 엑셀에 반영해줘\"
"""
                )
            st.session_state.diagnosis_show_welcome = False

        for msg in st.session_state.diagnosis_messages:
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

    user_input = st.chat_input("진단시트 관련 요청...", key="diagnosis_chat_input")

# ========================================
# 메시지 처리
# ========================================
if "diagnosis_quick_command" in st.session_state:
    user_input = st.session_state.diagnosis_quick_command
    del st.session_state.diagnosis_quick_command

if user_input:
    diagnosis_path = st.session_state.get("diagnosis_excel_path")
    diagnosis_name = st.session_state.get("diagnosis_excel_name", "")

    if diagnosis_path:
        if diagnosis_name and diagnosis_name in user_input:
            user_input = user_input.replace(diagnosis_name, diagnosis_path)
        elif diagnosis_path not in user_input:
            stripped = user_input.strip()
            if stripped in ["분석해줘", "분석", "진단해줘"]:
                user_input = f"{diagnosis_path} 파일을 분석해줘"
            elif any(k in stripped for k in ["보고서", "초안", "엑셀", "반영", "저장"]):
                user_input = f"{diagnosis_path} 파일을 " + stripped

    st.session_state.diagnosis_messages.append({"role": "user", "content": user_input})

    with chat_area:
        with st.chat_message("assistant", avatar=avatar_image):
            response_placeholder = st.empty()
            tool_container = st.container()

    async def stream_diagnosis_response_realtime():
        full_response = ""
        tool_messages = []
        tool_status = None

        async for chunk in st.session_state.agent.chat(user_input, mode="diagnosis"):
            if "**도구:" in chunk:
                tool_messages.append(chunk.strip())
                with tool_container:
                    if tool_status is None:
                        tool_status = st.status("도구 실행 로그", expanded=False, state="running")
                    tool_status.write(chunk.strip())
            else:
                full_response += chunk
                response_placeholder.markdown(full_response + "▌")

        response_placeholder.markdown(full_response)
        if tool_status is not None:
            final_state = "error" if any("실패" in m for m in tool_messages) else "complete"
            tool_status.update(state=final_state, expanded=False)
        return full_response, tool_messages

    assistant_response, tool_messages = asyncio.run(stream_diagnosis_response_realtime())
    st.session_state.diagnosis_messages.append(
        {"role": "assistant", "content": assistant_response, "tool_logs": tool_messages}
    )
    st.rerun()

# ========================================
# 결과 다운로드 (진단 보고서)
# ========================================
memory = getattr(st.session_state.get("agent"), "memory", None)
generated_files = []
if memory:
    generated_files = memory.session_metadata.get("generated_files", []) or []

latest_report_path = None
for p in reversed(generated_files):
    name = Path(p).name
    if name.startswith("diagnosis_report_") and name.lower().endswith(".xlsx"):
        latest_report_path = Path(p)
        break

if latest_report_path:
    project_root = Path(__file__).resolve().parent.parent
    temp_root = (project_root / "temp").resolve()

    try:
        resolved = latest_report_path.resolve()
        resolved.relative_to(temp_root)
        is_downloadable = resolved.is_file()
    except Exception:
        is_downloadable = False

    if is_downloadable:
        st.divider()
        st.markdown("### 최근 생성된 분석보고서")
        st.caption(f"• {resolved.name}")
        st.download_button(
            "다운로드",
            data=resolved.read_bytes(),
            file_name=resolved.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=False,
            key=f"diagnosis_download_latest_{memory.session_id}",
        )

# 푸터
st.divider()
st.markdown(
    """
    <div style="text-align: center; color: #64748b; font-size: 0.875rem;">
        Powered by Claude Opus 4.5 | VC Investment Agent v0.3.0
    </div>
    """,
    unsafe_allow_html=True,
)
