"""
Team Collaboration Hub
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

import streamlit as st
import streamlit.components.v1 as components

from shared.auth import check_authentication, get_user_api_key
from shared.config import initialize_agent, initialize_session_state, inject_custom_css
from shared.sidebar import render_sidebar
from shared.team_tasks import TeamTaskStore, STATUS_LABELS, format_remaining_kst, normalize_status
from shared.doc_checklist import TeamDocChecklistStore
from shared.calendar_store import TeamCalendarStore
from shared.comments_store import TeamCommentStore
from shared.activity_feed import get_recent_activity
from shared.collab_assistant import build_collab_brief, DEFAULT_MODEL
from shared.ui import render_page_header


def _parse_due_date(value: Optional[str]) -> Optional[date]:
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
    page_title="협업 허브 | 메리",
    page_icon="image-removebg-preview-5.png",
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

render_page_header(
    "팀 협업 허브",
    "팀 과업, 서류, 일정, 코멘트를 한 곳에서 정리합니다. 메리가 오늘의 흐름을 빠르게 정돈해드릴게요.",
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
board_filters = st.columns([1, 1, 2])
with board_filters[0]:
    show_done = st.toggle("완료 포함", value=False, key="collab_board_show_done")
with board_filters[1]:
    compact_view = st.toggle("요약 카드", value=True, key="collab_board_compact")
with board_filters[2]:
    st.caption("카드를 드래그해서 전/중/완료로 이동하세요. 상세 편집은 아래에서 가능합니다.")

board_tasks = []
task_lookup = {}
for task in tasks:
    status_key = normalize_status(task.get("status", "todo"))
    if not show_done and status_key == "done":
        continue
    task_id = task.get("id")
    if not task_id:
        continue
    remaining = format_remaining_kst(task.get("due_date", ""))
    card = {
        "id": task_id,
        "title": task.get("title", ""),
        "status": status_key,
        "owner": task.get("owner", ""),
        "due": task.get("due_date", ""),
        "remaining": remaining,
        "notes": task.get("notes", ""),
    }
    board_tasks.append(card)
    task_lookup[task_id] = task

board_payload = json.dumps(board_tasks, ensure_ascii=False)
compact_flag = "true" if compact_view else "false"
board_height = max(420, 140 + 110 * max(1, len(board_tasks) // 3 + 1))

board_html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<style>
    body {{
        margin: 0;
        font-family: "DM Sans", "Noto Sans KR", sans-serif;
        background: transparent;
    }}
    .board {{
        display: grid;
        grid-template-columns: repeat(3, minmax(220px, 1fr));
        gap: 16px;
        padding: 4px 2px 12px 2px;
    }}
    .column {{
        background: rgba(255, 255, 255, 0.92);
        border: 1px solid #e2e8f0;
        border-radius: 20px;
        display: flex;
        flex-direction: column;
        min-height: 320px;
        box-shadow: 0 12px 28px rgba(112, 144, 176, 0.14);
    }}
    .column-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 14px 8px 14px;
        font-size: 13px;
        font-weight: 600;
        color: #1a202c;
        border-bottom: 1px solid #edf2f7;
    }}
    .count {{
        font-size: 11px;
        padding: 3px 8px;
        border-radius: 999px;
        background: rgba(67, 24, 255, 0.12);
        color: #4318ff;
    }}
    .column-body {{
        padding: 10px;
        display: flex;
        flex-direction: column;
        gap: 10px;
        flex: 1;
        overflow-y: auto;
        min-height: 200px;
    }}
    .column-body.drag-over {{
        outline: 2px dashed rgba(67, 24, 255, 0.45);
        outline-offset: -6px;
        background: rgba(67, 24, 255, 0.05);
    }}
    .card {{
        background: rgba(255, 255, 255, 0.98);
        border-radius: 16px;
        border: 1px solid #e2e8f0;
        padding: 10px 12px;
        box-shadow: 0 8px 18px rgba(112, 144, 176, 0.12);
        cursor: grab;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }}
    .card:active {{
        cursor: grabbing;
    }}
    .card.dragging {{
        opacity: 0.6;
        transform: rotate(-1deg) scale(0.98);
    }}
    .card-title {{
        font-size: 13px;
        font-weight: 600;
        color: #1a202c;
    }}
    .card-meta {{
        margin-top: 6px;
        font-size: 11px;
        color: #718096;
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
    }}
    .card-tag {{
        padding: 2px 6px;
        border-radius: 999px;
        background: rgba(67, 24, 255, 0.12);
        color: #4318ff;
    }}
    .empty {{
        font-size: 12px;
        color: #a0aec0;
        padding: 8px 4px;
    }}
</style>
</head>
<body>
<div class="board" id="board"></div>
<script>
const tasks = {board_payload};
const compactView = {compact_flag};
const columns = [
    {{ key: "todo", label: "진행 전" }},
    {{ key: "in_progress", label: "진행 중" }},
    {{ key: "done", label: "완료" }},
];

const board = document.getElementById("board");
let dragId = null;
let dragFrom = null;

window.parent.postMessage(
    {{ isStreamlitMessage: true, type: "streamlit:componentReady", apiVersion: 1 }},
    "*"
);

function sendMove(payload) {{
    window.parent.postMessage(
        {{
            isStreamlitMessage: true,
            type: "streamlit:componentValue",
            value: payload
        }},
        "*"
    );
}}

function buildBoard() {{
    board.innerHTML = "";
    columns.forEach((column) => {{
        const col = document.createElement("div");
        col.className = "column";
        col.dataset.status = column.key;

        const header = document.createElement("div");
        header.className = "column-header";
        const title = document.createElement("div");
        title.textContent = column.label;
        const count = document.createElement("div");
        count.className = "count";
        const filtered = tasks.filter((task) => task.status === column.key);
        count.textContent = filtered.length;
        header.appendChild(title);
        header.appendChild(count);

        const body = document.createElement("div");
        body.className = "column-body";
        body.dataset.status = column.key;

        if (!filtered.length) {{
            const empty = document.createElement("div");
            empty.className = "empty";
            empty.textContent = "드래그해서 이동";
            body.appendChild(empty);
        }} else {{
            filtered.forEach((task) => {{
                const card = document.createElement("div");
                card.className = "card";
                card.draggable = true;
                card.dataset.id = task.id;
                card.dataset.status = task.status;

                const titleEl = document.createElement("div");
                titleEl.className = "card-title";
                titleEl.textContent = task.title || "제목 없음";
                card.appendChild(titleEl);

                const meta = document.createElement("div");
                meta.className = "card-meta";
                if (task.owner) {{
                    const tag = document.createElement("span");
                    tag.className = "card-tag";
                    tag.textContent = task.owner;
                    meta.appendChild(tag);
                }}
                if (task.remaining) {{
                    const tag = document.createElement("span");
                    tag.className = "card-tag";
                    tag.textContent = task.remaining;
                    meta.appendChild(tag);
                }} else if (task.due) {{
                    const tag = document.createElement("span");
                    tag.className = "card-tag";
                    tag.textContent = task.due;
                    meta.appendChild(tag);
                }}
                if (!compactView && task.notes) {{
                    const tag = document.createElement("span");
                    tag.className = "card-tag";
                    tag.textContent = task.notes.slice(0, 26);
                    meta.appendChild(tag);
                }}
                card.appendChild(meta);

                card.addEventListener("dragstart", (event) => {{
                    dragId = task.id;
                    dragFrom = task.status;
                    card.classList.add("dragging");
                    event.dataTransfer.effectAllowed = "move";
                    event.dataTransfer.setData("text/plain", task.id);
                }});
                card.addEventListener("dragend", () => {{
                    card.classList.remove("dragging");
                }});

                body.appendChild(card);
            }});
        }}

        body.addEventListener("dragover", (event) => {{
            event.preventDefault();
            body.classList.add("drag-over");
        }});
        body.addEventListener("dragleave", () => {{
            body.classList.remove("drag-over");
        }});
        body.addEventListener("drop", (event) => {{
            event.preventDefault();
            body.classList.remove("drag-over");
            const targetStatus = body.dataset.status;
            if (!dragId || !targetStatus || dragFrom === targetStatus) {{
                dragId = null;
                dragFrom = null;
                return;
            }}
            const targetTask = tasks.find((item) => item.id === dragId);
            if (targetTask) {{
                targetTask.status = targetStatus;
            }}
            const payload = {{
                task_id: dragId,
                from: dragFrom,
                status: targetStatus,
                ts: Date.now()
            }};
            dragId = null;
            dragFrom = null;
            buildBoard();
            sendMove(payload);
        }});

        col.appendChild(header);
        col.appendChild(body);
        board.appendChild(col);
    }});
}}

buildBoard();
</script>
</body>
</html>
"""

move_event = components.html(board_html, height=board_height, scrolling=False)
if move_event:
    try:
        move_data = move_event if isinstance(move_event, dict) else json.loads(move_event)
    except Exception:
        move_data = None
    if move_data:
        event_id = str(move_data.get("ts", "")) + str(move_data.get("task_id", ""))
        if st.session_state.get("collab_last_move") != event_id:
            st.session_state.collab_last_move = event_id
            task_id = move_data.get("task_id")
            new_status = move_data.get("status")
            if task_id and new_status:
                task_store.update_task(
                    task_id=task_id,
                    status=new_status,
                    updated_by=member_name,
                )
                st.toast("과업 상태가 업데이트되었습니다.")
                st.rerun()

with st.expander("과업 상세 편집", expanded=False):
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
