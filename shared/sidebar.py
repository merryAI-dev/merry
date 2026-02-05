"""
공통 사이드바 모듈
- 사용자 정보
- 파일 업로드
- 세션 관리
"""

import time
import streamlit as st
from pathlib import Path

from shared.file_utils import (
    get_secure_upload_path,
    cleanup_user_temp_files,
    validate_upload,
    ALLOWED_EXTENSIONS_EXCEL
)
from shared.session_utils import load_session_by_id
from shared.calendar_store import TeamCalendarStore
from shared.doc_checklist import TeamDocChecklistStore
from shared.comments_store import TeamCommentStore


def render_sidebar(mode: str = "exit"):
    """모든 페이지에서 사용하는 공통 사이드바

    Args:
        mode: "exit" | "peer" | "diagnosis" | "report"
    """
    with st.sidebar:
        # 로그인 정보
        user_id = st.session_state.get('user_id', 'anonymous')
        team_label = st.session_state.get("team_label") or "Team"
        member_name = st.session_state.get("member_name") or "멤버"
        st.markdown(f"**{team_label} | {member_name}**")
        st.caption(f"팀 세션 ID: {user_id}")

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
        elif mode == "report":
            st.markdown("### 파일 업로드")
            st.caption("보고서 모드에서는 메인 화면에서 기업 자료를 업로드합니다.")
        elif mode == "collab":
            st.markdown("### 파일 업로드")
            st.caption("협업 허브에서는 별도 파일 업로드를 사용하지 않습니다.")

        st.divider()

        # 세션 관리
        st.markdown("### 세션 관리")

        if st.session_state.agent and hasattr(st.session_state.agent, 'memory'):
            memory = st.session_state.agent.memory
            cache = st.session_state.get("sidebar_cache", {})
            cache_ttl = 45

            refresh = st.button("세션/통계 새로고침", use_container_width=True, key="sidebar_refresh")
            if refresh:
                cache.pop(f"recent_sessions:{memory.user_id}", None)
                cache.pop(f"feedback_stats:{memory.user_id}", None)
                st.session_state.sidebar_cache = cache

            def _get_cached(key: str):
                entry = cache.get(key)
                if not entry:
                    return None
                if time.time() - entry.get("ts", 0) > cache_ttl:
                    cache.pop(key, None)
                    return None
                return entry.get("data")

            def _set_cached(key: str, data):
                cache[key] = {"ts": time.time(), "data": data}
                st.session_state.sidebar_cache = cache

            # 최근 세션 목록
            sessions_key = f"recent_sessions:{memory.user_id}"
            recent_sessions = None if refresh else _get_cached(sessions_key)
            if recent_sessions is None:
                recent_sessions = memory.get_recent_sessions(limit=10)
                _set_cached(sessions_key, recent_sessions)

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

            # 업무 디렉토리
            st.markdown("### 업무 디렉토리")
            project_root = Path(__file__).resolve().parent.parent
            team_id = st.session_state.get("team_id") or memory.user_id
            temp_dir = project_root / "temp" / team_id
            history_dir = project_root / "chat_history" / team_id
            st.caption(f"프로젝트: `{project_root}`")
            st.caption(f"팀 temp: `{temp_dir}`")
            st.caption(f"팀 로그: `{history_dir}`")

            st.divider()

            # 팀 캘린더
            st.markdown("### 팀 캘린더")
            team_id = st.session_state.get("team_id") or memory.user_id
            calendar = TeamCalendarStore(team_id=team_id)
            events = calendar.list_events(limit=8)

            if events:
                for event in events:
                    title = event.get("title", "일정")
                    date_str = event.get("date", "")
                    created_by = event.get("created_by", "")
                    note = f" · {created_by}" if created_by else ""
                    st.caption(f"{date_str} | {title}{note}")
            else:
                st.caption("등록된 팀 일정이 없습니다.")

            with st.expander("일정 추가", expanded=False):
                event_date = st.date_input("날짜", key="calendar_event_date")
                event_title = st.text_input("일정 제목", key="calendar_event_title")
                event_notes = st.text_area("메모", key="calendar_event_notes", height=80)
                if st.button("일정 저장", use_container_width=True, key="calendar_event_save"):
                    if not event_title.strip():
                        st.warning("일정 제목을 입력해 주세요.")
                    else:
                        calendar.add_event(
                            event_date=event_date,
                            title=event_title,
                            notes=event_notes,
                            created_by=st.session_state.get("member_name", ""),
                        )
                        st.success("팀 일정이 저장되었습니다.")
                        st.rerun()

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
                stats_key = f"feedback_stats:{memory.user_id}"
                feedback_stats = None if refresh else _get_cached(stats_key)
                if feedback_stats is None:
                    feedback_stats = st.session_state.agent.feedback.get_feedback_stats()
                    _set_cached(stats_key, feedback_stats)
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

        # 필수 서류 체크리스트
        st.markdown("### 필수 서류 체크리스트")
        team_id = st.session_state.get("team_id") or user_id
        member_name = st.session_state.get("member_name") or ""
        doc_store = TeamDocChecklistStore(team_id=team_id)
        docs = doc_store.list_docs()

        if not docs:
            st.caption("필수 서류 리스트가 없습니다.")
            if st.button("추천 문서 추가", use_container_width=True, key="doc_seed_defaults"):
                added = doc_store.seed_defaults()
                st.success(f"{added}개 문서를 추가했습니다.")
                st.rerun()
        else:
            with st.expander("문서 상태 보기/수정", expanded=True):
                for doc in docs:
                    doc_id = doc.get("id")
                    uploaded_key = f"doc_uploaded_{doc_id}"
                    owner_key = f"doc_owner_{doc_id}"
                    notes_key = f"doc_notes_{doc_id}"
                    name = doc.get("name", "")
                    required = doc.get("required", False)
                    label = f"{name} {'(필수)' if required else '(선택)'}"

                    cols = st.columns([2.4, 1, 1.2])
                    with cols[0]:
                        st.markdown(label)
                    with cols[1]:
                        st.checkbox(
                            "Drive 업로드",
                            value=bool(doc.get("uploaded")),
                            key=uploaded_key,
                        )
                    with cols[2]:
                        st.text_input(
                            "담당자",
                            value=doc.get("owner", ""),
                            key=owner_key,
                        )

                    st.text_area(
                        "메모",
                        value=doc.get("notes", ""),
                        key=notes_key,
                        height=60,
                    )
                    st.divider()

                if st.button("문서 변경 저장", use_container_width=True, key="doc_save_updates"):
                    for doc in docs:
                        doc_id = doc.get("id")
                        uploaded_val = st.session_state.get(f"doc_uploaded_{doc_id}")
                        owner_val = st.session_state.get(f"doc_owner_{doc_id}") or ""
                        notes_val = st.session_state.get(f"doc_notes_{doc_id}") or ""
                        doc_store.update_doc(
                            doc_id=doc_id,
                            uploaded=bool(uploaded_val),
                            owner=owner_val,
                            notes=notes_val,
                            updated_by=member_name,
                        )
                    st.success("문서 상태가 저장되었습니다.")
                    st.rerun()

            with st.expander("문서 추가", expanded=False):
                new_doc_name = st.text_input("문서명", key="doc_new_name")
                new_doc_required = st.checkbox("필수 문서", value=True, key="doc_new_required")
                new_doc_owner = st.text_input("담당자", value=member_name, key="doc_new_owner")
                new_doc_notes = st.text_area("메모", key="doc_new_notes", height=60)
                if st.button("문서 추가", use_container_width=True, key="doc_new_submit"):
                    if not new_doc_name.strip():
                        st.warning("문서명을 입력해 주세요.")
                    else:
                        doc_store.add_doc(
                            name=new_doc_name,
                            required=new_doc_required,
                            owner=new_doc_owner,
                            notes=new_doc_notes,
                        )
                        st.success("문서가 추가되었습니다.")
                        st.rerun()

        st.divider()

        # 팀 코멘트 (항상 표시)
        st.markdown("### 팀 코멘트")
        comment_store = TeamCommentStore(team_id=team_id)
        comments = comment_store.list_comments(limit=12)
        if comments:
            for comment in comments:
                meta = comment.get("created_by") or "멤버"
                created_at = comment.get("created_at", "")
                st.caption(f"{meta} · {created_at}")
                st.write(comment.get("text", ""))
        else:
            st.caption("등록된 코멘트가 없습니다.")

        comment_text = st.text_area("코멘트 작성", key="team_comment_text", height=80)
        if st.button("코멘트 등록", use_container_width=True, key="team_comment_submit"):
            if not comment_text.strip():
                st.warning("코멘트를 입력해 주세요.")
            else:
                comment_store.add_comment(comment_text, created_by=member_name)
                st.success("코멘트가 등록되었습니다.")
                st.rerun()

        # 세션 초기화
        if st.button("대화 초기화", use_container_width=True, type="secondary", key="reset_session"):
            _reset_session()


