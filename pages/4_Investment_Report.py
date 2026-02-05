"""
투자심사 보고서 작성 페이지
- 기업 자료에서 시장규모 근거 추출
- 인수인의견 스타일 초안 작성
"""

import asyncio
import os
import re
import pandas as pd
from pathlib import Path

import streamlit as st

from agent.tools import _resolve_underwriter_data_path, execute_fetch_underwriter_opinion_data
from shared.deep_opinion import (
    build_evidence_context,
    cross_examine_and_score,
    generate_hallucination_check,
    generate_impact_analysis,
    generate_lens_group,
    synthesize_deep_opinion,
)
from shared.model_opinions import gather_model_opinions
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
from shared.team_tasks import TeamTaskStore, STATUS_LABELS, format_remaining_kst, normalize_status


st.set_page_config(
    page_title="투자심사 보고서 | 메리",
    page_icon="image-removebg-preview-5.png",
    layout="wide",
)

initialize_session_state()
check_authentication()
initialize_agent()
inject_custom_css()

avatar_image = get_avatar_image()
user_avatar_image = get_user_avatar_image()
render_sidebar(mode="report")


def _append_deep_log(logs, message, status_container=None):
    logs.append(message)
    if status_container is not None:
        status_container.write(message)


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


def _run_deep_opinion_generation(auto_run: bool = False) -> None:
    st.session_state.report_deep_error = None
    st.session_state.report_deep_step = 0
    st.session_state.report_deep_analysis = None
    st.session_state.report_deep_lens = None
    st.session_state.report_deep_scoring = None
    st.session_state.report_deep_hallucination = None
    st.session_state.report_deep_impact = None
    st.session_state.report_deep_logs = []

    evidence_context = build_evidence_context(st.session_state.get("report_evidence"))
    last_user_msgs = [
        msg.get("content", "")
        for msg in st.session_state.report_messages
        if msg.get("role") == "user"
    ]
    extra_context = "최근 사용자 요청:\n" + "\n".join(last_user_msgs[-3:]) if last_user_msgs else ""

    logs: list[str] = []
    progress = st.progress(0.0)
    status = st.status("Opus 심화 의견 생성 중...", expanded=not auto_run)
    try:
        api_key = st.session_state.get("user_api_key", "")
        if not api_key:
            raise ValueError("API 키를 입력해 주세요.")

        _append_deep_log(logs, "1/5 다중 관점 생성 시작", status)
        lens_outputs = generate_lens_group(
            api_key=api_key,
            evidence_context=evidence_context,
            extra_context=extra_context,
        )
        st.session_state.report_deep_lens = lens_outputs
        progress.progress(0.2)
        _append_deep_log(logs, "1/5 다중 관점 생성 완료", status)

        _append_deep_log(logs, "2/5 교차 검토 및 점수화 시작", status)
        scoring = cross_examine_and_score(
            api_key=api_key,
            evidence_context=evidence_context,
            lens_outputs=lens_outputs,
        )
        st.session_state.report_deep_scoring = scoring
        progress.progress(0.4)
        _append_deep_log(logs, "2/5 교차 검토 및 점수화 완료", status)

        _append_deep_log(logs, "3/5 할루시네이션 검증 시작", status)
        hallucination = generate_hallucination_check(
            api_key=api_key,
            evidence_context=evidence_context,
            lens_outputs=lens_outputs,
        )
        st.session_state.report_deep_hallucination = hallucination
        progress.progress(0.6)
        _append_deep_log(logs, "3/5 할루시네이션 검증 완료", status)

        _append_deep_log(logs, "4/5 임팩트 분석 시작", status)
        impact = generate_impact_analysis(
            api_key=api_key,
            evidence_context=evidence_context,
            lens_outputs=lens_outputs,
        )
        st.session_state.report_deep_impact = impact
        progress.progress(0.8)
        _append_deep_log(logs, "4/5 임팩트 분석 완료", status)

        _append_deep_log(logs, "5/5 최종 종합 시작", status)
        final_result = synthesize_deep_opinion(
            api_key=api_key,
            evidence_context=evidence_context,
            lens_outputs=lens_outputs,
            scoring=scoring,
            hallucination=hallucination,
            impact=impact,
        )

        if st.session_state.get("report_deep_multi"):
            _append_deep_log(logs, "5/5 멀티모델 의견 수집 시작", status)
            model_opinions = gather_model_opinions(
                user_message=last_user_msgs[-1] if last_user_msgs else "투자심사 보고서 심화 의견 생성",
                evidence=evidence_context,
                claude_api_key=api_key,
            )
            final_result["model_opinions"] = model_opinions
            _append_deep_log(logs, "5/5 멀티모델 의견 수집 완료", status)

        st.session_state.report_deep_analysis = final_result
        progress.progress(1.0)
        _append_deep_log(logs, "5/5 최종 종합 완료", status)
        status.update(label="심화 의견 생성 완료", state="complete", expanded=False)
    except Exception as exc:
        st.session_state.report_deep_error = str(exc)
        st.session_state.report_deep_analysis = None
        status.update(label="심화 의견 생성 실패", state="error", expanded=True)
    finally:
        st.session_state.report_deep_logs = logs

