"""
투자 계약서 리서치/검토 에이전트 (Term Sheet / 투자계약서)
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import streamlit as st

from shared.auth import check_authentication, get_user_api_key, get_user_id
from shared.config import initialize_session_state, inject_custom_css
from shared.file_utils import (
    ALLOWED_EXTENSIONS_PDF,
    cleanup_user_temp_files,
    get_secure_upload_path,
    validate_upload,
)
from shared.contract_review import (
    FIELD_DEFINITIONS,
    OCR_DEFAULT_MODEL,
    build_mask_replacements,
    compare_fields,
    detect_clauses,
    extract_fields,
    load_document,
    mask_analysis,
    mask_comparisons,
    mask_search_hits,
    search_segments,
)


st.set_page_config(
    page_title="계약서 리서치 | VC 투자 분석",
    page_icon="VC",
    layout="wide",
)

initialize_session_state()
check_authentication()
inject_custom_css()

st.markdown("# 계약서 리서치 에이전트")
st.caption("텀싯/투자계약서를 근거 기반으로 검토합니다. 법률 자문이 아니라 리서치 보조 도구입니다.")

st.warning("이 도구는 법률 자문이 아닙니다. 최종 판단은 반드시 법무 검토가 필요합니다.")

st.markdown("### 보안/마스킹")
masking_enabled = st.checkbox(
    "민감정보 마스킹 (기본 ON)",
    value=True,
    key="contract_masking",
    help="회사명/금액/연락처 등 민감정보를 토큰으로 치환해 표시합니다.",
)
st.info("업로드 → 로컬 파싱 → (필요 시 OCR) → 마스킹 → 규칙 기반 검토 → 화면 표시")

with st.expander("안심 플로우 자세히 보기"):
    st.markdown(
        """
        1. 파일 업로드 (임시 저장)
        2. PDF/DOCX 파싱
        3. (선택) 스캔본 OCR
        4. 민감정보 마스킹 (기본 ON)
        5. 규칙 기반 필드 추출 및 일치성 검토
        6. 결과 표시
        """
    )

st.markdown("### 스캔본 OCR (Claude)")
ocr_choice = st.selectbox(
    "OCR 사용 여부",
    ["자동(권장)", "강제", "끄기"],
    index=0,
    key="contract_ocr_mode",
    help="스캔본/깨진 텍스트가 있을 때 Claude OCR로 보정합니다.",
)
ocr_model = st.text_input(
    "OCR 모델",
    value=OCR_DEFAULT_MODEL,
    key="contract_ocr_model",
    help="Claude Opus 모델명을 입력하세요.",
)
st.caption("OCR 사용 시 페이지 이미지가 외부 API로 전송됩니다. 마스킹은 OCR 이후 표시 단계에서 적용됩니다.")

user_id = get_user_id()
user_api_key = get_user_api_key()
allowed_extensions = ALLOWED_EXTENSIONS_PDF + [".docx"]

if "contract_analysis" not in st.session_state:
    st.session_state.contract_analysis = {}



def _resolve_ocr_mode() -> str:
    mapping = {
        "자동(권장)": "auto",
        "강제": "force",
        "끄기": "off",
    }
    return mapping.get(ocr_choice, "auto")


def _save_upload(uploaded_file) -> Optional[Path]:
    if not uploaded_file:
        return None

    is_valid, error = validate_upload(
        filename=uploaded_file.name,
        file_size=uploaded_file.size,
        allowed_extensions=allowed_extensions,
    )
    if not is_valid:
        st.error(error)
        return None

    path = get_secure_upload_path(user_id=user_id, original_filename=uploaded_file.name)
    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    cleanup_user_temp_files(user_id, max_files=10)
    return path


col1, col2 = st.columns(2)

with col1:
    st.markdown("### 텀싯 업로드")
    term_sheet_file = st.file_uploader(
        "Term Sheet (PDF/DOCX)",
        type=["pdf", "docx"],
        key="term_sheet_file",
    )
    term_sheet_path = _save_upload(term_sheet_file) if term_sheet_file else None
    if term_sheet_path:
        st.session_state.contract_term_sheet_path = str(term_sheet_path)
        st.session_state.contract_term_sheet_name = term_sheet_file.name
        st.success(f"업로드 완료: {term_sheet_file.name}")

with col2:
    st.markdown("### 투자계약서 업로드")
    investment_file = st.file_uploader(
        "투자계약서 (PDF/DOCX)",
        type=["pdf", "docx"],
        key="investment_agreement_file",
    )
    investment_path = _save_upload(investment_file) if investment_file else None
    if investment_path:
        st.session_state.contract_investment_path = str(investment_path)
        st.session_state.contract_investment_name = investment_file.name
        st.success(f"업로드 완료: {investment_file.name}")

st.divider()

analyze_clicked = st.button("분석 실행", type="primary")


def _analyze_document(
    path_str: str,
    doc_type: str,
    doc_label: str,
    on_step=None,
    ocr_callback=None,
) -> Optional[Dict[str, object]]:
    if not path_str:
        return None

    path = Path(path_str)
    try:
        if on_step:
            on_step(f"{doc_label} 문서 파싱 중...")
        loaded = load_document(
            path,
            ocr_mode=_resolve_ocr_mode(),
            api_key=user_api_key,
            ocr_model=(ocr_model or OCR_DEFAULT_MODEL).strip(),
            progress_callback=ocr_callback,
        )
    except Exception as exc:
        st.error(f"문서 파싱 실패: {path.name} ({exc})")
        return None

    segments = loaded.get("segments", [])
    if on_step:
        on_step(f"{doc_label} 필드/조항 추출 중...")
    fields = extract_fields(segments)
    clauses = detect_clauses(segments, doc_type)

    return {
        "path": str(path),
        "name": path.name,
        "doc_type": doc_type,
        "segments": segments,
        "fields": fields,
        "clauses": clauses,
        "text_length": len(loaded.get("text", "")),
        "page_count": loaded.get("page_count", 0),
        "ocr_used": loaded.get("ocr_used", False),
        "ocr_error": loaded.get("ocr_error", ""),
    }


if analyze_clicked:
    term_sheet_path = st.session_state.get("contract_term_sheet_path")
    investment_path = st.session_state.get("contract_investment_path")

    status = st.status("분석 준비 중...", expanded=True)
    overall_progress = st.progress(0.0, text="분석 대기 중")
    ocr_progress_placeholder = st.empty()
    detail_placeholder = st.empty()

    total_steps = 0
    if term_sheet_path:
        total_steps += 2
    if investment_path:
        total_steps += 2
    if term_sheet_path and investment_path:
        total_steps += 1
    progress_state = {"done": 0}

    def _advance(label: str) -> None:
        progress_state["done"] += 1
        ratio = progress_state["done"] / total_steps if total_steps else 1.0
        overall_progress.progress(min(ratio, 1.0), text=label)
        detail_placeholder.markdown(f"현재 단계: {label}")
        status.update(label=label, state="running")

    def _make_ocr_callback(doc_label: str):
        def _callback(current: int, total: int, message: str) -> None:
            if total <= 0:
                return
            ratio = min(current / total, 1.0)
            ocr_progress_placeholder.progress(
                ratio,
                text=f"{doc_label} {message} ({current}/{total})",
            )

        return _callback

    st.session_state.contract_analysis = {}

    if term_sheet_path:
        doc = _analyze_document(
            term_sheet_path,
            "term_sheet",
            "텀싯",
            on_step=_advance,
            ocr_callback=_make_ocr_callback("텀싯"),
        )
        if doc:
            if doc.get("ocr_error"):
                ocr_progress_placeholder.progress(1.0, text=f"텀싯 OCR 실패: {doc.get('ocr_error')}")
            elif doc.get("ocr_used"):
                ocr_progress_placeholder.progress(1.0, text="텀싯 OCR 완료")
            else:
                ocr_progress_placeholder.progress(0.0, text="텀싯 OCR 미사용")
            st.session_state.contract_analysis["term_sheet"] = doc
    if investment_path:
        doc = _analyze_document(
            investment_path,
            "investment_agreement",
            "투자계약서",
            on_step=_advance,
            ocr_callback=_make_ocr_callback("투자계약서"),
        )
        if doc:
            if doc.get("ocr_error"):
                ocr_progress_placeholder.progress(1.0, text=f"투자계약서 OCR 실패: {doc.get('ocr_error')}")
            elif doc.get("ocr_used"):
                ocr_progress_placeholder.progress(1.0, text="투자계약서 OCR 완료")
            else:
                ocr_progress_placeholder.progress(0.0, text="투자계약서 OCR 미사용")
            st.session_state.contract_analysis["investment_agreement"] = doc

    if not st.session_state.contract_analysis:
        st.warning("먼저 문서를 업로드하세요.")
        status.update(label="문서 업로드 필요", state="error")
        overall_progress.progress(0.0, text="분석 중단")
    else:
        if term_sheet_path and investment_path:
            _advance("문서 간 일치 검토 준비...")
        status.update(label="분석 완료", state="complete")
        overall_progress.progress(1.0, text="분석 완료")
        st.toast("분석 완료")

analysis = st.session_state.contract_analysis

if analysis:
    replacements = {}
    if masking_enabled:
        field_sets = []
        for key in ["term_sheet", "investment_agreement"]:
            doc = analysis.get(key)
            if doc:
                field_sets.append(doc.get("fields", {}))
        replacements = build_mask_replacements(field_sets)

    if masking_enabled:
        st.caption("마스킹 ON: 회사명/금액/연락처 등 민감정보는 토큰으로 표시됩니다.")

    st.divider()
    st.markdown("## 문서 요약")

    for key in ["term_sheet", "investment_agreement"]:
        doc = analysis.get(key)
        if not doc:
            continue

        title = "텀싯" if key == "term_sheet" else "투자계약서"
        display_doc = mask_analysis(doc, replacements) if masking_enabled else doc
        st.markdown(f"### {title}")
        ocr_status = "OCR: 사용됨" if doc.get("ocr_used") else "OCR: 미사용"
        if doc.get("ocr_error"):
            ocr_status = "OCR: 실패"
        st.caption(
            f"파일: {doc.get('name')} · 길이: {doc.get('text_length', 0):,} chars · 세그먼트: {len(doc.get('segments', []))} · {ocr_status}"
        )
        if doc.get("ocr_error"):
            st.warning(f"OCR 실패: {doc.get('ocr_error')}")

        st.markdown("**핵심 필드 추출**")
        field_rows = []
        for field in FIELD_DEFINITIONS:
            entry = display_doc.get("fields", {}).get(field["name"])
            field_rows.append({
                "항목": field["label"],
                "값": entry.get("value") if entry else "",
                "근거(소스)": entry.get("source") if entry else "",
                "근거(스니펫)": entry.get("snippet") if entry else "",
            })
        st.dataframe(field_rows, use_container_width=True)

        st.markdown("**조항 체크리스트**")
        clause_rows = []
        for clause in display_doc.get("clauses", []):
            clause_rows.append({
                "조항": clause.get("label"),
                "존재": "O" if clause.get("present") else "X",
                "근거(소스)": clause.get("source") or "",
                "근거(스니펫)": clause.get("snippet") or "",
            })
        st.dataframe(clause_rows, use_container_width=True)

    term_sheet = analysis.get("term_sheet")
    investment_agreement = analysis.get("investment_agreement")
    if term_sheet and investment_agreement:
        st.divider()
        st.markdown("## 내용 일치 검토")
        st.caption("핵심 항목이 두 문서에서 일치하는지 확인합니다.")
        comparisons = compare_fields(term_sheet.get("fields", {}), investment_agreement.get("fields", {}))
        if masking_enabled:
            comparisons = mask_comparisons(comparisons, replacements)
        st.dataframe(comparisons, use_container_width=True)

    st.divider()
    st.markdown("## 문서 내 검색")
    query = st.text_input("검색어", key="contract_search_query", placeholder="예: 투자금액, 준거법, 청산우선권")
    if query:
        if term_sheet:
            st.markdown("**텀싯 검색 결과**")
            hits = search_segments(term_sheet.get("segments", []), query)
            if masking_enabled:
                hits = mask_search_hits(hits, replacements)
            if hits:
                for hit in hits:
                    st.caption(f"{hit.get('source')}: {hit.get('snippet')}")
            else:
                st.caption("일치하는 결과가 없습니다.")
        if investment_agreement:
            st.markdown("**투자계약서 검색 결과**")
            hits = search_segments(investment_agreement.get("segments", []), query)
            if masking_enabled:
                hits = mask_search_hits(hits, replacements)
            if hits:
                for hit in hits:
                    st.caption(f"{hit.get('source')}: {hit.get('snippet')}")
            else:
                st.caption("일치하는 결과가 없습니다.")