def _load_session(selected_session: str):
    selected_session_id = selected_session.split(" ")[0]
    if st.session_state.agent and load_session_by_id(st.session_state.agent, selected_session_id):
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
    st.session_state.report_messages = []
    st.session_state.report_file_path = None
    st.session_state.report_file_name = None
    st.session_state.report_files = []
    st.session_state.report_file_types = {}
    st.session_state.report_doc_weights = {
        "IR": 0.4,
        "요약보고서": 0.3,
        "사업자등록증": 0.2,
        "기타": 0.1,
    }
    st.session_state.report_uploaded_names = []
    st.session_state.report_draft_content = ""
    st.session_state.projection_data = None
    st.session_state.exit_projection_assumptions = None
    st.session_state.peer_analysis_result = None
    st.session_state.diagnosis_analysis_result = None
    st.session_state.diagnosis_draft_path = None
    st.session_state.diagnosis_draft_progress = None
    st.session_state.report_evidence = None
    st.session_state.report_deep_analysis = None
    st.session_state.report_deep_error = None
    st.session_state.report_deep_step = 0
    st.session_state.uploaded_file_path = None
    st.session_state.uploaded_file_name = None
    st.session_state.peer_pdf_path = None
    st.session_state.peer_pdf_name = None
    st.session_state.diagnosis_excel_path = None
    st.session_state.diagnosis_excel_name = None
    memory = getattr(st.session_state.agent, "memory", None)
    user_info = memory.session_metadata.get("user_info", {}) if memory else {}
    st.session_state.exit_user_info_collected = bool(user_info.get("nickname") and user_info.get("company"))
    st.session_state.exit_show_welcome = not st.session_state.exit_user_info_collected
    st.session_state.diagnosis_show_welcome = True

    st.rerun()