st.markdown("# 투자심사 보고서 작성")
st.markdown("시장규모 근거를 추출하고 인수인의견 스타일 초안을 작성합니다")
st.divider()

with st.expander("현재 보고서 목차", expanded=False):
    outline = st.session_state.get("report_outline") or []
    if outline:
        for item in outline:
            st.markdown(f"- {item}")
    else:
        st.caption("목차 정보가 없습니다.")

# 팀 과업 요약
team_id = st.session_state.get("team_id") or st.session_state.get("user_id")
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

# 업로드 영역
st.markdown("### 기업 자료 업로드")
upload_cols = st.columns([2, 1])

def _guess_doc_type(filename: str) -> str:
    lower = filename.lower()
    if "ir" in lower or "investor" in lower:
        return "IR"
    if "요약" in filename or "summary" in lower or "보고서" in filename:
        return "요약보고서"
    if "사업자" in filename or "등록증" in filename:
        return "사업자등록증"
    return "기타"


def _build_report_context_text() -> str:
    assets = st.session_state.get("report_files") or []
    if not assets:
        return ""

    weights = st.session_state.get("report_doc_weights", {})
    analyzable_exts = {".pdf", ".xlsx", ".xls", ".docx"}
    lines = ["업로드 자료 목록 및 가중치:"]
    for asset in assets:
        name = asset.get("name", "")
        doc_type = asset.get("doc_type") or _guess_doc_type(name)
        weight = weights.get(doc_type, weights.get("기타", 0.0))
        path = asset.get("path", "")
        ext = Path(name).suffix.lower()
        if ext in analyzable_exts:
            status = "분석 대상"
            path_text = path
        else:
            status = "참고용(자동 분석 미지원)"
            path_text = "경로 제공 안함"
        lines.append(f"- {name} | {doc_type} | weight {weight:.2f} | {status} | path: {path_text}")
    lines.append("가중치는 문서 신뢰도/중요도를 의미하며, 보고서 작성 시 반영하세요.")
    return "\n".join(lines)


def _init_report_chapters() -> list:
    outline = st.session_state.get("report_outline") or []
    chapter_order = [item for item in outline if re.match(r'^[IVX]+\\.', item)]
    if not chapter_order:
        chapter_order = [
            "I. 투자 개요",
            "II. 기업 현황",
            "III. 시장 분석",
            "IV. 사업 분석",
            "V. 투자 적합성 및 임팩트",
            "VI. 수익성/Valuation",
            "VII. 임팩트 리스크",
            "VIII. 종합 결론",
        ]
    if not st.session_state.get("report_chapter_order"):
        st.session_state.report_chapter_order = chapter_order
    return st.session_state.report_chapter_order


def _compose_full_draft(chapters: dict, order: list) -> str:
    blocks = []
    for key in order:
        content = (chapters or {}).get(key)
        if content:
            blocks.append(content.strip())
    return "\n\n".join(blocks).strip()


def _save_current_chapter(mark_done: bool = False) -> None:
    chapter_order = st.session_state.get("report_chapter_order") or []
    idx = st.session_state.get("report_chapter_index", 0)
    if not chapter_order:
        return
    idx = max(0, min(idx, len(chapter_order) - 1))
    current = chapter_order[idx]
    current_text = st.session_state.get("report_edit_buffer", "").strip()
    if current_text:
        st.session_state.report_chapters[current] = current_text
    if mark_done:
        st.session_state.report_chapter_status[current] = "done"
    else:
        st.session_state.report_chapter_status.setdefault(current, "draft")
    st.session_state.report_draft_content = _compose_full_draft(
        st.session_state.report_chapters,
        chapter_order,
    )

