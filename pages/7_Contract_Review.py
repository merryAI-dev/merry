"""
투자 계약서 리서치/검토 에이전트 (Term Sheet / 투자계약서)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Optional

import streamlit as st

from shared.auth import check_authentication, get_user_api_key, get_user_id
from shared.config import initialize_session_state, inject_custom_css
from shared.ui import render_page_header
from shared.file_utils import (
    ALLOWED_EXTENSIONS_PDF,
    cleanup_user_temp_files,
    get_secure_upload_path,
    validate_upload,
)
try:
    from shared.cache_utils import (
        clear_cache_dir,
        compute_file_hash,
        compute_payload_hash,
        get_cache_dir,
        load_json,
        remove_cache_file,
        save_json,
    )
    _CACHE_UTILS_AVAILABLE = True
    _CACHE_UTILS_ERROR = None
except Exception as exc:
    _CACHE_UTILS_AVAILABLE = False
    _CACHE_UTILS_ERROR = exc

    def clear_cache_dir(namespace: str, user_id: str) -> int:
        return 0

    def compute_file_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
        return "nocache"

    def compute_payload_hash(payload: Dict[str, object]) -> str:
        return "nocache"

    def get_cache_dir(namespace: str, user_id: str) -> Path:
        return Path("temp") / "cache" / "disabled"

    def load_json(path: Path) -> Optional[Dict[str, object]]:
        return None

    def remove_cache_file(path: Path) -> bool:
        return False

    def save_json(path: Path, data: Dict[str, object]) -> None:
        return None
from shared.contract_review import (
    FIELD_DEFINITIONS,
    OCR_DEFAULT_MODEL,
    build_mask_replacements,
    build_review_opinion,
    compare_fields,
    detect_clauses,
    extract_fields,
    load_document,
    generate_contract_opinion_llm,
    local_ocr_available,
    mask_analysis,
    mask_comparisons,
    mask_sensitive_text,
    mask_search_hits,
    search_segments,
)

CACHE_NAMESPACE = "contract_review"
CACHE_VERSION = 2


st.set_page_config(
    page_title="계약서 리서치 | 메리",
    page_icon="image-removebg-preview-5.png",
    layout="wide",
)

initialize_session_state()
check_authentication()
inject_custom_css()

user_id = get_user_id()
user_api_key = get_user_api_key()

render_page_header(
    "계약서 리서치 에이전트",
    "텀싯/투자계약서를 근거 기반으로 검토합니다. 법률 자문이 아니라 리서치 보조 도구입니다.",
)

st.warning("이 도구는 법률 자문이 아닙니다. 최종 판단은 반드시 법무 검토가 필요합니다.")

analysis_exists = bool(st.session_state.get("contract_analysis"))

if not _CACHE_UTILS_AVAILABLE:
    st.warning("캐시 모듈을 로드하지 못했습니다. 캐시 기능이 비활성화됩니다.")
    if _CACHE_UTILS_ERROR:
        st.caption(f"세부 오류: {_CACHE_UTILS_ERROR}")

if st.session_state.get("contract_cache_version") != CACHE_VERSION:
    clear_cache_dir(CACHE_NAMESPACE, user_id or "anonymous")
    st.session_state.contract_cache_version = CACHE_VERSION

with st.expander("보안/마스킹", expanded=not analysis_exists):
    masking_enabled = st.checkbox(
        "민감정보 마스킹 (기본 ON)",
        value=True,
        key="contract_masking",
        help="회사명/금액/연락처 등 민감정보를 토큰으로 치환해 표시합니다.",
    )
    show_file_names = st.checkbox(
        "파일명 표시",
        value=False,
        key="contract_show_file_names",
        help="파일명에 회사명이 포함될 수 있어 기본은 숨김입니다.",
    )
    if not masking_enabled:
        st.warning("원문 표시 중입니다. 공유/스크린샷에 주의하세요.")
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

with st.expander("스캔본 OCR (Claude)", expanded=not analysis_exists):
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
        help="이미지 OCR로 전환될 때 사용됩니다.",
    )
    ocr_refine = st.checkbox(
        "Claude 정제 (로컬 OCR 텍스트 후처리)",
        value=st.session_state.get("contract_ocr_refine", True),
        key="contract_ocr_refine",
    )
    ocr_refine_model = st.text_input(
        "정제 모델",
        value=st.session_state.get("contract_ocr_refine_model", OCR_DEFAULT_MODEL),
        key="contract_ocr_refine_model",
    )
    ocr_lang = st.text_input(
        "로컬 OCR 언어",
        value=st.session_state.get("contract_ocr_lang", "kor+eng"),
        key="contract_ocr_lang",
        help="tesseract 언어 코드 (예: kor+eng)",
    )
    local_ocr_status = "사용 가능" if local_ocr_available() else "불가 (이미지 OCR로 대체)"
    st.caption(f"로컬 OCR 상태: {local_ocr_status}")
    st.caption("기본은 로컬 OCR → Claude 텍스트 정제입니다. 로컬 OCR 불가 시 이미지 OCR로 전환됩니다.")

with st.expander("분석 모드", expanded=not analysis_exists):
    analysis_mode = st.selectbox(
        "분석 모드",
        ["빠른 스캔", "정밀 분석"],
        index=0,
        key="contract_analysis_mode",
        help="빠른 스캔은 OCR 페이지를 제한하고 핵심 리스크를 먼저 보여줍니다.",
    )
    ocr_strategy = st.selectbox(
        "OCR 페이지 선정",
        ["밀도 기반(빠름)", "앞/뒤 우선", "균등 분할"],
        index=0,
        key="contract_ocr_strategy",
    )
    ocr_budget = st.slider(
        "OCR 페이지 예산",
        min_value=2,
        max_value=40,
        value=6,
        step=1,
        key="contract_ocr_budget",
        disabled=analysis_mode == "정밀 분석" or ocr_choice == "끄기",
        help="빠른 스캔에서 OCR할 최대 페이지 수입니다.",
    )
    if analysis_mode == "빠른 스캔":
        st.caption("빠른 스캔은 선택된 페이지만 OCR해서 속도를 높입니다. 세부 확인은 추가 질문으로 진행하세요.")


def _resolve_ocr_mode() -> str:
    mapping = {
        "자동(권장)": "auto",
        "강제": "force",
        "끄기": "off",
    }
    return mapping.get(ocr_choice, "auto")


def _resolve_ocr_strategy() -> str:
    mapping = {
        "밀도 기반(빠름)": "density",
        "앞/뒤 우선": "front_back",
        "균등 분할": "uniform",
    }
    return mapping.get(ocr_strategy, "density")


def _resolve_ocr_budget() -> int:
    if analysis_mode == "정밀 분석" or ocr_choice == "끄기":
        return 0
    return int(ocr_budget)


def _resolve_ocr_refine() -> bool:
    return bool(ocr_refine)


def _resolve_ocr_refine_model() -> str:
    return (ocr_refine_model or OCR_DEFAULT_MODEL).strip()


def _resolve_ocr_lang() -> str:
    return (ocr_lang or "kor+eng").strip()

with st.expander("캐시 관리", expanded=False):
    if st.button("계약서 캐시 전체 삭제", type="secondary"):
        cleared = clear_cache_dir(CACHE_NAMESPACE, user_id or "anonymous")
        st.success(f"캐시 삭제 완료: {cleared}건")
    doc_paths = [
        ("텀싯", st.session_state.get("contract_term_sheet_path"), "term_sheet"),
        ("투자계약서", st.session_state.get("contract_investment_path"), "investment_agreement"),
    ]
    for label, path_str, doc_type in doc_paths:
        if not path_str:
            continue
        if st.button(f"{label} 캐시 삭제", type="secondary"):
            try:
                path = Path(path_str)
                file_hash = compute_file_hash(path)
                payload = {
                    "version": CACHE_VERSION,
                    "doc_type": doc_type,
                    "file_hash": file_hash,
                    "ocr_mode": _resolve_ocr_mode(),
                    "ocr_model": (ocr_model or OCR_DEFAULT_MODEL).strip(),
                    "ocr_refine": _resolve_ocr_refine(),
                    "ocr_refine_model": _resolve_ocr_refine_model(),
                    "ocr_strategy": _resolve_ocr_strategy(),
                    "ocr_budget": _resolve_ocr_budget(),
                    "ocr_lang": _resolve_ocr_lang(),
                }
                cache_key = compute_payload_hash(payload)
                cache_dir = get_cache_dir(CACHE_NAMESPACE, user_id)
                cache_path = cache_dir / f"{cache_key}.json"
                removed = remove_cache_file(cache_path)
                if removed:
                    st.success(f"{label} 캐시 삭제 완료")
                else:
                    st.warning(f"{label} 캐시 파일이 없습니다.")
            except Exception as exc:
                st.error(f"{label} 캐시 삭제 실패: {exc}")

allowed_extensions = ALLOWED_EXTENSIONS_PDF + [".docx"]

if "contract_analysis" not in st.session_state:
    st.session_state.contract_analysis = {}


def _build_doc_cache_path(path: Path, doc_type: str) -> Path:
    file_hash = compute_file_hash(path)
    payload = {
        "version": CACHE_VERSION,
        "doc_type": doc_type,
        "file_hash": file_hash,
        "ocr_mode": _resolve_ocr_mode(),
        "ocr_model": (ocr_model or OCR_DEFAULT_MODEL).strip(),
        "ocr_refine": _resolve_ocr_refine(),
        "ocr_refine_model": _resolve_ocr_refine_model(),
        "ocr_strategy": _resolve_ocr_strategy(),
        "ocr_budget": _resolve_ocr_budget(),
        "ocr_lang": _resolve_ocr_lang(),
    }
    cache_key = compute_payload_hash(payload)
    cache_dir = get_cache_dir(CACHE_NAMESPACE, user_id)
    return cache_dir / f"{cache_key}.json"


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
        if show_file_names:
            st.success(f"업로드 완료: {term_sheet_file.name}")
        else:
            st.success("업로드 완료")

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
        if show_file_names:
            st.success(f"업로드 완료: {investment_file.name}")
        else:
            st.success("업로드 완료")

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
        cache_path = _build_doc_cache_path(path, doc_type)
        cached = load_json(cache_path)
        if cached:
            cached["cache_hit"] = True
            if on_step:
                on_step(f"{doc_label} 캐시 사용")
            return cached

        if on_step:
            on_step(f"{doc_label} 문서 파싱 중...")
        loaded = load_document(
            path,
            ocr_mode=_resolve_ocr_mode(),
            api_key=user_api_key,
            ocr_model=(ocr_model or OCR_DEFAULT_MODEL).strip(),
            ocr_page_budget=_resolve_ocr_budget(),
            ocr_strategy=_resolve_ocr_strategy(),
            ocr_refine=_resolve_ocr_refine(),
            ocr_refine_model=_resolve_ocr_refine_model(),
            ocr_fast_lang=_resolve_ocr_lang(),
            progress_callback=ocr_callback,
        )
    except Exception as exc:
        st.error(f"문서 파싱 실패: {path.name} ({exc})")
        return None

    segments = loaded.get("segments", [])
    if on_step:
        on_step(f"{doc_label} 필드/조항 추출 중...")
    fields = extract_fields(segments)
    clauses = detect_clauses(segments, doc_type, loaded.get("segment_scores", {}))

    doc = {
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
        "ocr_pages_used": loaded.get("ocr_pages_used", []),
        "ocr_engine": loaded.get("ocr_engine", ""),
        "ocr_refined": loaded.get("ocr_refined", False),
        "ocr_refine_error": loaded.get("ocr_refine_error", ""),
        "priority_segments": loaded.get("priority_segments", []),
        "cache_hit": False,
    }
    save_json(cache_path, doc)
    return doc


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
    st.session_state.contract_opinion_text = ""
    st.session_state.contract_opinion_cache_key = ""

    if term_sheet_path:
        doc = _analyze_document(
            term_sheet_path,
            "term_sheet",
            "텀싯",
            on_step=_advance,
            ocr_callback=_make_ocr_callback("텀싯"),
        )
        if doc:
            if doc.get("cache_hit"):
                ocr_progress_placeholder.progress(1.0, text="텀싯 캐시 사용")
            else:
                if doc.get("ocr_error"):
                    ocr_progress_placeholder.progress(1.0, text=f"텀싯 OCR 실패: {doc.get('ocr_error')}")
                elif doc.get("ocr_used"):
                    ocr_pages = doc.get("ocr_pages_used", [])
                    total_pages = doc.get("page_count", 0)
                    engine_label = doc.get("ocr_engine", "")
                    engine_text = ""
                    if engine_label == "local+claude":
                        engine_text = "로컬+정제"
                    elif engine_label == "local":
                        engine_text = "로컬"
                    elif engine_label == "claude_image":
                        engine_text = "이미지"
                    suffix = f", {engine_text}" if engine_text else ""
                    ocr_progress_placeholder.progress(
                        1.0,
                        text=f"텀싯 OCR 완료 ({len(ocr_pages)}/{total_pages}p{suffix})",
                    )
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
            if doc.get("cache_hit"):
                ocr_progress_placeholder.progress(1.0, text="투자계약서 캐시 사용")
            else:
                if doc.get("ocr_error"):
                    ocr_progress_placeholder.progress(1.0, text=f"투자계약서 OCR 실패: {doc.get('ocr_error')}")
                elif doc.get("ocr_used"):
                    ocr_pages = doc.get("ocr_pages_used", [])
                    total_pages = doc.get("page_count", 0)
                    engine_label = doc.get("ocr_engine", "")
                    engine_text = ""
                    if engine_label == "local+claude":
                        engine_text = "로컬+정제"
                    elif engine_label == "local":
                        engine_text = "로컬"
                    elif engine_label == "claude_image":
                        engine_text = "이미지"
                    suffix = f", {engine_text}" if engine_text else ""
                    ocr_progress_placeholder.progress(
                        1.0,
                        text=f"투자계약서 OCR 완료 ({len(ocr_pages)}/{total_pages}p{suffix})",
                    )
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

    term_sheet = analysis.get("term_sheet")
    investment_agreement = analysis.get("investment_agreement")
    comparisons = []
    if term_sheet and investment_agreement:
        comparisons = compare_fields(term_sheet.get("fields", {}), investment_agreement.get("fields", {}))
        if masking_enabled:
            comparisons = mask_comparisons(comparisons, replacements)

    st.divider()
    st.markdown("## 종합 의견")
    opinion = build_review_opinion(term_sheet, investment_agreement, comparisons)
    st.markdown("**요약**")
    for line in opinion.get("summary", []):
        st.markdown(f"- {line}")

    opinion_items = opinion.get("items", [])
    if opinion_items:
        st.markdown("**핵심 이슈**")
        severity_order = {"높음": 0, "중간": 1, "낮음": 2, "정보": 3}
        ranked = sorted(opinion_items, key=lambda item: severity_order.get(item.get("severity", ""), 9))
        rows = []
        for idx, item in enumerate(ranked, start=1):
            detail = item.get("detail", "")
            action = item.get("action", "")
            detail_text = detail
            if action:
                detail_text = f"{detail} → {action}" if detail else action
            rows.append({
                "순위": idx,
                "심각도": item.get("severity", ""),
                "이슈": item.get("issue", ""),
                "상세 내용": detail_text,
            })
        st.dataframe(rows, use_container_width=True)
    else:
        st.caption("표시할 이슈가 없습니다.")

    st.markdown("### Claude 종합 의견")
    use_llm_opinion = st.toggle(
        "Claude 종합 의견 자동 생성",
        value=st.session_state.get("contract_llm_opinion", True),
        key="contract_llm_opinion",
        help="규칙 기반 이슈를 바탕으로 Claude가 종합 의견을 작성합니다.",
    )
    opinion_model = st.text_input(
        "종합 의견 모델",
        value=st.session_state.get("contract_opinion_model", OCR_DEFAULT_MODEL),
        key="contract_opinion_model",
        help="기본: Claude Opus. 비용/속도에 따라 변경 가능.",
    )
    if use_llm_opinion:
        st.caption("종합 의견 생성 시 요약 데이터가 외부 API로 전송됩니다.")
        opinion_payload = json.dumps(opinion, ensure_ascii=False, sort_keys=True)
        opinion_key = hashlib.sha256(opinion_payload.encode("utf-8")).hexdigest()
        if not user_api_key:
            st.warning("Claude 종합 의견을 생성하려면 API 키가 필요합니다.")
        elif st.session_state.get("contract_opinion_cache_key") != opinion_key:
            st.session_state.contract_opinion_text = ""
            with st.spinner("Claude가 종합 의견을 작성 중입니다..."):
                try:
                    st.session_state.contract_opinion_text = generate_contract_opinion_llm(
                        opinion,
                        api_key=user_api_key,
                        model=(opinion_model or OCR_DEFAULT_MODEL).strip(),
                    )
                    st.session_state.contract_opinion_cache_key = opinion_key
                except Exception as exc:
                    st.error(f"종합 의견 생성 실패: {exc}")
        if st.session_state.get("contract_opinion_text"):
            st.markdown(st.session_state.contract_opinion_text)

    questions = opinion.get("questions", [])
    if questions:
        st.markdown("**확인 질문**")
        for question in questions:
            st.markdown(f"- {question}")

    st.divider()
    st.markdown("## 리스크 질문 (멀티턴)")
    if "contract_chat" not in st.session_state:
        st.session_state.contract_chat = []

    if st.button("질문 기록 초기화", type="secondary"):
        st.session_state.contract_chat = []

    for message in st.session_state.contract_chat:
        st.chat_message(message.get("role", "assistant")).markdown(message.get("content", ""))

    user_query = st.chat_input("궁금한 조항/리스크를 질문하세요. 예: 청산우선권, 희석방지, 투자금액")
    if user_query:
        st.session_state.contract_chat.append({"role": "user", "content": user_query})

        available_docs = []
        missing_docs = []
        if term_sheet:
            available_docs.append("텀싯")
        else:
            missing_docs.append("텀싯")
        if investment_agreement:
            available_docs.append("투자계약서")
        else:
            missing_docs.append("투자계약서")

        responses = []
        term_hits = []
        invest_hits = []
        if term_sheet:
            term_hits = search_segments(term_sheet.get("segments", []), user_query, max_hits=3)
        if investment_agreement:
            invest_hits = search_segments(investment_agreement.get("segments", []), user_query, max_hits=3)

        if masking_enabled:
            term_hits = mask_search_hits(term_hits, replacements)
            invest_hits = mask_search_hits(invest_hits, replacements)

        if term_hits or invest_hits:
            if available_docs:
                responses.append(f"검색 범위: {', '.join(available_docs)}")
            responses.append("관련 스니펫:")
            for hit in term_hits:
                responses.append(f"- [텀싯 {hit.get('source')}] {hit.get('snippet')}")
            for hit in invest_hits:
                responses.append(f"- [투자계약서 {hit.get('source')}] {hit.get('snippet')}")
        else:
            responses.append("관련 텍스트를 찾지 못했습니다. 다른 키워드로 검색하거나 OCR 범위를 늘려보세요.")
            if available_docs:
                responses.append(f"현재 검색 범위: {', '.join(available_docs)}")
            if missing_docs:
                responses.append(f"비교/대조를 위해 추가 업로드 필요: {', '.join(missing_docs)}")

        if analysis_mode == "빠른 스캔" and ocr_choice != "끄기":
            responses.append("빠른 스캔 모드라 일부 페이지만 OCR했습니다. 중요한 조항은 정밀 분석에서 다시 확인하세요.")

        st.session_state.contract_chat.append({"role": "assistant", "content": "\n".join(responses)})
        st.rerun()

    with st.expander("문서 상세 보기", expanded=False):
        st.markdown("### 문서 요약")

        for key in ["term_sheet", "investment_agreement"]:
            doc = analysis.get(key)
            if not doc:
                continue

            title = "텀싯" if key == "term_sheet" else "투자계약서"
            display_doc = mask_analysis(doc, replacements) if masking_enabled else doc
            st.markdown(f"#### {title}")
            ocr_pages = doc.get("ocr_pages_used", [])
            ocr_engine = doc.get("ocr_engine", "")
            engine_label = ""
            if ocr_engine == "local+claude":
                engine_label = "로컬+정제"
            elif ocr_engine == "local":
                engine_label = "로컬"
            elif ocr_engine == "claude_image":
                engine_label = "이미지"
            if doc.get("ocr_error"):
                ocr_status = "OCR: 실패"
            elif doc.get("ocr_used"):
                suffix = f" ({engine_label})" if engine_label else ""
                ocr_status = f"OCR: {len(ocr_pages)}/{doc.get('page_count', 0)}p{suffix}"
            else:
                ocr_status = "OCR: 미사용"
            if doc.get("cache_hit"):
                ocr_status = f"{ocr_status} · 캐시"
            file_label = doc.get("name") if show_file_names else "(숨김)"
            st.caption(
                f"파일: {file_label} · 길이: {doc.get('text_length', 0):,} chars · 세그먼트: {len(doc.get('segments', []))} · {ocr_status}"
            )
            if doc.get("ocr_error"):
                st.warning(f"OCR 실패: {doc.get('ocr_error')}")
            if doc.get("ocr_refine_error"):
                st.warning(f"Claude 정제 실패: {doc.get('ocr_refine_error')}")

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
                    "가중치": clause.get("weight", 0.0),
                    "근거(소스)": clause.get("source") or "",
                    "근거(스니펫)": clause.get("snippet") or "",
                })
            st.dataframe(clause_rows, use_container_width=True)

            priority_segments = doc.get("priority_segments", [])
            if priority_segments:
                st.markdown("**우선 검토 영역 (비지도 가중치 상위)**")
                rows = []
                for entry in priority_segments[:8]:
                    snippet = entry.get("snippet", "")
                    if masking_enabled:
                        snippet = mask_sensitive_text(snippet, replacements)
                    rows.append({
                        "가중치": entry.get("weight", 0.0),
                        "섹션": entry.get("section", ""),
                        "소스": entry.get("source", ""),
                        "요약": snippet,
                    })
                st.dataframe(rows, use_container_width=True)

        if comparisons:
            st.markdown("### 내용 일치 검토")
            st.caption("핵심 항목이 두 문서에서 일치하는지 확인합니다.")
            st.dataframe(comparisons, use_container_width=True)

        st.markdown("### 문서 내 검색")
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
else:
    st.divider()
    st.info("분석 결과가 아직 없습니다. 문서를 업로드한 뒤 '분석 실행'을 눌러주세요.")
