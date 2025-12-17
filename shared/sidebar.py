"""
공통 사이드바 모듈
- 사용자 정보
- 파일 업로드
- 세션 관리
"""

import streamlit as st
from pathlib import Path

from shared.file_utils import (
    get_secure_upload_path,
    cleanup_user_temp_files,
    validate_upload,
    ALLOWED_EXTENSIONS_EXCEL
)


def render_sidebar(mode: str = "exit"):
    """모든 페이지에서 사용하는 공통 사이드바

    Args:
        mode: "exit" | "peer" | "diagnosis"
    """
    with st.sidebar:
        # 로그인 정보
        user_id = st.session_state.get('user_id', 'anonymous')
        st.markdown(f"**User: {user_id[:8]}...**")
        st.caption("Claude API Key 인증")

        st.divider()

        # 파일 업로드 (페이지별)
        if mode == "exit":
            st.markdown("### 파일 업로드")

            uploaded_file = st.file_uploader(
                "투자검토 엑셀",
                type=["xlsx", "xls"],
                help="분석할 투자검토 엑셀 파일",
                label_visibility="collapsed",
                key="sidebar_excel_uploader"
            )

            if uploaded_file:
                # 업로드 전 검증 (확장자 + 크기)
                is_valid, error = validate_upload(
                    filename=uploaded_file.name,
                    file_size=uploaded_file.size,
                    allowed_extensions=ALLOWED_EXTENSIONS_EXCEL
                )

                if not is_valid:
                    st.error(error)
                else:
                    # 안전한 업로드 경로 생성 (사용자별 격리)
                    secure_path = get_secure_upload_path(
                        user_id=user_id,
                        original_filename=uploaded_file.name
                    )

                    with open(secure_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    # 오래된 파일 정리 (최신 10개 + TTL 7일)
                    cleanup_user_temp_files(user_id, max_files=10)

                    st.success(f"{uploaded_file.name}")
                    st.session_state.uploaded_file_path = str(secure_path)
                    st.session_state.uploaded_file_name = uploaded_file.name
        elif mode == "peer":
            st.markdown("### 파일 업로드")
            st.caption("Peer PER 모드에서는 메인 화면에서 PDF를 업로드합니다.")
        elif mode == "diagnosis":
            st.markdown("### 파일 업로드")
            st.caption("진단시트 모드에서는 메인 화면에서 엑셀을 업로드합니다.")

        st.divider()

        # 세션 관리
        st.markdown("### 세션 관리")

        if st.session_state.agent and hasattr(st.session_state.agent, 'memory'):
            memory = st.session_state.agent.memory

            # 최근 세션 목록
            recent_sessions = memory.get_recent_sessions(limit=10)

            if recent_sessions:
                # 세션 선택 드롭다운 (현재 세션 정보 포함)
                current_user_info = memory.session_metadata.get("user_info", {})
                if current_user_info.get("nickname") and current_user_info.get("company"):
                    current_label = f"현재: {current_user_info['nickname']} - {current_user_info['company']}"
                else:
                    current_label = "현재 세션"

                session_options = [current_label] + [
                    f"{s['session_id']} ({s.get('message_count', 0)}개 메시지)"
                    for s in recent_sessions
                    if s['session_id'] != memory.session_id
                ]

                selected_session = st.selectbox(
                    "세션 선택",
                    options=session_options,
                    key="session_selector",
                    label_visibility="collapsed"
                )

                # 세션 불러오기 버튼
                if not selected_session.startswith("현재"):
                    if st.button("세션 불러오기", use_container_width=True, type="primary", key="load_session"):
                        _load_session(selected_session)

            st.divider()

            # 분석 현황
            st.markdown("### 분석 현황")

            # 사용자 정보
            user_info = memory.session_metadata.get("user_info", {})
            if user_info.get("nickname") and user_info.get("company"):
                st.markdown(f"**담당자**: {user_info['nickname']}")
                st.markdown(f"**분석 기업**: {user_info['company']}")
                st.divider()

            # 분석된 파일
            if memory.session_metadata.get("analyzed_files"):
                st.markdown("**분석된 파일:**")
                for file in memory.session_metadata["analyzed_files"]:
                    st.caption(f"• {Path(file).name}")

            # 생성된 파일
            if memory.session_metadata.get("generated_files"):
                st.markdown("**생성된 파일:**")
                files = memory.session_metadata["generated_files"]
                latest_file = files[-1]
                latest_path = Path(latest_file)
                st.caption(f"• {latest_path.name}")

                # temp 디렉토리 내부 파일만 다운로드 허용
                project_root = Path(__file__).resolve().parent.parent
                temp_root = (project_root / "temp").resolve()

                try:
                    resolved_path = latest_path.resolve()
                    resolved_path.relative_to(temp_root)
                    is_in_temp = resolved_path.is_file()
                except Exception:
                    is_in_temp = False

                if is_in_temp:
                    ext = resolved_path.suffix.lower()
                    mime_by_ext = {
                        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        ".xls": "application/vnd.ms-excel",
                        ".pdf": "application/pdf",
                    }
                    mime = mime_by_ext.get(ext, "application/octet-stream")

                    try:
                        st.download_button(
                            "최근 생성 파일 다운로드",
                            data=resolved_path.read_bytes(),
                            file_name=resolved_path.name,
                            mime=mime,
                            use_container_width=True,
                            type="primary",
                            key=f"download_latest_generated_{memory.session_id}"
                        )
                    except OSError:
                        st.caption("다운로드 파일을 준비할 수 없습니다.")

                if len(files) > 1:
                    with st.expander("이전 생성 파일", expanded=False):
                        for file in reversed(files[:-1]):
                            st.caption(f"• {Path(file).name}")

            # 세션 정보
            st.caption(f"메시지: {len(memory.session_metadata.get('messages', []))}개")
            st.caption(f"세션 ID: {memory.session_id}")

            # 피드백 통계
            if hasattr(st.session_state.agent, 'feedback'):
                feedback_stats = st.session_state.agent.feedback.get_feedback_stats()
                if feedback_stats["total_feedback"] > 0:
                    st.markdown("**피드백 통계:**")
                    st.caption(f"총 피드백: {feedback_stats['total_feedback']}개")
                    st.caption(f"만족도: {feedback_stats['satisfaction_rate']*100:.0f}%")

            # 토큰 사용량
            if hasattr(st.session_state.agent, 'get_token_usage'):
                usage = st.session_state.agent.get_token_usage()
                if usage["total_tokens"] > 0:
                    st.divider()
                    st.markdown("**토큰 사용량:**")
                    st.caption(f"입력: {usage['input_tokens']:,} 토큰")
                    st.caption(f"출력: {usage['output_tokens']:,} 토큰")
                    st.caption(f"API 호출: {usage['api_calls']}회")
                    st.caption(f"예상 비용: ${usage['estimated_cost_usd']:.4f} (₩{usage['estimated_cost_krw']:,.0f})")

            # 히스토리 내보내기
            if st.button("히스토리 내보내기", use_container_width=True, type="primary", key="export_history"):
                export_path = memory.export_session()
                st.success(f"내보내기 완료: {export_path}")

        st.divider()

        # 세션 초기화
        if st.button("대화 초기화", use_container_width=True, type="secondary", key="reset_session"):
            _reset_session()


def _load_session(selected_session: str):
    """선택된 세션 불러오기"""
    memory = st.session_state.agent.memory

    # 선택된 세션 ID 추출
    selected_session_id = selected_session.split(" ")[0]

    # 세션 데이터 로드
    session_data = memory.load_session(selected_session_id)

    if session_data:
        messages = session_data.get("messages", []) or []

        # UI 메시지 복원 (user/assistant만)
        ui_messages = []
        for msg in messages:
            if msg.get("role") not in ["user", "assistant"]:
                continue
            ui_messages.append(
                {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                }
            )

        st.session_state.exit_messages = list(ui_messages)
        st.session_state.peer_messages = list(ui_messages)
        st.session_state.diagnosis_messages = list(ui_messages)

        # 파생 결과는 세션에 맞게 다시 sync 되도록 초기화
        st.session_state.projection_data = None
        st.session_state.peer_analysis_result = None
        st.session_state.diagnosis_analysis_result = None

        # 에이전트 컨텍스트 복원
        st.session_state.agent.context["analyzed_files"] = session_data.get("analyzed_files", [])
        memory.session_id = session_data.get("session_id", selected_session_id)
        memory.session_metadata = dict(session_data)
        memory.session_metadata["session_id"] = memory.session_id
        memory.session_metadata["user_id"] = memory.user_id
        memory.current_session_file = memory.storage_dir / f"session_{memory.session_id}.json"

        # 대화 히스토리 복원
        st.session_state.agent.conversation_history = []
        for msg in ui_messages:
            st.session_state.agent.conversation_history.append(
                {
                    "role": msg.get("role"),
                    "content": msg.get("content", ""),
                }
            )

        # 사용자 정보 수집 상태 복원
        user_info = session_data.get("user_info", {})
        if user_info.get("nickname") and user_info.get("company"):
            st.session_state.exit_user_info_collected = True
        else:
            st.session_state.exit_user_info_collected = False
        st.session_state.exit_show_welcome = not st.session_state.exit_user_info_collected

        # 가능하면 마지막 분석 파일도 복원 (temp 내부 파일만)
        analyzed_files = session_data.get("analyzed_files", []) or []
        project_root = Path(__file__).resolve().parent.parent
        temp_root = (project_root / "temp").resolve()
        last_pdf = None
        last_excel = None
        for p in reversed(analyzed_files):
            path = Path(p)
            try:
                resolved = path.resolve()
                resolved.relative_to(temp_root)
                if not resolved.is_file():
                    continue
            except Exception:
                continue

            ext = resolved.suffix.lower()
            if ext == ".pdf" and last_pdf is None:
                last_pdf = resolved
            if ext in [".xlsx", ".xls"] and last_excel is None:
                last_excel = resolved
            if last_pdf and last_excel:
                break

        if last_pdf:
            st.session_state.peer_pdf_path = str(last_pdf)
            st.session_state.peer_pdf_name = last_pdf.name

        if last_excel:
            st.session_state.uploaded_file_path = str(last_excel)
            st.session_state.uploaded_file_name = last_excel.name
            st.session_state.diagnosis_excel_path = str(last_excel)
            st.session_state.diagnosis_excel_name = last_excel.name

        st.success(f"세션 {selected_session_id} 불러오기 완료")
        st.rerun()
    else:
        st.error("세션을 불러올 수 없습니다.")


def _reset_session():
    """세션 초기화"""
    if st.session_state.agent:
        st.session_state.agent.reset()
        if hasattr(st.session_state.agent, "memory"):
            current_user_info = st.session_state.agent.memory.session_metadata.get("user_info", {})
            st.session_state.agent.memory.start_new_session(user_info=current_user_info)

    st.session_state.exit_messages = []
    st.session_state.peer_messages = []
    st.session_state.diagnosis_messages = []
    st.session_state.projection_data = None
    st.session_state.peer_analysis_result = None
    st.session_state.diagnosis_analysis_result = None
    memory = getattr(st.session_state.agent, "memory", None)
    user_info = memory.session_metadata.get("user_info", {}) if memory else {}
    st.session_state.exit_user_info_collected = bool(user_info.get("nickname") and user_info.get("company"))
    st.session_state.exit_show_welcome = not st.session_state.exit_user_info_collected
    st.session_state.diagnosis_show_welcome = True

    st.rerun()