with upload_cols[0]:
    report_files = st.file_uploader(
        "기업 자료 (PDF/Word/이미지/엑셀) - 다중 업로드 가능",
        type=["pdf", "docx", "doc", "png", "jpg", "jpeg", "xlsx", "xls", "pptx"],
        key="report_file_uploader",
        accept_multiple_files=True,
        help="시장규모 근거가 포함된 기업 자료를 업로드하세요",
    )
    st.caption("PDF/엑셀/DOCX는 자동 분석 대상입니다. 이미지/PPTX/DOC는 참고용으로 저장됩니다.")

with upload_cols[1]:
    if report_files:
        allowed = ALLOWED_EXTENSIONS_EXCEL + ALLOWED_EXTENSIONS_PDF + [
            ".docx", ".doc", ".png", ".jpg", ".jpeg", ".pptx"
        ]
        selected_names = [f.name for f in report_files]
        if selected_names != st.session_state.get("report_uploaded_names", []):
            uploaded_assets = []
            for report_file in report_files:
                is_valid, error = validate_upload(
                    filename=report_file.name,
                    file_size=report_file.size,
                    allowed_extensions=allowed,
                )
                if not is_valid:
                    st.error(f"{report_file.name}: {error}")
                    continue

                user_id = st.session_state.get("user_id", "anonymous")
                secure_path = get_secure_upload_path(user_id=user_id, original_filename=report_file.name)
                with open(secure_path, "wb") as f:
                    f.write(report_file.getbuffer())

                cleanup_user_temp_files(user_id, max_files=20)
                uploaded_assets.append({
                    "name": report_file.name,
                    "path": str(secure_path),
                })

            if uploaded_assets:
                st.session_state.report_files = uploaded_assets
                st.session_state.report_uploaded_names = selected_names
                st.success(f"{len(uploaded_assets)}개 파일 업로드 완료")

if st.session_state.get("report_files"):
    st.markdown("#### 자료 유형 지정")
    type_options = ["IR", "요약보고서", "사업자등록증", "기타"]
    doc_type_map = st.session_state.get("report_file_types", {})
    updated_assets = []
    for idx, asset in enumerate(st.session_state.report_files):
        guess = _guess_doc_type(asset["name"])
        current = doc_type_map.get(asset["name"], guess)
        label = f"{asset['name']} ({guess})"
        doc_type = st.selectbox(
            label,
            options=type_options,
            index=type_options.index(current) if current in type_options else 0,
            key=f"report_doc_type_{idx}",
        )
        doc_type_map[asset["name"]] = doc_type
        updated_assets.append({**asset, "doc_type": doc_type})
    st.session_state.report_file_types = doc_type_map
    st.session_state.report_files = updated_assets

    primary = next((a for a in updated_assets if a.get("doc_type") == "IR"), updated_assets[0])
    st.session_state.report_file_path = primary["path"]
    st.session_state.report_file_name = primary["name"]

    st.markdown("#### 자료 가중치 (합계 1.0 고정)")
    weights = st.session_state.get("report_doc_weights", {})
    w_ir = st.slider("IR", min_value=0.0, max_value=1.0, value=weights.get("IR", 0.4), step=0.05, key="weight_ir")
    max_summary = max(0.0, 1.0 - w_ir)
    w_summary = st.slider(
        "요약보고서",
        min_value=0.0,
        max_value=max_summary,
        value=min(weights.get("요약보고서", 0.3), max_summary),
        step=0.05,
        key="weight_summary",
    )
    max_reg = max(0.0, 1.0 - w_ir - w_summary)
    w_reg = st.slider(
        "사업자등록증",
        min_value=0.0,
        max_value=max_reg,
        value=min(weights.get("사업자등록증", 0.2), max_reg),
        step=0.05,
        key="weight_reg",
    )
    w_other = max(0.0, 1.0 - w_ir - w_summary - w_reg)
    st.metric("기타", f"{w_other:.2f}")
    st.caption("합계는 자동으로 1.0으로 고정됩니다. (기타는 자동 조정)")
    st.session_state.report_doc_weights = {
        "IR": round(w_ir, 2),
        "요약보고서": round(w_summary, 2),
        "사업자등록증": round(w_reg, 2),
        "기타": round(w_other, 2),
    }

st.divider()

# DART 인수인의견 데이터 설정
st.markdown("### DART 인수인의견 데이터")
dart_cols = st.columns([2, 1])
with dart_cols[0]:
    dart_api_key = st.text_input(
        "DART API Key",
        type="password",
        placeholder="DART API 키를 입력하세요",
        value=st.session_state.get("dart_api_key", ""),
    )
    if dart_api_key:
        st.session_state.dart_api_key = dart_api_key
        os.environ["DART_API_KEY"] = dart_api_key

    data_path, data_error = _resolve_underwriter_data_path(None)
    if data_error:
        st.warning("DART 인수인의견 데이터셋을 찾을 수 없습니다.")
        st.caption(data_error)
    else:
        st.success("DART 인수인의견 데이터셋이 준비되어 있습니다.")
        st.caption(f"경로: {data_path}")

