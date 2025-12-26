"""
Check-in Review Page (Supabase-backed summaries)
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from shared.auth import check_authentication, get_user_id
from shared.config import initialize_session_state, inject_custom_css
from shared.team_tasks import TeamTaskStore, STATUS_LABELS, format_remaining_kst, normalize_status
try:
    from shared.voice_logs import (
        build_checkin_context_text,
        build_checkin_summary_text,
        get_checkin_context,
        get_checkin_summaries,
    )
    VOICE_LOGS_IMPORT_ERROR = None
except Exception as exc:
    VOICE_LOGS_IMPORT_ERROR = exc

    def _empty_context(*_args, **_kwargs):
        return {"start": "", "end": "", "voice_logs": [], "chat_messages": []}

    def _empty_text(*_args, **_kwargs):
        return ""

    def _empty_list(*_args, **_kwargs):
        return []

    build_checkin_context_text = _empty_text
    build_checkin_summary_text = _empty_text
    get_checkin_context = _empty_context
    get_checkin_summaries = _empty_list


st.set_page_config(
    page_title="체크인 기록 | VC 투자 분석",
    page_icon="VC",
    layout="wide",
)

initialize_session_state()
check_authentication()
inject_custom_css()

if VOICE_LOGS_IMPORT_ERROR:
    st.error(
        "voice_logs 로드 실패: "
        f"{type(VOICE_LOGS_IMPORT_ERROR).__name__}: {VOICE_LOGS_IMPORT_ERROR}"
    )
    st.caption("Streamlit Cloud 로그에서 상세 원인을 확인해주세요.")
    st.stop()

st.markdown("# 체크인 기록")
st.caption("Supabase에 저장된 체크인 요약과 원본 로그를 확인합니다.")

user_id = get_user_id()
team_id = st.session_state.get("team_id") or user_id
task_store = TeamTaskStore(team_id=team_id)
team_tasks = task_store.list_tasks(include_done=True, limit=12)

if team_tasks:
    st.markdown("## 팀 과업 요약")
    status_groups = {"todo": [], "in_progress": [], "done": []}
    for task in team_tasks:
        status_key = normalize_status(task.get("status", "todo"))
        status_groups.setdefault(status_key, []).append(task)

    cols = st.columns(3)
    for col, key in zip(cols, ["todo", "in_progress", "done"]):
        with col:
            st.markdown(f"### {STATUS_LABELS.get(key, key)}")
            tasks = status_groups.get(key, [])
            if not tasks:
                st.caption("비어 있음")
            else:
                for task in tasks[:4]:
                    title = task.get("title", "")
                    owner = task.get("owner") or "담당 미정"
                    due_date = task.get("due_date", "")
                    remaining = format_remaining_kst(due_date)
                    with st.container(border=True):
                        st.markdown(f"**{title}**")
                        st.caption(f"담당: {owner}")
                        if due_date:
                            if remaining:
                                st.caption(f"마감: {due_date} · {remaining}")
                            else:
                                st.caption(f"마감: {due_date}")
                        else:
                            st.caption("마감: 미설정")
    st.divider()
summaries = get_checkin_summaries(user_id, limit=30)

if not summaries:
    st.info("저장된 체크인 요약이 없습니다. 먼저 체크인을 진행하세요.")
    context = get_checkin_context(user_id, day_offset=1, limit=20)
    context_text = build_checkin_context_text(context, max_items=8)
    if context_text:
        st.markdown("### 어제 기록 (원본 로그)")
        st.write(context_text)
    st.stop()

summary_dates = []
for entry in summaries:
    if entry.get("summary_date"):
        summary_dates.append(entry.get("summary_date"))

summary_dates = sorted(set(summary_dates), reverse=True)
selected_date = st.selectbox("날짜 선택", options=summary_dates, index=0)

selected = next((s for s in summaries if s.get("summary_date") == selected_date), None)
if not selected:
    st.warning("선택된 날짜의 요약을 찾지 못했습니다.")
    st.stop()

summary_text = build_checkin_summary_text(selected)

st.markdown("### 체크인 요약")
if summary_text:
    st.write(summary_text)
else:
    st.write("요약 텍스트가 비어 있습니다.")

st.markdown("### 요약 JSON")
st.json(selected.get("summary_json") or {})

try:
    target_date = date.fromisoformat(selected_date)
    day_offset = max((date.today() - target_date).days, 0)
except ValueError:
    day_offset = 1

with st.expander("원본 로그 보기", expanded=False):
    context = get_checkin_context(user_id, day_offset=day_offset, limit=20)
    context_text = build_checkin_context_text(context, max_items=10)
    if context_text:
        st.write(context_text)
    else:
        st.caption("해당 날짜의 원본 로그가 없습니다.")
