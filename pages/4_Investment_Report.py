"""
투자심사 보고서 작성 페이지
- 기업 자료에서 시장규모 근거 추출
- 인수인의견 스타일 초안 작성
"""

import asyncio
import pandas as pd

import streamlit as st

from shared.deep_opinion import build_evidence_context, generate_deep_investment_opinion
from shared.auth import check_authentication
from shared.config import (
    get_avatar_image,
    get_user_avatar_image,
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
user_avatar_image = get_user_avatar_image()
render_sidebar(mode="report")


def _sync_report_evidence_from_memory():
    agent = st.session_state.get("agent")
    if not agent or not hasattr(agent, "memory"):
        return
    messages = agent.memory.session_metadata.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") != "tool":
            continue
        meta = msg.get("metadata") or {}
        if meta.get("tool_name") != "extract_pdf_market_evidence":
            continue
        result = meta.get("result")
        if isinstance(result, dict):
            st.session_state.report_evidence = result if result.get("success") else None
        break


_sync_report_evidence_from_memory()

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

# 요약 영역
evidence = st.session_state.get("report_evidence")
if evidence:
    st.markdown("### 시장규모 근거 요약")
    if evidence.get("cache_hit"):
        st.caption("캐시 사용: 최근 분석 결과를 재사용했습니다.")
    warnings = evidence.get("warnings") or []
    if warnings:
        st.warning("검증/주의 사항")
        for warning in warnings:
            st.markdown(f"- {warning}")

    rows = []
    for item in evidence.get("evidence", [])[:8]:
        rows.append({
            "페이지": item.get("page"),
            "근거": item.get("text"),
            "숫자": ", ".join(item.get("numbers", [])),
        })
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.caption("표시할 근거가 없습니다.")

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

# ========================================
# 심화 투자 의견 (Opus)
# ========================================
st.markdown("## 심화 투자 의견 (Opus)")
st.caption("근거 기반 다중 관점 검토 + 할루시네이션 검증 + 임팩트(탄소/IRIS+) 분석")

deep_cols = st.columns([1.2, 1.2, 1])
with deep_cols[0]:
    if st.button("심화 의견 생성", type="primary", use_container_width=True, key="report_deep_generate"):
        st.session_state.report_deep_error = None
        st.session_state.report_deep_step = 0

        evidence_context = build_evidence_context(st.session_state.get("report_evidence"))
        last_user_msgs = [
            msg.get("content", "")
            for msg in st.session_state.report_messages
            if msg.get("role") == "user"
        ]
        extra_context = "최근 사용자 요청:\n" + "\n".join(last_user_msgs[-3:]) if last_user_msgs else ""

        with st.spinner("Opus로 심화 의견 생성 중..."):
            try:
                api_key = st.session_state.get("user_api_key", "")
                result = generate_deep_investment_opinion(
                    api_key=api_key,
                    evidence_context=evidence_context,
                    extra_context=extra_context,
                )
                st.session_state.report_deep_analysis = result
            except Exception as exc:
                st.session_state.report_deep_error = str(exc)
                st.session_state.report_deep_analysis = None

with deep_cols[1]:
    if st.button("처음부터 다시", use_container_width=True, key="report_deep_reset"):
        st.session_state.report_deep_step = 0

with deep_cols[2]:
    if st.button("초기화", use_container_width=True, key="report_deep_clear"):
        st.session_state.report_deep_analysis = None
        st.session_state.report_deep_step = 0
        st.session_state.report_deep_error = None

if st.session_state.report_deep_error:
    st.error(f"심화 의견 생성 실패: {st.session_state.report_deep_error}")

deep_analysis = st.session_state.get("report_deep_analysis")
if deep_analysis:
    steps = [
        ("결론", "conclusion"),
        ("Core Case", "core_case"),
        ("Dissent Case", "dissent_case"),
        ("Top Risks", "top_risks"),
        ("Hallucination Check", "hallucination_check"),
        ("Impact Analysis", "impact_analysis"),
        ("데이터 공백", "data_gaps"),
        ("딜 브레이커/GO 조건", "deal_breakers"),
        ("다음 액션", "next_actions"),
    ]
    current_step = st.session_state.get("report_deep_step", 0)
    current_step = max(0, min(current_step, len(steps) - 1))
    st.session_state.report_deep_step = current_step

    st.progress((current_step + 1) / len(steps))
    step_title, step_key = steps[current_step]
    st.markdown(f"### {step_title}")

    if step_key == "conclusion":
        paragraphs = deep_analysis.get("conclusion", {}).get("paragraphs", [])
        for paragraph in paragraphs:
            st.markdown(paragraph)
    elif step_key in ("core_case", "dissent_case"):
        section = deep_analysis.get(step_key, {})
        summary = section.get("summary")
        if summary:
            st.markdown(summary)
        points = section.get("points", [])
        for item in points:
            point = item.get("point", "")
            evidence = ", ".join(item.get("evidence", []) or [])
            suffix = f" (근거: {evidence})" if evidence else " (근거: 없음)"
            st.markdown(f"- {point}{suffix}")
    elif step_key == "top_risks":
        for risk in deep_analysis.get("top_risks", []):
            evidence = ", ".join(risk.get("evidence", []) or [])
            severity = risk.get("severity", "medium")
            verification = risk.get("verification", "")
            label = f"[{severity}] {risk.get('risk', '')}"
            suffix = f" · 검증: {verification}" if verification else ""
            if evidence:
                suffix += f" · 근거: {evidence}"
            st.markdown(f"- {label}{suffix}")
    elif step_key == "hallucination_check":
        hc = deep_analysis.get("hallucination_check", {})
        st.markdown("**미검증 주장**")
        for item in hc.get("unverified_claims", []):
            st.markdown(f"- {item.get('claim', '')} (사유: {item.get('reason', '')})")
        st.markdown("**수치 충돌**")
        for item in hc.get("numeric_conflicts", []):
            st.markdown(f"- {item}")
        st.markdown("**근거 공백**")
        for item in hc.get("evidence_gaps", []):
            st.markdown(f"- {item}")
    elif step_key == "impact_analysis":
        impact = deep_analysis.get("impact_analysis", {})
        carbon = impact.get("carbon", {})
        st.markdown("**탄소 분석**")
        pathways = ", ".join(carbon.get("pathways", []) or [])
        if pathways:
            st.markdown(f"- 경로: {pathways}")
        for metric in carbon.get("metrics", []):
            evidence = ", ".join(metric.get("evidence", []) or [])
            suffix = f" (근거: {evidence})" if evidence else ""
            st.markdown(f"- {metric.get('metric', '')}: {metric.get('method', '')}{suffix}")
        for gap in carbon.get("gaps", []):
            st.markdown(f"- 공백: {gap}")
        st.markdown("**IRIS+ 매핑**")
        for item in impact.get("iris_plus", []):
            evidence = ", ".join(item.get("evidence", []) or [])
            suffix = f" (근거: {evidence})" if evidence else ""
            st.markdown(
                f"- {item.get('code', 'IRIS+')}: {item.get('name', '')} · {item.get('why', '')} "
                f"· {item.get('measurement', '')}{suffix}"
            )
    elif step_key == "data_gaps":
        for item in deep_analysis.get("data_gaps", []):
            st.markdown(f"- {item}")
    elif step_key == "deal_breakers":
        st.markdown("**딜 브레이커**")
        for item in deep_analysis.get("deal_breakers", []):
            st.markdown(f"- {item}")
        st.markdown("**GO 조건**")
        for item in deep_analysis.get("go_conditions", []):
            st.markdown(f"- {item}")
    elif step_key == "next_actions":
        for item in deep_analysis.get("next_actions", []):
            st.markdown(f"- {item.get('priority', 'P1')}: {item.get('action', '')}")

    nav_cols = st.columns([1, 1, 2])
    with nav_cols[0]:
        if st.button("이전", disabled=current_step == 0, use_container_width=True, key="report_deep_prev"):
            st.session_state.report_deep_step = current_step - 1
            st.rerun()
    with nav_cols[1]:
        if st.button("다음", disabled=current_step >= len(steps) - 1, use_container_width=True, key="report_deep_next"):
            st.session_state.report_deep_step = current_step + 1
            st.rerun()
    with nav_cols[2]:
        if st.button("전체 펼치기", use_container_width=True, key="report_deep_expand"):
            st.session_state.report_deep_step = len(steps) - 1
            st.rerun()

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
                with st.chat_message("user", avatar=user_avatar_image):
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
