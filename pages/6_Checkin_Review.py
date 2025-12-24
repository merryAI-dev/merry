"""
Check-in Review Page (Supabase-backed summaries)
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from shared.auth import check_authentication, get_user_id
from shared.config import initialize_session_state, inject_custom_css
from shared.voice_logs import (
    build_checkin_context_text,
    build_checkin_summary_text,
    get_checkin_context,
    get_checkin_summaries,
)


st.set_page_config(
    page_title="체크인 기록 | VC 투자 분석",
    page_icon="VC",
    layout="wide",
)

initialize_session_state()
check_authentication()
inject_custom_css()

st.markdown("# 체크인 기록")
st.caption("Supabase에 저장된 체크인 요약과 원본 로그를 확인합니다.")

user_id = get_user_id()
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