with dart_cols[1]:
    if st.button("DART 데이터 수집", use_container_width=True, key="report_dart_fetch"):
        if not dart_api_key:
            st.error("DART API 키를 입력해 주세요.")
        else:
            with st.spinner("DART 데이터를 수집하는 중..."):
                result = execute_fetch_underwriter_opinion_data(api_key=dart_api_key)
            if result.get("success"):
                st.success(f"수집 완료: {result.get('output_file')}")
            else:
                st.error(f"수집 실패: {result.get('error')}")

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

auto_cols = st.columns([1, 1, 2])
with auto_cols[0]:
    st.toggle(
        "심화 의견 자동 생성",
        value=st.session_state.get("report_deep_autorun", True),
        key="report_deep_autorun",
    )
with auto_cols[1]:
    multi_state = "ON" if st.session_state.get("report_deep_multi") else "OFF"
    st.caption(f"멀티모델 의견: {multi_state}")
with auto_cols[2]:
    st.caption("보고서 화면 진입 시 자동으로 심화 의견을 생성합니다.")

deep_cols = st.columns([1.2, 1.2, 1])
with deep_cols[0]:
    if st.button("심화 의견 생성", type="primary", use_container_width=True, key="report_deep_generate"):
        _run_deep_opinion_generation(auto_run=False)

with deep_cols[1]:
    if st.button("처음부터 다시", use_container_width=True, key="report_deep_reset"):
        st.session_state.report_deep_step = 0

with deep_cols[2]:
    if st.button("초기화", use_container_width=True, key="report_deep_clear"):
        st.session_state.report_deep_analysis = None
        st.session_state.report_deep_lens = None
        st.session_state.report_deep_scoring = None
        st.session_state.report_deep_hallucination = None
        st.session_state.report_deep_impact = None
        st.session_state.report_deep_step = 0
        st.session_state.report_deep_error = None
        st.session_state.report_deep_logs = []

should_autorun = (
    st.session_state.get("report_deep_mode")
    and st.session_state.get("report_deep_autorun")
    and not st.session_state.get("report_deep_analysis")
    and not st.session_state.get("report_deep_error")
    and not st.session_state.get("report_deep_autorun_done")
    and (st.session_state.get("report_file_path") or st.session_state.get("report_evidence"))
)
if should_autorun:
    st.session_state.report_deep_autorun_done = True
    _run_deep_opinion_generation(auto_run=True)

if st.session_state.report_deep_error:
    st.error(f"심화 의견 생성 실패: {st.session_state.report_deep_error}")

deep_logs = st.session_state.get("report_deep_logs") or []
if deep_logs:
    with st.expander("심화 의견 생성 로그", expanded=False):
        for line in deep_logs:
            st.caption(line)

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
    if deep_analysis.get("model_opinions"):
        insert_at = 6
        steps.insert(insert_at, ("모델 다중 의견", "model_opinions"))
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
    elif step_key == "model_opinions":
        opinions = deep_analysis.get("model_opinions", [])
        if not opinions:
            st.caption("모델 의견이 없습니다.")
        else:
            for opinion in opinions:
                provider = opinion.get("provider", "model").upper()
                model_name = opinion.get("model", "")
                label = f"{provider} ({model_name})" if model_name else provider
                if opinion.get("success"):
                    content = (opinion.get("content") or "").strip()
                    st.markdown(f"**{label}**")
                    st.markdown(content if content else "응답 내용 없음")
                else:
                    error = opinion.get("error", "실패")
                    st.markdown(f"**{label}**")
                    st.caption(f"실패: {error}")
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

# 채팅/초안 레이아웃
chat_area = None
draft_placeholder = None
chat_col, draft_col = st.columns([1, 1], gap="large")

chapter_order = _init_report_chapters()
if chapter_order:
    st.session_state.report_chapter_index = max(
        0,
        min(st.session_state.get("report_chapter_index", 0), len(chapter_order) - 1),
    )
    current_chapter = chapter_order[st.session_state.report_chapter_index]
else:
    current_chapter = None

with chat_col:
    st.markdown("## 대화")
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
1. 상단에 **기업 자료(PDF/엑셀/DOCX)**를 업로드하세요
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

