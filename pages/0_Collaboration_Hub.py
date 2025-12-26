"""
Team Collaboration Hub
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import streamlit as st

from shared.auth import check_authentication, get_user_api_key
from shared.config import initialize_agent, initialize_session_state, inject_custom_css
from shared.sidebar import render_sidebar
from shared.team_tasks import TeamTaskStore, STATUS_LABELS, format_remaining_kst, normalize_status
from shared.doc_checklist import TeamDocChecklistStore
from shared.calendar_store import TeamCalendarStore
from shared.comments_store import TeamCommentStore
from shared.activity_feed import get_recent_activity
from shared.collab_assistant import build_collab_brief, DEFAULT_MODEL


def _parse_due_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _truncate(text: str, limit: int = 140) -> str:
    if not text:
        return ""
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _render_brief_list(title: str, items: list[str]) -> None:
    if not items:
        st.caption(f"{title}: 없음")
        return
    st.markdown(f"**{title}**")
    st.markdown("\n".join([f"- {item}" for item in items]))


st.set_page_config(
    page_title="협업 허브 | VC 투자 분석",
    page_icon="VC",
    layout="wide",
)

initialize_session_state()
check_authentication()
initialize_agent()
inject_custom_css()
render_sidebar(mode="collab")

team_id = st.session_state.get("team_id") or st.session_state.get("user_id") or "team_1"
member_name = st.session_state.get("member_name") or "멤버"
api_key = get_user_api_key()

task_store = TeamTaskStore(team_id=team_id)
doc_store = TeamDocChecklistStore(team_id=team_id)
calendar_store = TeamCalendarStore(team_id=team_id)
comment_store = TeamCommentStore(team_id=team_id)

tasks = task_store.list_tasks(include_done=True, limit=60)
docs = doc_store.list_docs()
events = calendar_store.list_events(limit=12)
comments = comment_store.list_comments(limit=10)

st.markdown(
    """
    <style>
    .hub-hero {
        padding: 8px 0 6px 0;
    }
    .hub-hero h1 {
        font-size: 30px;
        margin-bottom: 4px;
    }
    .hub-hero p {
        color: #6b5f53;
        font-size: 14px;
        margin-top: 0;
    }
    .hub-card {
        border-radius: 16px;
        border: 1px solid rgba(31, 26, 20, 0.08);
        padding: 12px 14px;
        background: rgba(255, 255, 255, 0.85);
        box-shadow: 0 12px 24px rgba(25, 18, 9, 0.06);
    }
    .hub-chip {
        display: inline-block;
        font-size: 11px;
        padding: 3px 8px;
        border-radius: 999px;
        background: rgba(31, 26, 20, 0.08);
        margin-right: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hub-hero">
        <h1>팀 협업 허브</h1>
        <p>팀 과업, 서류, 일정, 코멘트를 한 곳에서 정리합니다. 메리가 오늘의 흐름을 빠르게 정돈해드릴게요.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption(f"현재 팀: {st.session_state.get('team_label', 'Team')} · 담당자: {member_name}")

todo_count = sum(1 for task in tasks if normalize_status(task.get("status", "todo")) == "todo")
progress_count = sum(1 for task in tasks if normalize_status(task.get("status", "")) == "in_progress")
done_count = sum(1 for task in tasks if normalize_status(task.get("status", "")) == "done")

required_docs = [doc for doc in docs if doc.get("required")]
required_uploaded = [doc for doc in required_docs if doc.get("uploaded")]
required_ratio = f"{len(required_uploaded)}/{len(required_docs)}" if required_docs else "0/0"

metric_cols = st.columns(4)
metric_cols[0].metric("진행 전", str(todo_count))
metric_cols[1].metric("진행 중", str(progress_count))
metric_cols[2].metric("완료", str(done_count))
metric_cols[3].metric("필수 서류 업로드", required_ratio)

snapshot_cols = st.columns([1.4, 1])
with snapshot_cols[0]:
    st.markdown("### 오늘 집중 과업")
    upcoming = []
    for task in tasks:
        if normalize_status(task.get("status", "todo")) == "done":
            continue
        due = _parse_due_date(task.get("due_date"))
        if due:
            upcoming.append((due, task))
    upcoming.sort(key=lambda item: item[0])
    focus_tasks = [task for _, task in upcoming][:4]
    if not focus_tasks:
        focus_tasks = [task for task in tasks if normalize_status(task.get("status", "todo")) != "done"][:4]

    if not focus_tasks:
        st.caption("등록된 과업이 없습니다.")
    else:
        for task in focus_tasks:
            remaining = format_remaining_kst(task.get("due_date", ""))
            owner = task.get("owner") or "담당 미정"
            meta = f"담당: {owner}"
            if remaining:
                meta = f"{meta} · {remaining}"
            st.markdown(f"- **{task.get('title', '')}**  \n  {meta}")

with snapshot_cols[1]:
    st.markdown("### 리스크/누락")
    risks = []
    if any(not task.get("owner") for task in tasks if normalize_status(task.get("status", "todo")) != "done"):
        risks.append("담당자 미지정 과업이 있습니다.")
    overdue_tasks = [
        task for task in tasks
        if normalize_status(task.get("status", "todo")) != "done"
        and format_remaining_kst(task.get("due_date", "")).startswith("마감 지남")
    ]
    if overdue_tasks:
        risks.append(f"마감 지연 과업 {len(overdue_tasks)}건 확인 필요.")
    missing_docs = [doc for doc in required_docs if not doc.get("uploaded")]
    if missing_docs:
        risks.append(f"필수 서류 미업로드 {len(missing_docs)}건.")

    if risks:
        st.markdown("\n".join([f"- {item}" for item in risks]))
    else:
        st.caption("현재 등록된 리스크가 없습니다.")

st.divider()

if "collab_brief" not in st.session_state:
    st.session_state.collab_brief = None
if "collab_brief_error" not in st.session_state:
    st.session_state.collab_brief_error = None

with st.expander("메리의 협업 브리프", expanded=True):
    st.caption("팀 데이터를 요약해 오늘의 실행 포인트를 제안합니다.")
    selected_model = st.session_state.get("collab_brief_model", DEFAULT_MODEL)
    st.caption(f"브리프 모델: {selected_model}")
    if st.button("AI 브리프 생성", type="primary", use_container_width=True, key="collab_brief_generate"):
        if not api_key:
            st.warning("Claude API 키가 필요합니다. 로그인 화면에서 API 키를 입력해 주세요.")
        else:
            with st.spinner("메리가 협업 브리프를 생성 중입니다..."):
                try:
                    brief = build_collab_brief(
                        api_key=api_key,
                        tasks=tasks,
                        docs=docs,
                        events=events,
                        recent_comments=comments,
                        model=selected_model,
                    )
                    st.session_state.collab_brief = brief
                    st.session_state.collab_brief_error = None
                except Exception as exc:
                    st.session_state.collab_brief_error = str(exc)

    if st.session_state.collab_brief_error:
        st.warning(f"브리프 생성 실패: {st.session_state.collab_brief_error}")

    brief = st.session_state.collab_brief
    if brief:
        _render_brief_list("오늘 집중", brief.get("today_focus", []))
        _render_brief_list("과업 리스크", brief.get("task_risks", []))
        _render_brief_list("문서 공백", brief.get("doc_gaps", []))
        _render_brief_list("필수 문서 추천", brief.get("required_docs", []))
        _render_brief_list("다음 액션", brief.get("next_actions", []))
        _render_brief_list("확인 질문", brief.get("questions", []))

        recommended_docs = brief.get("required_docs", []) if isinstance(brief.get("required_docs"), list) else []
        if recommended_docs:
            existing_names = {doc.get("name") for doc in docs}
            to_add = [name for name in recommended_docs if name and name not in existing_names]
            if to_add and st.button("추천 문서 체크리스트에 추가", use_container_width=True, key="collab_add_docs"):
                for name in to_add:
                    doc_store.add_doc(name=name, required=True, owner=member_name)
                st.success(f"{len(to_add)}개 문서를 추가했습니다.")
                st.rerun()

st.divider()

st.markdown("## 팀 과업 보드")
status_groups = {"todo": [], "in_progress": [], "done": []}
for task in tasks:
    status_key = normalize_status(task.get("status", "todo"))
    status_groups.setdefault(status_key, []).append(task)

task_cols = st.columns(3)
for col, key in zip(task_cols, ["todo", "in_progress", "done"]):
    with col:
        st.markdown(f"### {STATUS_LABELS.get(key, key)}")
        group = status_groups.get(key, [])
        if not group:
            st.caption("비어 있음")
        else:
            for task in group[:6]:
                remaining = format_remaining_kst(task.get("due_date", ""))
                owner = task.get("owner") or "담당 미정"
                with st.container(border=True):
                    st.markdown(f"**{task.get('title', '')}**")
                    st.caption(f"담당: {owner}")
                    if remaining:
                        st.caption(remaining)
                    elif task.get("due_date"):
                        st.caption(f"마감: {task.get('due_date')}")
                    else:
                        st.caption("마감: 미설정")

with st.expander("과업 추가/수정", expanded=False):
    st.markdown("### 새 과업 추가")
    new_title = st.text_input("과업 제목", key="collab_task_title")
    new_owner = st.text_input("담당자", value=member_name, key="collab_task_owner")
    new_due = st.text_input("마감일 (YYYY-MM-DD)", key="collab_task_due")
    new_notes = st.text_area("메모", key="collab_task_notes", height=80)
    if st.button("과업 추가", use_container_width=True, key="collab_task_add"):
        if not new_title.strip():
            st.warning("과업 제목을 입력해 주세요.")
        else:
            due_date = _parse_due_date(new_due)
            task_store.add_task(
                title=new_title,
                owner=new_owner,
                due_date=due_date,
                notes=new_notes,
                created_by=member_name,
            )
            st.success("과업이 추가되었습니다.")
            st.rerun()

    st.divider()
    st.markdown("### 기존 과업 업데이트")
    status_options = ["todo", "in_progress", "done"]
    for task in tasks:
        task_id = task.get("id")
        if not task_id:
            continue
        with st.container(border=True):
            st.markdown(f"**{task.get('title', '')}**")
            status_value = normalize_status(task.get("status", "todo"))
            status_key = st.selectbox(
                "상태",
                options=status_options,
                index=status_options.index(status_value) if status_value in status_options else 0,
                key=f"collab_task_status_{task_id}",
                format_func=lambda value: STATUS_LABELS.get(value, value),
            )
            owner_value = st.text_input(
                "담당자",
                value=task.get("owner", ""),
                key=f"collab_task_owner_{task_id}",
            )
            due_value = st.text_input(
                "마감일 (YYYY-MM-DD)",
                value=task.get("due_date", ""),
                key=f"collab_task_due_{task_id}",
            )
            notes_value = st.text_area(
                "메모",
                value=task.get("notes", ""),
                key=f"collab_task_notes_{task_id}",
                height=70,
            )
            if st.button("과업 저장", use_container_width=True, key=f"collab_task_save_{task_id}"):
                task_store.update_task(
                    task_id=task_id,
                    status=status_key,
                    owner=owner_value,
                    due_date=_parse_due_date(due_value),
                    notes=notes_value,
                    updated_by=member_name,
                )
                st.success("과업이 업데이트되었습니다.")
                st.rerun()

st.divider()

doc_cols = st.columns([1.2, 1])
with doc_cols[0]:
    st.markdown("## 필수 서류 체크")
    if not docs:
        st.caption("등록된 서류 체크리스트가 없습니다.")
        if st.button("추천 문서 추가", use_container_width=True, key="collab_doc_seed"):
            added = doc_store.seed_defaults()
            st.success(f"{added}개 문서를 추가했습니다.")
            st.rerun()
    else:
        for doc in docs:
            label = f"{doc.get('name', '')} {'(필수)' if doc.get('required') else '(선택)'}"
            with st.container(border=True):
                st.markdown(label)
                st.caption(f"Drive 업로드: {'완료' if doc.get('uploaded') else '미완료'}")
                st.caption(f"담당: {doc.get('owner') or '미지정'}")
                if doc.get("notes"):
                    st.caption(doc.get("notes"))

        with st.expander("서류 상태 업데이트", expanded=False):
            for doc in docs:
                doc_id = doc.get("id")
                if not doc_id:
                    continue
                st.markdown(f"**{doc.get('name', '')}**")
                st.checkbox(
                    "Drive 업로드",
                    value=bool(doc.get("uploaded")),
                    key=f"collab_doc_uploaded_{doc_id}",
                )
                st.text_input(
                    "담당자",
                    value=doc.get("owner", ""),
                    key=f"collab_doc_owner_{doc_id}",
                )
                st.text_area(
                    "메모",
                    value=doc.get("notes", ""),
                    key=f"collab_doc_notes_{doc_id}",
                    height=60,
                )
                st.divider()

            if st.button("문서 변경 저장", use_container_width=True, key="collab_doc_save"):
                for doc in docs:
                    doc_id = doc.get("id")
                    if not doc_id:
                        continue
                    doc_store.update_doc(
                        doc_id=doc_id,
                        uploaded=bool(st.session_state.get(f"collab_doc_uploaded_{doc_id}")),
                        owner=st.session_state.get(f"collab_doc_owner_{doc_id}", ""),
                        notes=st.session_state.get(f"collab_doc_notes_{doc_id}", ""),
                        updated_by=member_name,
                    )
                st.success("문서 상태를 저장했습니다.")
                st.rerun()

with doc_cols[1]:
    st.markdown("## 팀 캘린더")
    if events:
        for event in events:
            note = f" · {event.get('created_by')}" if event.get("created_by") else ""
            st.markdown(f"- **{event.get('date', '')}** {event.get('title', '')}{note}")
            if event.get("notes"):
                st.caption(event.get("notes"))
    else:
        st.caption("등록된 일정이 없습니다.")

    with st.expander("일정 추가", expanded=False):
        event_date = st.date_input("날짜", key="collab_event_date")
        event_title = st.text_input("일정 제목", key="collab_event_title")
        event_notes = st.text_area("메모", key="collab_event_notes", height=80)
        if st.button("일정 저장", use_container_width=True, key="collab_event_save"):
            if not event_title.strip():
                st.warning("일정 제목을 입력해 주세요.")
            else:
                calendar_store.add_event(
                    event_date=event_date,
                    title=event_title,
                    notes=event_notes,
                    created_by=member_name,
                )
                st.success("일정이 저장되었습니다.")
                st.rerun()

st.divider()

activity_cols = st.columns([1.1, 0.9])
with activity_cols[0]:
    st.markdown("## 팀 코멘트")
    if comments:
        for comment in comments:
            meta = comment.get("created_by") or "멤버"
            created_at = comment.get("created_at", "")
            st.caption(f"{meta} · {created_at}")
            st.write(comment.get("text", ""))
    else:
        st.caption("등록된 코멘트가 없습니다.")

    new_comment = st.text_area("코멘트 작성", key="collab_comment_text", height=90)
    if st.button("코멘트 등록", use_container_width=True, key="collab_comment_submit"):
        if not new_comment.strip():
            st.warning("코멘트를 입력해 주세요.")
        else:
            comment_store.add_comment(new_comment, created_by=member_name)
            st.success("코멘트가 등록되었습니다.")
            st.rerun()

with activity_cols[1]:
    st.markdown("## 최근 활동")
    activity = get_recent_activity(team_id, limit=10)
    if not activity:
        st.caption("최근 활동이 없습니다.")
    else:
        for item in activity:
            role = item.get("role", "")
            actor = item.get("member") or "멤버"
            created_at = item.get("created_at", "")
            content = _truncate(item.get("content", ""))
            st.caption(f"{actor} · {created_at} · {role}")
            st.write(content)

st.divider()

st.markdown("## 업무 디렉토리")
project_root = Path(__file__).resolve().parent.parent
team_temp = project_root / "temp" / team_id
team_history = project_root / "chat_history" / team_id
st.markdown(f"- 프로젝트: `{project_root}`")
st.markdown(f"- 팀 temp: `{team_temp}`")
st.markdown(f"- 팀 로그: `{team_history}`")
