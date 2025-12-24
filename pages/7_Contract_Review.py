"""
투자 계약서 리서치/검토 에이전트 (Term Sheet / 투자계약서)
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import streamlit as st

from shared.auth import check_authentication, get_user_id
from shared.config import initialize_session_state, inject_custom_css
from shared.file_utils import (
    ALLOWED_EXTENSIONS_PDF,
    cleanup_user_temp_files,
    get_secure_upload_path,
    validate_upload,
)
from shared.contract_review import (
    FIELD_DEFINITIONS,
    compare_fields,
    detect_clauses,
    extract_fields,
    load_document,
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

user_id = get_user_id()
allowed_extensions = ALLOWED_EXTENSIONS_PDF + [".docx"]

if "contract_analysis" not in st.session_state:
    st.session_state.contract_analysis = {}



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


def _analyze_document(path_str: str, doc_type: str) -> Optional[Dict[str, object]]:
    if not path_str:
        return None

    path = Path(path_str)
    try:
        loaded = load_document(path)
    except Exception as exc:
        st.error(f"문서 파싱 실패: {path.name} ({exc})")
        return None

    segments = loaded.get("segments", [])
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
    }


if analyze_clicked:
    term_sheet_path = st.session_state.get("contract_term_sheet_path")
    investment_path = st.session_state.get("contract_investment_path")

    st.session_state.contract_analysis = {}

    if term_sheet_path:
        st.session_state.contract_analysis["term_sheet"] = _analyze_document(term_sheet_path, "term_sheet")
    if investment_path:
        st.session_state.contract_analysis["investment_agreement"] = _analyze_document(
            investment_path,
            "investment_agreement",
        )

    if not st.session_state.contract_analysis:
        st.warning("먼저 문서를 업로드하세요.")

analysis = st.session_state.contract_analysis

if analysis:
    st.divider()
    st.markdown("## 문서 요약")

    for key in ["term_sheet", "investment_agreement"]:
        doc = analysis.get(key)
        if not doc:
            continue

        title = "텀싯" if key == "term_sheet" else "투자계약서"
        st.markdown(f"### {title}")
        st.caption(f"파일: {doc.get('name')} · 길이: {doc.get('text_length', 0):,} chars · 세그먼트: {len(doc.get('segments', []))}")

        st.markdown("**핵심 필드 추출**")
        field_rows = []
        for field in FIELD_DEFINITIONS:
            entry = doc.get("fields", {}).get(field["name"])
            field_rows.append({
                "항목": field["label"],
                "값": entry.get("value") if entry else "",
                "근거(소스)": entry.get("source") if entry else "",
                "근거(스니펫)": entry.get("snippet") if entry else "",
            })
        st.dataframe(field_rows, use_container_width=True)

        st.markdown("**조항 체크리스트**")
        clause_rows = []
        for clause in doc.get("clauses", []):
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
        st.dataframe(comparisons, use_container_width=True)

    st.divider()
    st.markdown("## 문서 내 검색")
    query = st.text_input("검색어", key="contract_search_query", placeholder="예: 투자금액, 준거법, 청산우선권")
    if query:
        if term_sheet:
            st.markdown("**텀싯 검색 결과**")
            hits = search_segments(term_sheet.get("segments", []), query)
            if hits:
                for hit in hits:
                    st.caption(f"{hit.get('source')}: {hit.get('snippet')}")
            else:
                st.caption("일치하는 결과가 없습니다.")
        if investment_agreement:
            st.markdown("**투자계약서 검색 결과**")
            hits = search_segments(investment_agreement.get("segments", []), query)
            if hits:
                for hit in hits:
                    st.caption(f"{hit.get('source')}: {hit.get('snippet')}")
            else:
                st.caption("일치하는 결과가 없습니다.")