with draft_col:
    st.markdown("## 챕터 작성")
    draft_container = st.container(border=True, height=550)
    with draft_container:
        if chapter_order:
            total = len(chapter_order)
            idx = st.session_state.get("report_chapter_index", 0)
            idx = max(0, min(idx, total - 1))
            current_chapter = chapter_order[idx]
            status = st.session_state.get("report_chapter_status", {}).get(current_chapter, "draft")
            st.caption(f"현재 챕터: {current_chapter} · 상태: {status} · {idx+1}/{total}")
            st.progress((idx + 1) / total)

            draft_placeholder = st.empty()
            existing = st.session_state.get("report_chapters", {}).get(current_chapter, "")
            if existing and not st.session_state.get("report_edit_buffer"):
                st.session_state.report_edit_buffer = existing
            if not existing:
                draft_placeholder.markdown("초안이 생성되면 여기에 표시됩니다.")

            st.text_area(
                "편집",
                key="report_edit_buffer",
                height=260,
                placeholder="챕터 내용을 편집하세요.",
            )

            btn_cols = st.columns(3)
            with btn_cols[0]:
                if st.button("이전", use_container_width=True, disabled=idx == 0):
                    _save_current_chapter(mark_done=False)
                    st.session_state.report_chapter_index = max(0, idx - 1)
                    st.session_state.report_edit_buffer = st.session_state.report_chapters.get(
                        chapter_order[st.session_state.report_chapter_index], ""
                    )
                    st.rerun()
            with btn_cols[1]:
                if st.button("완료", use_container_width=True):
                    _save_current_chapter(mark_done=True)
                    if idx < total - 1:
                        st.session_state.report_chapter_index = idx + 1
                        st.session_state.report_edit_buffer = st.session_state.report_chapters.get(
                            chapter_order[idx + 1], ""
                        )
                    st.rerun()
            with btn_cols[2]:
                if st.button("다음", use_container_width=True, disabled=idx >= total - 1):
                    _save_current_chapter(mark_done=False)
                    st.session_state.report_chapter_index = min(total - 1, idx + 1)
                    st.session_state.report_edit_buffer = st.session_state.report_chapters.get(
                        chapter_order[st.session_state.report_chapter_index], ""
                    )
                    st.rerun()
        else:
            draft_placeholder = st.empty()
            draft_placeholder.markdown("목차가 설정되지 않았습니다.")


if st.session_state.get("report_quick_command"):
    user_input = st.session_state.report_quick_command
    st.session_state.report_quick_command = None


if user_input:
    report_context_text = _build_report_context_text()
    if chapter_order:
        idx = st.session_state.get("report_chapter_index", 0)
        idx = max(0, min(idx, len(chapter_order) - 1))
        current_chapter = chapter_order[idx]
        chapter_instruction = (
            f"현재 작성 챕터: {current_chapter}.\n"
            "이 챕터만 작성하고 다른 챕터는 출력하지 마세요.\n"
            "형식: ### 챕터 제목 → 요약/근거/심사 판단 포함.\n"
            "마지막에 ### 검증 로그(해당 챕터) 포함."
        )
        report_context_text = f"{report_context_text}\n\n{chapter_instruction}".strip()
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
        current_chapter = None
        if chapter_order:
            idx = st.session_state.get("report_chapter_index", 0)
            idx = max(0, min(idx, len(chapter_order) - 1))
            current_chapter = chapter_order[idx]

        async for chunk in st.session_state.agent.chat(
            user_input,
            mode="report",
            context_text=report_context_text,
            model_override="claude-opus-4-5-20251101",
        ):
            if "**도구:" in chunk:
                tool_messages.append(chunk.strip())
                with tool_container:
                    if tool_status is None:
                        tool_status = st.status("도구 실행 중...", expanded=True, state="running")
                    tool_status.write(chunk.strip())
            else:
                full_response += chunk
                response_placeholder.markdown(full_response + "▌")
                if draft_placeholder is not None:
                    draft_placeholder.markdown(full_response + "▌")

        response_placeholder.markdown(full_response)
        if draft_placeholder is not None:
            draft_placeholder.markdown(full_response)
        if tool_status is not None:
            final_state = "error" if any("실패" in m for m in tool_messages) else "complete"
            tool_status.update(label="도구 실행 완료", state=final_state, expanded=False)
        st.session_state.report_draft_content = full_response
        if current_chapter:
            st.session_state.report_chapters[current_chapter] = full_response
            st.session_state.report_edit_buffer = full_response
            st.session_state.report_chapter_status[current_chapter] = "draft"
            st.session_state.report_draft_content = _compose_full_draft(
                st.session_state.report_chapters,
                chapter_order,
            )
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
