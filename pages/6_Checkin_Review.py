"""
Check-in Review Page (Supabase-backed summaries)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import streamlit as st

from shared.auth import check_authentication, get_user_id, get_user_email, get_user_api_key
from shared.config import initialize_session_state, inject_custom_css
from shared.team_tasks import TeamTaskStore, STATUS_LABELS, format_remaining_kst, normalize_status

# 발굴 분석 임포트
try:
    from agent.discovery_agent import run_discovery_analysis
    DISCOVERY_AVAILABLE = True
except ImportError:
    DISCOVERY_AVAILABLE = False

# Supabase 피드백 임포트
try:
    from agent.supabase_storage import SupabaseStorage
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# 체크인 에이전트 임포트
try:
    from agent.checkin_agent import CheckinAgent, run_feedback_analysis
    CHECKIN_AGENT_AVAILABLE = True
except ImportError:
    CHECKIN_AGENT_AVAILABLE = False

PROJECT_ROOT = Path(__file__).parent.parent
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
    page_title="체크인 기록 | 메리",
    page_icon="image-removebg-preview-5.png",
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

# ========================================
# 스타트업 발굴 추천 (있으면 표시)
# ========================================
if st.session_state.get("discovery_recommendations"):
    recs = st.session_state.discovery_recommendations.get("recommendations", [])
    if recs:
        st.markdown("---")
        st.markdown("## 유망 스타트업 영역 추천")
        st.caption("정책 분석 기반 발굴 추천 결과입니다.")

        # 상위 3개 추천만 표시
        for i, rec in enumerate(recs[:3], 1):
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{i}. {rec.get('industry', 'N/A')}**")
                    if rec.get("rationale"):
                        st.caption(rec.get("rationale")[:150] + "..." if len(rec.get("rationale", "")) > 150 else rec.get("rationale"))
                with col2:
                    st.metric("점수", f"{rec.get('total_score', 0):.1f}")

        # 자세히 보기 링크
        st.page_link("pages/8_Startup_Discovery.py", label="자세히 보기 →", icon="🔍")
        st.markdown("---")

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

# ========================================
# 분석 피드백 리뷰 (Supabase에서 가져옴)
# ========================================
if SUPABASE_AVAILABLE:
    feedback_storage = SupabaseStorage(user_id=user_id)
    recent_feedbacks = feedback_storage.get_recent_feedback(limit=20)

    if recent_feedbacks:
        st.markdown("## 분석 피드백 리뷰")
        st.caption("심사보고서, 피어분석, 엑싯 등에서 남긴 피드백을 확인합니다.")

        # 피드백 통계 표시
        stats = feedback_storage.get_feedback_stats()
        col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 2])
        with col1:
            st.metric("전체 피드백", stats.get("total", 0))
        with col2:
            st.metric("긍정", stats.get("positive", 0), delta=None)
        with col3:
            st.metric("개선 필요", stats.get("negative", 0), delta=None)
        with col4:
            rate = stats.get("satisfaction_rate", 0) * 100
            st.metric("만족도", f"{rate:.0f}%")
        with col5:
            # AI 브리핑 생성 버튼
            if CHECKIN_AGENT_AVAILABLE:
                if st.button("AI 브리핑 생성", type="primary", use_container_width=True):
                    with st.spinner("피드백 분석 중..."):
                        api_key = get_user_api_key()
                        result = run_feedback_analysis(recent_feedbacks, stats, api_key)
                        if result.get("success"):
                            st.session_state["checkin_briefing"] = result.get("analysis")
                        else:
                            st.error(f"분석 실패: {result.get('error')}")

        # AI 브리핑 결과 표시
        if st.session_state.get("checkin_briefing"):
            st.markdown("### AI 브리핑")
            with st.container(border=True):
                st.markdown(st.session_state["checkin_briefing"])
            if st.button("브리핑 닫기"):
                del st.session_state["checkin_briefing"]
                st.rerun()

        st.markdown("### 최근 피드백")

        # 피드백 타입별 아이콘
        feedback_icons = {
            "thumbs_up": "👍",
            "thumbs_down": "👎",
            "text_feedback": "💬",
            "correction": "✏️",
            "rating": "⭐"
        }

        for fb in recent_feedbacks[:10]:
            fb_type = fb.get("feedback_type", "text_feedback")
            icon = feedback_icons.get(fb_type, "📝")
            created_at = fb.get("created_at", "")[:10] if fb.get("created_at") else ""

            # 컨텍스트에서 페이지 정보 추출
            context = fb.get("context", {})
            page_name = context.get("page", context.get("source", "알 수 없음"))

            with st.container(border=True):
                # 헤더: 피드백 타입 + 페이지 + 날짜
                header_col1, header_col2 = st.columns([3, 1])
                with header_col1:
                    st.markdown(f"{icon} **{fb_type.replace('_', ' ').title()}** · {page_name}")
                with header_col2:
                    st.caption(created_at)

                # 사용자 질문 (요약)
                user_msg = fb.get("user_message", "")
                if user_msg:
                    if len(user_msg) > 100:
                        st.caption(f"질문: {user_msg[:100]}...")
                    else:
                        st.caption(f"질문: {user_msg}")

                # 피드백 값 (텍스트 피드백인 경우)
                fb_value = fb.get("feedback_value")
                if fb_value and isinstance(fb_value, str):
                    st.info(fb_value)
                elif fb_value and isinstance(fb_value, dict):
                    if fb_value.get("comment"):
                        st.info(fb_value.get("comment"))

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
