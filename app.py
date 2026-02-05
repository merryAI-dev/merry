"""
VC 투자 분석 에이전트 - Claude Code 스타일

실행: streamlit run app.py
"""

import asyncio
import re
from datetime import datetime
import io
import textwrap
from pathlib import Path
from typing import Optional
import streamlit as st

from shared.config import (
    get_avatar_image,
    get_user_avatar_image,
    initialize_session_state,
    initialize_agent,
)
from shared.auth import check_authentication
from shared.file_utils import (
    ALLOWED_EXTENSIONS_PDF,
    ALLOWED_EXTENSIONS_EXCEL,
    cleanup_user_temp_files,
    get_secure_upload_path,
    validate_upload,
)
from shared.logging_config import setup_logging
from agent.tools import (
    execute_read_pdf_as_text,
    execute_extract_pdf_market_evidence,
    execute_read_excel_as_text,
    execute_read_docx_as_text,
)
from dolphin_service.processor import process_documents_batch

# 로깅 초기화
setup_logging()

# 페이지 설정
st.set_page_config(
    page_title="메리 | VC 에이전트",
    page_icon="M",
    layout="wide",
    initial_sidebar_state="collapsed"  # 사이드바 숨김
)

# 초기화 및 인증
initialize_session_state()
check_authentication()  # 인증되지 않으면 여기서 멈춤

# ========================================
# 포트폴리오 데이터 사전 로드 (백그라운드 캐싱)
# ========================================
from shared.airtable_portfolio import _get_cached_dataframe

# 앱 시작 시 DataFrame 미리 로드 (첫 검색부터 빠르게)
# @st.cache_data로 캐싱되므로 한 번만 실행됨
try:
    with st.spinner("📊 투자 데이터 로딩 중..."):
        df = _get_cached_dataframe()
        portfolio_size = len(df)

        st.session_state["portfolio_preloaded"] = True
        st.session_state["portfolio_size"] = portfolio_size

        # 성공 메시지 (2초 후 사라짐)
        success_container = st.empty()
        success_container.success(f"✅ 투자 데이터 로딩 완료! ({portfolio_size}개 기업)")
        import time
        time.sleep(2)
        success_container.empty()

except Exception as e:
    st.session_state["portfolio_preloaded"] = False
    st.session_state["portfolio_error"] = str(e)
    st.error(f"❌ 데이터 로딩 실패: {str(e)}")

# ========================================
# Claude Code 스타일 CSS
# ========================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

/* 전역 스타일 - 다크 테마 */
:root {
    --bg-primary: #0f0f0f;
    --bg-secondary: #1a1a1a;
    --border-color: #2a2a2a;
    --text-primary: #e4e4e7;
    --text-secondary: #a1a1aa;
    --accent: #3b82f6;
    --accent-hover: #2563eb;
    --tool-bg: #1a1a1a;
    --tool-border: #2a2a2a;
    --success: #10b981;
    --warning: #f59e0b;
}

html, body, [class*="css"] {
    font-family: 'Inter', 'Noto Sans KR', sans-serif;
    color: var(--text-primary);
    background-color: var(--bg-primary) !important;
}

/* 사이드바 완전히 숨김 */
[data-testid="stSidebar"] {
    display: none !important;
}

/* 메인 컨테이너 */
.stApp {
    background-color: var(--bg-primary) !important;
}

.main .block-container {
    max-width: 900px;
    padding-top: 2rem;
    padding-bottom: 6rem;
}

/* 헤더 */
.claude-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 0;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 2rem;
}

.claude-header__logo {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-primary);
}

.claude-header__badge {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    background: var(--bg-secondary);
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text-secondary);
    border: 1px solid var(--border-color);
}

/* Welcome 화면 */
.welcome-screen {
    text-align: center;
    padding: 4rem 2rem;
    max-width: 600px;
    margin: 0 auto;
}

.welcome-screen__title {
    font-size: 1.875rem;
    font-weight: 600;
    margin-bottom: 0.75rem;
}

.welcome-screen__subtitle {
    font-size: 1rem;
    color: var(--text-secondary);
    margin-bottom: 3rem;
}

.capability-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    justify-content: center;
    margin-bottom: 2rem;
}

/* Tool Use 카드 (Claude Code 스타일) */
.tool-card {
    margin: 1rem 0;
    border: 1px solid var(--tool-border);
    border-radius: 0.5rem;
    background: var(--tool-bg);
    overflow: hidden;
}

.tool-card__header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    background: var(--bg-primary);
    border-bottom: 1px solid var(--tool-border);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.875rem;
    font-weight: 500;
}

.tool-card__body {
    padding: 1rem;
    font-size: 0.875rem;
    line-height: 1.5;
}

.tool-card--running {
    border-color: var(--accent);
}

.tool-card--success {
    border-color: var(--success);
}

.tool-card--error {
    border-color: var(--warning);
}

/* 스피너 (실행 중) */
.tool-spinner {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 2px solid var(--tool-border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* 파일 칩 */
.file-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.375rem 0.75rem;
    border-radius: 0.375rem;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    font-size: 0.875rem;
    margin: 0.25rem;
}

/* 하단 고정 파일 영역 */
.fixed-file-area {
    max-width: 900px;
    margin: 0 auto 0.5rem auto;
    padding: 0.5rem 0;
}

/* Streamlit 기본 버튼 스타일 */
div[data-testid="stButton"] button {
    background: var(--bg-secondary) !important;
    border: 1px solid var(--border-color) !important;
    color: var(--text-primary) !important;
    border-radius: 0.5rem !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    padding: 0.5rem 1rem !important;
}

div[data-testid="stButton"] button:hover {
    background: var(--bg-primary) !important;
    border-color: var(--accent) !important;
    color: var(--accent) !important;
}

/* 게임 로딩 팁 배너 */
.loading-tips-banner {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: linear-gradient(90deg, #1a1a1a 0%, #2a2a2a 50%, #1a1a1a 100%);
    border-top: 1px solid var(--border-color);
    padding: 0.75rem 1rem;
    z-index: 999;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
}

.loading-tips-banner__icon {
    color: var(--success);
    font-size: 1rem;
    animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.loading-tips-banner__text {
    color: var(--text-secondary);
    font-size: 0.8125rem;
    max-width: 800px;
    text-align: center;
    transition: opacity 0.5s ease-in-out;
}

.report-preparse-status {
    width: 100%;
    white-space: normal;
    word-break: break-all;
    overflow-wrap: anywhere;
}

/* 시스템 메시지 (요약) 스타일 */
.system-message {
    background: rgba(59, 130, 246, 0.1);
    border-left: 3px solid var(--accent);
    padding: 0.75rem 1rem;
    border-radius: 0.5rem;
    margin: 1rem 0;
    font-size: 0.875rem;
}
</style>
""", unsafe_allow_html=True)

# ========================================
# 헤더
# ========================================
# 헤더: 3컬럼 레이아웃 (제목, 팀 선택, 새 대화 버튼)
col_left, col_mid, col_right = st.columns([3, 2, 1])

with col_left:
    st.markdown("""
    <div class="claude-header">
        <div class="claude-header__logo">
            <span>Merry</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_mid:
    # 팀 드롭다운
    team_options = [
        "CIC 봄날",
        "CIC 스템",
        "CIC 썬",
        "CIC 모모",
        "LS그룹",
        "CI그룹",
        "대표이사실"
    ]
    current_team = st.session_state.get("current_team", "CIC 봄날")
    selected_team = st.selectbox(
        "팀 선택",
        options=team_options,
        index=team_options.index(current_team) if current_team in team_options else 0,
        key="team_selector",
        label_visibility="collapsed"
    )
    if selected_team != current_team:
        st.session_state.current_team = selected_team
        st.rerun()

with col_right:
    if st.button("새 대화", key="new_chat", help="대화 초기화"):
        st.session_state.unified_messages = []
        st.session_state.unified_files = []
        st.rerun()

# 빠른 페이지 이동 (사이드바 숨김 보완)
st.markdown("### 바로가기")
nav_cols = st.columns(5)
with nav_cols[0]:
    st.page_link("pages/10_Fund_Dashboard.py", label="펀드 대시보드", icon="📊")
with nav_cols[1]:
    st.page_link("pages/0_Collaboration_Hub.py", label="협업 허브", icon="🧭")
with nav_cols[2]:
    st.page_link("pages/8_Startup_Discovery.py", label="스타트업 발굴", icon="🔍")
with nav_cols[3]:
    st.page_link("pages/11_Fund_Company_View.py", label="펀드/기업 상세", icon="🏷️")
with nav_cols[4]:
    st.page_link("pages/12_Fund_Newsletter.py", label="펀드 뉴스레터", icon="📰")

# ========================================
# 대화 기록 불러오기
# ========================================
from shared.conversation_history import list_conversations, load_conversation, save_conversation

current_team = st.session_state.get("current_team", "CIC 봄날")

# 대화 ID 초기화
if "current_conversation_id" not in st.session_state:
    st.session_state.current_conversation_id = None

# 대화 기록 expander
with st.expander("📚 대화 기록", expanded=False):
    conversations = list_conversations(current_team, limit=10)

    if conversations:
        st.caption(f"최근 {len(conversations)}개 대화")

        for conv in conversations:
            conv_id = conv["conversation_id"]
            preview = conv["preview"]
            msg_count = conv["message_count"]
            created = conv["created_at"][:16]  # YYYY-MM-DD HH:MM

            col1, col2 = st.columns([4, 1])
            with col1:
                if st.button(
                    f"💬 {preview} ({msg_count}개)",
                    key=f"load_{conv_id}",
                    help=f"생성: {created}",
                    use_container_width=True
                ):
                    # 대화 불러오기
                    messages, metadata = load_conversation(current_team, conv_id)
                    if messages:
                        st.session_state.unified_messages = messages
                        st.session_state.current_conversation_id = conv_id
                        st.toast(f"✅ 대화 불러오기 완료 ({msg_count}개 메시지)")
                        st.rerun()
            with col2:
                st.caption(f"{created[5:]}")  # MM-DD HH:MM
    else:
        st.info("저장된 대화 기록이 없습니다")

st.markdown("---")

# ========================================
# 에이전트 초기화
# ========================================
initialize_agent()

avatar_image = get_avatar_image()
user_avatar_image = get_user_avatar_image()

# 세션 상태 초기화
if "unified_messages" not in st.session_state:
    st.session_state.unified_messages = []
if "unified_files" not in st.session_state:
    st.session_state.unified_files = []
if "processed_upload_keys" not in st.session_state:
    st.session_state.processed_upload_keys = []
if "uploader_key_seed" not in st.session_state:
    st.session_state.uploader_key_seed = 0
if "report_panel_enabled" not in st.session_state:
    st.session_state.report_panel_enabled = False
if "unified_mode" not in st.session_state:
    st.session_state.unified_mode = "unified"
if "report_preparse_results" not in st.session_state:
    st.session_state.report_preparse_results = {}
if "report_preparse_status" not in st.session_state:
    st.session_state.report_preparse_status = "idle"
if "report_preparse_at" not in st.session_state:
    st.session_state.report_preparse_at = None
if "report_preparse_summary" not in st.session_state:
    st.session_state.report_preparse_summary = []
if "report_preparse_progress" not in st.session_state:
    st.session_state.report_preparse_progress = 0.0
if "report_preparse_current" not in st.session_state:
    st.session_state.report_preparse_current = ""
if "report_preparse_total" not in st.session_state:
    st.session_state.report_preparse_total = 0
if "report_preparse_log" not in st.session_state:
    st.session_state.report_preparse_log = []
if "report_panel_uploader_seed" not in st.session_state:
    st.session_state.report_panel_uploader_seed = 0
if "report_preparse_max_pages" not in st.session_state:
    st.session_state.report_preparse_max_pages = 30
if "report_preparse_market_evidence" not in st.session_state:
    st.session_state.report_preparse_market_evidence = True
if "report_preparse_fast_mode" not in st.session_state:
    st.session_state.report_preparse_fast_mode = False
if "report_preparse_mode" not in st.session_state:
    st.session_state.report_preparse_mode = "정확도 우선 (Vision)"
if "report_preparse_min_text_chars" not in st.session_state:
    st.session_state.report_preparse_min_text_chars = 200
if "report_preparse_max_ocr_pages" not in st.session_state:
    st.session_state.report_preparse_max_ocr_pages = 8
if "report_preparse_stage1_md" not in st.session_state:
    st.session_state.report_preparse_stage1_md = ""
if "report_preparse_stage2_md" not in st.session_state:
    st.session_state.report_preparse_stage2_md = ""
if "report_md_imported_at" not in st.session_state:
    st.session_state.report_md_imported_at = None
if "report_evidence_pack_md" not in st.session_state:
    st.session_state.report_evidence_pack_md = ""
if "report_evidence_pack_at" not in st.session_state:
    st.session_state.report_evidence_pack_at = None
if "report_evidence_pack_status" not in st.session_state:
    st.session_state.report_evidence_pack_status = "idle"
if "report_evidence_pack_company" not in st.session_state:
    st.session_state.report_evidence_pack_company = ""
if "report_evidence_pack_raw" not in st.session_state:
    st.session_state.report_evidence_pack_raw = ""
if "report_evidence_pack_raw_at" not in st.session_state:
    st.session_state.report_evidence_pack_raw_at = None
if "report_evidence_pack_raw_status" not in st.session_state:
    st.session_state.report_evidence_pack_raw_status = "idle"

if st.session_state.get("report_panel_enabled"):
    st.markdown(
        """
        <style>
        .main .block-container { max-width: 1400px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def _build_preparse_summary(results: dict) -> list:
    summary = []
    for path, info in (results or {}).items():
        entry = {
            "file": Path(path).name,
            "type": "",
            "status": "실패",
            "detail": "",
        }
        if "pdf" in info:
            pdf_result = info.get("pdf", {})
            entry["type"] = "PDF"
            if pdf_result.get("success"):
                entry["status"] = "성공"
                pages = pdf_result.get("pages_read")
                total_pages = pdf_result.get("total_pages")
                method = pdf_result.get("processing_method", "")
                entry["detail"] = f"{pages}/{total_pages}p · {method}"
            else:
                entry["detail"] = pdf_result.get("error", "PDF 파싱 실패")
            evidence = info.get("market_evidence", {})
            if isinstance(evidence, dict) and evidence.get("success"):
                entry["detail"] += f" · 시장근거 {evidence.get('evidence_count', 0)}건"
        elif "excel" in info:
            excel_result = info.get("excel", {})
            entry["type"] = "Excel"
            if excel_result.get("success"):
                entry["status"] = "성공"
                entry["detail"] = f"시트 {excel_result.get('total_sheets', 0)}개"
            else:
                entry["detail"] = excel_result.get("error", "엑셀 파싱 실패")
        elif "docx" in info:
            docx_result = info.get("docx", {})
            entry["type"] = "DOCX"
            if docx_result.get("success"):
                entry["status"] = "성공"
                entry["detail"] = f"문단 {docx_result.get('parsed_paragraphs', 0)}개"
            else:
                entry["detail"] = docx_result.get("error", "DOCX 파싱 실패")
        else:
            entry["detail"] = info.get("error", "지원되지 않는 파일")
        summary.append(entry)
    return summary


def _build_preparse_context(summary: list) -> Optional[str]:
    if not summary:
        return None
    lines = ["사전 파싱 완료 (캐시 사용 가능):"]
    for item in summary:
        lines.append(
            f"- {item.get('file')} [{item.get('type')}] {item.get('status')} · {item.get('detail')}"
        )
    return "\n".join(lines)


def _build_preparse_summary_block(summary: list) -> str:
    if not summary:
        return "- (파싱 요약 없음)"
    lines = []
    for item in summary:
        lines.append(
            f"- file: {item.get('file')} | type: {item.get('type')} | status: {item.get('status')} | detail: {item.get('detail')}"
        )
    return "\n".join(lines)


def _condense_stage1_for_extract(stage1_md: str, max_chars: int = 60000) -> str:
    if not stage1_md:
        return ""
    if len(stage1_md) <= max_chars:
        return stage1_md
    keywords = [
        "매출", "영업", "순이익", "자산", "부채", "자본", "현금", "투자", "주주", "지분",
        "설립", "대표", "법인", "사업자", "인증", "특허", "고객", "계약", "시장",
        "TAM", "SAM", "SOM", "성장", "재무", "IR", "valuation", "cap", "cap table",
    ]
    lines = []
    for line in stage1_md.splitlines():
        if any(k in line for k in keywords) or re.search(r"\\d", line):
            lines.append(line)
    condensed = "\n".join(lines).strip()
    if len(condensed) < 1000:
        half = max_chars // 2
        head = stage1_md[:half]
        tail = stage1_md[-half:]
        condensed = (head + "\n...\n" + tail).strip()
    return condensed[:max_chars]


def _derive_company_label(files: list) -> str:
    if not files:
        return "unknown"
    name = Path(files[0]).stem
    name = re.sub(r"^[0-9a-f]{6,}_", "", name)
    name = re.sub(r"[_\-]+", " ", name).strip()
    return name or "unknown"


def _format_financial_tables_md(financial_tables: dict, source_file: str = "") -> str:
    """financial_tables 딕셔너리를 마크다운으로 변환"""
    if not financial_tables:
        return ""

    lines = []
    source_prefix = f"[{source_file}] " if source_file else ""

    # 손익계산서
    is_data = financial_tables.get("income_statement", {})
    if is_data.get("found"):
        lines.append(f"#### {source_prefix}손익계산서 (p.{is_data.get('page', '?')})")
        unit = is_data.get("unit", "")
        years = is_data.get("years", [])
        metrics = is_data.get("metrics", {})
        if years and metrics:
            header = "| 항목 | " + " | ".join(str(y) for y in years) + " |"
            sep = "| --- |" + " --- |" * len(years)
            lines.append(header)
            lines.append(sep)
            metric_names = {
                "revenue": "매출액",
                "gross_profit": "매출총이익",
                "operating_income": "영업이익",
                "ebitda": "EBITDA",
                "net_income": "당기순이익",
            }
            for key, label in metric_names.items():
                vals = metrics.get(key, [])
                if vals:
                    row = f"| {label} ({unit}) | " + " | ".join(str(v) if v is not None else "-" for v in vals) + " |"
                    lines.append(row)
        lines.append("")

    # 재무상태표
    bs_data = financial_tables.get("balance_sheet", {})
    if bs_data.get("found"):
        lines.append(f"#### {source_prefix}재무상태표 (p.{bs_data.get('page', '?')})")
        unit = bs_data.get("unit", "")
        years = bs_data.get("years", [])
        metrics = bs_data.get("metrics", {})
        if years and metrics:
            header = "| 항목 | " + " | ".join(str(y) for y in years) + " |"
            sep = "| --- |" + " --- |" * len(years)
            lines.append(header)
            lines.append(sep)
            metric_names = {
                "total_assets": "총자산",
                "total_liabilities": "총부채",
                "total_equity": "총자본",
                "cash": "현금성자산",
            }
            for key, label in metric_names.items():
                vals = metrics.get(key, [])
                if vals:
                    row = f"| {label} ({unit}) | " + " | ".join(str(v) if v is not None else "-" for v in vals) + " |"
                    lines.append(row)
        lines.append("")

    # 현금흐름표
    cf_data = financial_tables.get("cash_flow", {})
    if cf_data.get("found"):
        lines.append(f"#### {source_prefix}현금흐름표 (p.{cf_data.get('page', '?')})")
        unit = cf_data.get("unit", "")
        years = cf_data.get("years", [])
        metrics = cf_data.get("metrics", {})
        if years and metrics:
            header = "| 항목 | " + " | ".join(str(y) for y in years) + " |"
            sep = "| --- |" + " --- |" * len(years)
            lines.append(header)
            lines.append(sep)
            metric_names = {
                "operating_cf": "영업CF",
                "investing_cf": "투자CF",
                "financing_cf": "재무CF",
                "fcf": "FCF",
            }
            for key, label in metric_names.items():
                vals = metrics.get(key, [])
                if vals:
                    row = f"| {label} ({unit}) | " + " | ".join(str(v) if v is not None else "-" for v in vals) + " |"
                    lines.append(row)
        lines.append("")

    # Cap Table
    cap_data = financial_tables.get("cap_table", {})
    if cap_data.get("found"):
        lines.append(f"#### {source_prefix}Cap Table (p.{cap_data.get('page', '?')})")
        shareholders = cap_data.get("shareholders", [])
        if shareholders:
            lines.append("| 주주명 | 지분율 | 주식수 |")
            lines.append("| --- | --- | --- |")
            for sh in shareholders:
                name = sh.get("name", "")
                pct = sh.get("ownership_pct", sh.get("percentage", ""))
                shares = sh.get("shares", "")
                lines.append(f"| {name} | {pct} | {shares} |")
        total_shares = cap_data.get("total_shares")
        if total_shares:
            lines.append(f"\n총발행주식수: {total_shares:,}" if isinstance(total_shares, (int, float)) else f"\n총발행주식수: {total_shares}")
        lines.append("")

    return "\n".join(lines)


def _format_investment_terms_md(inv_terms: dict, source_file: str = "") -> str:
    """투자조건 딕셔너리를 마크다운으로 변환"""
    if not inv_terms or not inv_terms.get("found"):
        return ""

    source_prefix = f"[{source_file}] " if source_file else ""
    lines = [f"#### {source_prefix}투자조건 (p.{inv_terms.get('page', '?')})"]

    field_names = {
        "investment_amount": "투자금액",
        "pre_money": "Pre-money 밸류",
        "post_money": "Post-money 밸류",
        "price_per_share": "주당 투자단가",
        "shares_acquired": "취득 주식수",
        "ownership_pct": "취득 지분율",
        "investment_type": "투자 구조",
        "investment_round": "투자 라운드",
    }

    for key, label in field_names.items():
        val = inv_terms.get(key)
        if val:
            lines.append(f"- {label}: {val}")

    return "\n".join(lines) + "\n"


def _build_stage1_markdown(results: dict) -> str:
    blocks = []
    appendix_blocks = []

    for path, info in (results or {}).items():
        title = Path(path).name
        blocks.append(f"### {title}")
        if "pdf" in info:
            pdf_result = info.get("pdf", {})
            content = pdf_result.get("content") or ""
            blocks.append(content if content else "_(PDF 텍스트 없음)_")

            # 구조화된 재무 데이터가 있으면 Appendix에 추가
            financial_tables = pdf_result.get("financial_tables", {})
            if financial_tables:
                ft_md = _format_financial_tables_md(financial_tables, title)
                if ft_md.strip():
                    appendix_blocks.append(ft_md)

            # 투자조건 데이터
            inv_terms = pdf_result.get("investment_terms", {})
            if inv_terms and inv_terms.get("found"):
                inv_md = _format_investment_terms_md(inv_terms, title)
                if inv_md.strip():
                    appendix_blocks.append(inv_md)

        elif "excel" in info:
            content = info.get("excel", {}).get("content") or ""
            blocks.append(content if content else "_(엑셀 텍스트 없음)_")
        elif "docx" in info:
            content = info.get("docx", {}).get("content") or ""
            blocks.append(content if content else "_(DOCX 텍스트 없음)_")
        else:
            blocks.append("_지원되지 않는 파일 형식_")
        blocks.append("")

    # Appendix: 구조화된 재무 데이터
    if appendix_blocks:
        blocks.append("\n---\n## Appendix: 자동 추출된 재무 데이터\n")
        blocks.append("아래 데이터는 PDF에서 자동 추출된 구조화된 재무정보입니다.\n")
        blocks.extend(appendix_blocks)

    return "\n".join(blocks).strip()


def _build_preparse_md() -> str:
    summary = st.session_state.get("report_preparse_summary", [])
    results = st.session_state.get("report_preparse_results", {})
    stage1_md = st.session_state.get("report_preparse_stage1_md") or _build_stage1_markdown(results)
    stage2_md = st.session_state.get("report_preparse_stage2_md") or "N/A"
    files = st.session_state.get("unified_files", [])
    label = _derive_company_label(files)
    created_at = datetime.now().isoformat()
    lines = [
        "# MerryParse Export",
        f"- created_at: {created_at}",
        f"- source_files: {[Path(f).name for f in files]}",
        f"- ocr_mode: {st.session_state.get('report_preparse_mode')}",
        f"- max_pages: {st.session_state.get('report_preparse_max_pages')}",
        f"- market_evidence: {st.session_state.get('report_preparse_market_evidence')}",
        "",
        "## Stage1 (Raw Markdown)",
        stage1_md if stage1_md else "N/A",
        "",
        "## Stage2 (Refined Markdown)",
        stage2_md if stage2_md else "N/A",
        "",
        "## Summary",
    ]
    for item in summary:
        lines.append(
            f"- file: {item.get('file')} | status: {item.get('status')} | detail: {item.get('detail')}"
        )
    return "\n".join(lines), label


def _parse_md_sections(md_text: str) -> dict:
    sections = {"stage1": "", "stage2": "", "summary": []}
    current = None
    for line in md_text.splitlines():
        if line.strip().startswith("## Stage1"):
            current = "stage1"
            continue
        if line.strip().startswith("## Stage2"):
            current = "stage2"
            continue
        if line.strip().startswith("## Summary"):
            current = "summary"
            continue
        if current == "summary":
            if line.strip().startswith("- file:"):
                parts = line.split("|")
                entry = {"file": "", "status": "", "detail": ""}
                if parts:
                    entry["file"] = parts[0].replace("- file:", "").strip()
                if len(parts) > 1:
                    entry["status"] = parts[1].replace("status:", "").strip()
                if len(parts) > 2:
                    entry["detail"] = parts[2].replace("detail:", "").strip()
                sections["summary"].append(entry)
        elif current in ["stage1", "stage2"]:
            sections[current] += line + "\n"
    for key in ["stage1", "stage2"]:
        sections[key] = sections[key].strip()
    return sections


def _restore_from_md(md_text: str) -> None:
    if md_text.lstrip().startswith("# Investment Review Evidence Pack"):
        st.session_state.report_evidence_pack_md = md_text
        st.session_state.report_evidence_pack_at = datetime.now().isoformat()
        st.session_state.report_md_imported_at = datetime.now().isoformat()
        company = ""
        for line in md_text.splitlines()[:20]:
            if line.strip().startswith("- company:"):
                company = line.split(":", 1)[1].strip()
                break
        st.session_state.report_evidence_pack_company = company
        return
    parsed = _parse_md_sections(md_text)
    st.session_state.report_preparse_stage1_md = parsed.get("stage1", "")
    st.session_state.report_preparse_stage2_md = parsed.get("stage2", "")
    st.session_state.report_preparse_summary = parsed.get("summary", [])
    st.session_state.report_preparse_at = datetime.now().isoformat()
    st.session_state.report_md_imported_at = datetime.now().isoformat()


def _collect_market_evidence(results: dict, max_items: int = 30) -> list:
    items = []
    for path, info in (results or {}).items():
        evidence = info.get("market_evidence", {})
        if not isinstance(evidence, dict):
            continue
        for entry in evidence.get("evidence", [])[:max_items]:
            items.append({
                "file": Path(path).name,
                "page": entry.get("page"),
                "text": entry.get("text"),
                "numbers": entry.get("numbers", []),
            })
            if len(items) >= max_items:
                return items
    return items


def _collect_structured_financial_data(results: dict) -> str:
    """파싱 결과에서 구조화된 재무 데이터를 마크다운으로 수집"""
    blocks = []

    for path, info in (results or {}).items():
        filename = Path(path).name
        if "pdf" not in info:
            continue

        pdf_result = info.get("pdf", {})
        financial_tables = pdf_result.get("financial_tables", {})
        investment_terms = pdf_result.get("investment_terms", {})

        # 재무제표 데이터
        if financial_tables:
            ft_md = _format_financial_tables_md(financial_tables, filename)
            if ft_md.strip():
                blocks.append(ft_md)

        # 투자조건 데이터
        if investment_terms and investment_terms.get("found"):
            inv_md = _format_investment_terms_md(investment_terms, filename)
            if inv_md.strip():
                blocks.append(inv_md)

    if not blocks:
        return "- (자동 추출된 구조화 데이터 없음)"

    return "\n\n".join(blocks)


def _extract_evidence_pack_quality(md_text: str) -> dict:
    lines = [line.strip() for line in (md_text or "").splitlines()]
    evidence_count = sum(1 for line in lines if line.startswith("- [근거"))
    has_unknown = any("판단 유보" in line for line in lines)
    return {
        "evidence_count": evidence_count,
        "has_unknown": has_unknown,
    }


def _is_evidence_pack_stale() -> bool:
    pack_at = st.session_state.get("report_evidence_pack_at")
    preparse_at = st.session_state.get("report_preparse_at")
    if not pack_at or not preparse_at:
        return False
    try:
        return pack_at < preparse_at
    except Exception:
        return False


def _build_evidence_pack_extract_prompt(stage1_md: str, evidence_items: list, preparse_summary: str, structured_financial: str = "") -> str:
    company = st.session_state.get("report_evidence_pack_company") or "unknown"
    source_files = [Path(f).name for f in st.session_state.get("unified_files", [])]
    created_at = datetime.now().isoformat()
    evidence_lines = []
    for item in evidence_items:
        page = item.get("page")
        page_text = f"p.{page}" if page else "p.?"
        text = (item.get("text") or "").strip()
        numbers = item.get("numbers") or []
        number_str = ", ".join(numbers) if numbers else ""
        evidence_lines.append(
            f"- [{item.get('file')}] {page_text}: {text} {number_str}".strip()
        )

    evidence_block = "\n".join(evidence_lines) if evidence_lines else "- (근거 없음)"
    structured_block = structured_financial if structured_financial else "- (자동 추출된 구조화 데이터 없음)"

    return textwrap.dedent(
        f"""
        당신은 문서에서 사실/수치만 뽑아내는 Extractor입니다.
        아래 자료를 읽고 **JSON만** 출력하세요. 설명 금지.

        **중요: [자동 추출된 구조화 재무 데이터] 섹션에 이미 손익계산서/재무상태표/Cap Table 등이 정리되어 있습니다.**
        **이 데이터를 numbers에 그대로 옮기고, 추가로 텍스트에서 발견한 정보만 보충하세요.**
        **자동 추출 데이터가 있는 항목은 [추정]이 아니라 실제 Source를 명시하세요.**

        JSON 스키마:
        {{
          "company": "{company}",
          "source_files": {source_files},
          "facts": [{{"chapter": "I. 투자 개요", "text": "...", "source": "파일명 p.x"}}],
          "numbers": [{{"chapter": "VI. 수익성/Valuation", "metric": "매출", "value": "1,234", "unit": "백만원", "period": "2024", "source": "파일명 p.x"}}],
          "financial_tables": {{
            "income_statement": {{"years": [...], "revenue": [...], "operating_income": [...], "net_income": [...], "unit": "...", "source": "파일명 p.x"}},
            "balance_sheet": {{"years": [...], "total_assets": [...], "total_liabilities": [...], "total_equity": [...], "unit": "...", "source": "파일명 p.x"}},
            "cap_table": {{"shareholders": [{{"name": "...", "ownership_pct": "...", "shares": ...}}], "total_shares": ..., "source": "파일명 p.x"}},
            "investment_terms": {{"amount": "...", "pre_money": "...", "price_per_share": "...", "source": "파일명 p.x"}}
          }},
          "entities": {{"organizations": [], "people": [], "products": [], "certifications": [], "competitors": []}},
          "missing": [{{"chapter": "III. 시장 분석", "items": ["TAM/SAM/SOM"]}}]
        }}

        규칙:
        - **자동 추출된 구조화 데이터를 최우선으로 사용** (이미 파싱 완료된 정확한 데이터)
        - Fact/Number는 반드시 Source 포함 (파일명 p.페이지번호)
        - 자동 추출 데이터에 없는 항목만 텍스트에서 추가 추출
        - 추정은 text에 [추정] 표기 (자동 추출 데이터는 추정 아님)
        - 숫자는 단위/기간 포함
        - 자료가 없으면 missing에 기록
        - JSON 이외 텍스트 출력 금지

        [파싱 요약]
        {preparse_summary}

        [자동 추출된 구조화 재무 데이터] (최우선 사용)
        {structured_block}

        [Stage1 Markdown]
        {stage1_md}

        [Market Evidence]
        {evidence_block}
        """
    ).strip()


def _build_evidence_pack_format_prompt(extraction_json: str, preparse_summary: str) -> str:
    company = st.session_state.get("report_evidence_pack_company") or "unknown"
    source_files = [Path(f).name for f in st.session_state.get("unified_files", [])]
    created_at = datetime.now().isoformat()
    return textwrap.dedent(
        f"""
        당신은 시니어 VC 심사역입니다. 아래 추출 JSON을 바탕으로 **Evidence Pack MD (심사역이 보완 가능한 추출물)**를 작성하세요.
        이 문서는 **GPT-2 수준 모델도 사용할 수 있을 정도로 명확하고 구조화된 추출물**이어야 합니다.

        출력 형식은 반드시 다음 템플릿을 따르세요:

        # Investment Review Evidence Pack
        - company: {company}
        - created_at: {created_at}
        - source_files: {source_files}

        ## 0. 파싱 요약
        {preparse_summary}

        ## 1. 핵심 정보 요약 (One-Page)
        - 기업/제품 한줄 요약:
        - 타겟 시장/고객:
        - 수익 모델:
        - 현재 단계(시드/Pre-A/Series A 등):
        - 핵심 수치(매출/손익/자본/부채 등):

        ## 2. 챕터별 근거 맵 (Facts/Numbers)
        ### I. 투자 개요
        #### Facts
        - Fact: ... | Source: ...
        #### Numbers
        | Metric | Value | Unit | Period | Source |
        | --- | --- | --- | --- | --- |
        #### Missing
        - ...

        ### II. 기업 현황
        #### Facts
        - Fact: ... | Source: ...
        #### Numbers
        | Metric | Value | Unit | Period | Source |
        | --- | --- | --- | --- | --- |
        #### Missing
        - ...

        ### III. 시장 분석
        #### Facts
        - Fact: ... | Source: ...
        #### Numbers
        | Metric | Value | Unit | Period | Source |
        | --- | --- | --- | --- | --- |
        #### Missing
        - ...

        ### IV. 사업 분석
        #### Facts
        - Fact: ... | Source: ...
        #### Numbers
        | Metric | Value | Unit | Period | Source |
        | --- | --- | --- | --- | --- |
        #### Missing
        - ...

        ### V. 투자 적합성 및 임팩트
        #### Facts
        - Fact: ... | Source: ...
        #### Numbers
        | Metric | Value | Unit | Period | Source |
        | --- | --- | --- | --- | --- |
        #### Missing
        - ...

        ### VI. 수익성/Valuation
        #### Facts
        - Fact: ... | Source: ...
        #### Numbers
        | Metric | Value | Unit | Period | Source |
        | --- | --- | --- | --- | --- |
        #### Missing
        - ...

        ### VII. 임팩트 리스크
        #### Facts
        - Fact: ... | Source: ...
        #### Numbers
        | Metric | Value | Unit | Period | Source |
        | --- | --- | --- | --- | --- |
        #### Missing
        - ...

        ### VIII. 종합 결론
        #### Facts
        - Fact: ... | Source: ...
        #### Missing
        - ...

        ## 3. 엔티티/키워드
        - Organizations:
        - People:
        - Products/Services:
        - Certifications/Regulatory:
        - Competitors:

        ## 4. 재무/표 추출 (자동 추출 데이터 기반)
        **⚠️ 중요: Extraction JSON의 financial_tables에 자동 추출된 데이터가 있으면 이를 그대로 사용하세요. [추정] 표기 금지.**

        ### 4.1 손익계산서
        | Year | Revenue | Gross Profit | Operating Income | Net Income | Unit | Source |
        | --- | --- | --- | --- | --- | --- | --- |
        (financial_tables.income_statement 데이터를 연도별로 펼쳐서 작성)

        ### 4.2 재무상태표
        | Year | Total Assets | Total Liabilities | Total Equity | Cash | Unit | Source |
        | --- | --- | --- | --- | --- | --- | --- |
        (financial_tables.balance_sheet 데이터를 연도별로 펼쳐서 작성)

        ### 4.3 현금흐름
        | Year | Operating CF | Investing CF | Financing CF | FCF | Unit | Source |
        | --- | --- | --- | --- | --- | --- |
        (financial_tables.cash_flow 데이터가 있으면 작성)

        ### 4.4 Cap Table
        | 주주명 | 지분율 | 주식수 |
        | --- | --- | --- |
        (financial_tables.cap_table.shareholders 데이터를 그대로 작성)
        총발행주식수: (financial_tables.cap_table.total_shares)

        ### 4.5 투자조건
        (financial_tables.investment_terms 데이터를 항목별로 작성)
        - 투자금액:
        - Pre-money:
        - 주당가격:
        - 취득지분:

        ## 5. HF 검증 체크리스트 (사람 검토용)
        - [ ] 투자 조건(금액/밸류/지분율) 원문 확인
        - [ ] 핵심 제품/서비스 기능 검증
        - [ ] 주요 고객/매출처 검증
        - [ ] 재무제표 수치 대조
        - [ ] 법적 리스크(등기부 말소사항) 확인

        ## 6. Machine-Readable Summary (YAML)
        ```yaml
        company: {company}
        industry: unknown
        products: []
        customers: []
        business_model: unknown
        stage: unknown
        financials:
          revenue: {{}}
          operating_income: {{}}
          net_income: {{}}
          assets: {{}}
          liabilities: {{}}
        certifications: []
        risks: []
        ```

        규칙:
        - **🚨 최우선: financial_tables에 자동 추출된 데이터가 있으면 반드시 사용. [추정] 표기 대신 실제 Source(파일명 p.페이지) 명시**
        - 반드시 각 챕터별로 Facts/Numbers/Missing을 포함
        - 근거 문항은 가능하면 5개, 부족하면 2~3개라도 작성
        - 자료가 부족하면 "판단 유보(근거 부족)"으로 명시하되, 파일명/메타에서 합리적 추정이 가능한 경우 [추정]으로 표기
        - 모든 Fact/Number는 **Source**를 포함 (없으면 "Source: Evidence Pack MD"로 표시)
        - company/source_files/created_at 값을 임의로 변경하지 말고 그대로 출력
        - 불필요한 서론/설명 없이 MD만 출력
        - **섹션 4의 재무 테이블은 financial_tables 데이터를 그대로 옮겨 작성 (비어있지 않게)**

        [Extraction JSON]
        {extraction_json}
        """
    ).strip()

def _preparse_report_files_batch(
    max_pages: int,
    include_market_evidence: bool,
) -> None:
    """모든 PDF를 한 번에 합쳐서 단일 API 호출로 처리 (효율적)"""
    st.session_state.report_preparse_status = "running"
    st.session_state.report_preparse_progress = 0.0
    st.session_state.report_preparse_current = ""
    st.session_state.report_preparse_log = []

    files = list(st.session_state.get("unified_files", []))
    missing_files = [f for f in files if not Path(f).exists()]
    if missing_files:
        st.warning("일부 파일이 삭제되었습니다. 다시 업로드해 주세요.")
        files = [f for f in files if Path(f).exists()]
        st.session_state.unified_files = files
    if not files:
        st.warning("업로드된 파일이 없습니다.")
        st.session_state.report_preparse_status = "idle"
        return

    st.session_state.report_preparse_total = len(files)
    progress = st.progress(0.0)
    status = st.empty()

    # PDF와 기타 파일 분리
    pdf_files = [f for f in files if Path(f).suffix.lower() == ".pdf"]
    other_files = [f for f in files if Path(f).suffix.lower() != ".pdf"]

    results = {}

    # 1. 모든 PDF를 한 번에 배치 처리
    if pdf_files:
        status.markdown(
            f"<div class='report-preparse-status'>📥 {len(pdf_files)}개 PDF 일괄 분석 중...</div>",
            unsafe_allow_html=True,
        )
        st.session_state.report_preparse_log.append(f"PDF {len(pdf_files)}개 일괄 처리 시작")
        st.session_state.report_preparse_current = f"PDF {len(pdf_files)}개"

        def progress_cb(event):
            msg = event.get("content", "")
            st.session_state.report_preparse_log.append(msg)

        batch_result = process_documents_batch(
            pdf_paths=pdf_files,
            max_pages_per_pdf=max_pages,
            max_total_images=20,  # Claude 제한
            output_mode="structured",
            progress_callback=progress_cb,
        )

        progress.progress(0.7)
        st.session_state.report_preparse_progress = 0.7

        if batch_result.get("success"):
            # 배치 결과를 개별 파일 결과로 분배 (호환성 유지)
            for pdf_path in pdf_files:
                filename = Path(pdf_path).name
                results[pdf_path] = {
                    "pdf": {
                        "success": True,
                        "content": batch_result.get("content", ""),
                        "financial_tables": batch_result.get("financial_tables", {}),
                        "investment_terms": batch_result.get("investment_terms", {}),
                        "company_info": batch_result.get("company_info", {}),
                        "processing_method": "claude_opus_batch",
                        "pages_read": batch_result.get("file_page_map", {}).get(filename, 0),
                        "total_pages": batch_result.get("file_page_map", {}).get(filename, 0),
                        # 배치 전체 정보
                        "_batch_source_files": batch_result.get("source_files", []),
                        "_batch_total_images": batch_result.get("total_images", 0),
                    }
                }
            st.session_state.report_preparse_log.append(
                f"PDF 일괄 처리 완료 ({batch_result.get('processing_time_seconds', 0):.1f}초)"
            )

            # Market evidence는 별도로 (선택적)
            if include_market_evidence:
                for pdf_path in pdf_files:
                    evidence_result = execute_extract_pdf_market_evidence(
                        pdf_path=pdf_path,
                        max_pages=max_pages,
                        max_results=20,
                    )
                    results[pdf_path]["market_evidence"] = evidence_result
        else:
            st.error(f"PDF 배치 처리 실패: {batch_result.get('error', 'Unknown error')}")
            for pdf_path in pdf_files:
                results[pdf_path] = {"pdf": {"success": False, "error": batch_result.get("error")}}

    # 2. Excel/DOCX는 개별 처리
    for idx, path in enumerate(other_files):
        filename = Path(path).name
        st.session_state.report_preparse_current = filename
        ext = Path(path).suffix.lower()

        if ext in [".xlsx", ".xls"]:
            excel_result = execute_read_excel_as_text(excel_path=path, max_rows=80)
            results[path] = {"excel": excel_result}
        elif ext == ".docx":
            docx_result = execute_read_docx_as_text(docx_path=path, max_paragraphs=200)
            results[path] = {"docx": docx_result}
        else:
            results[path] = {"error": "지원되지 않는 파일 형식"}

        st.session_state.report_preparse_log.append(f"완료: {filename}")

    progress.progress(1.0)
    st.session_state.report_preparse_results = results
    st.session_state.report_preparse_summary = _build_preparse_summary(results)
    st.session_state.report_preparse_at = datetime.now().isoformat()
    st.session_state.report_preparse_status = "done"
    st.session_state.report_preparse_progress = 1.0
    st.session_state.report_preparse_current = ""
    status.markdown("✅ 일괄 파싱 완료")


def _preparse_report_files(
    max_pages: int,
    include_market_evidence: bool,
    ocr_mode: str,
    min_text_chars: int,
    max_ocr_pages: int,
) -> None:
    """개별 파일별 파싱 (기존 방식, 호환성 유지)"""
    st.session_state.report_preparse_status = "running"
    st.session_state.report_preparse_progress = 0.0
    st.session_state.report_preparse_current = ""
    st.session_state.report_preparse_log = []

    files = list(st.session_state.get("unified_files", []))
    missing_files = [f for f in files if not Path(f).exists()]
    if missing_files:
        st.warning(
            "일부 업로드 파일이 임시 저장소에서 삭제되었습니다. "
            "다시 업로드한 후 파싱을 진행해 주세요."
        )
        st.session_state.report_preparse_log.append(
            f"누락 파일 {len(missing_files)}개 감지"
        )
        files = [f for f in files if Path(f).exists()]
        st.session_state.unified_files = files
    if not files:
        st.warning("업로드된 파일이 없습니다.")
        st.session_state.report_preparse_status = "idle"
        return

    st.session_state.report_preparse_total = len(files)
    results = {}
    progress = st.progress(0.0)
    status = st.empty()

    total = len(files)
    for idx, path in enumerate(files, start=1):
        filename = Path(path).name
        st.session_state.report_preparse_current = filename
        st.session_state.report_preparse_progress = min((idx - 1) / max(total, 1), 0.95)
        st.session_state.report_preparse_log.append(f"시작: {filename}")
        status.markdown(
            f"<div class='report-preparse-status'>📥 {filename} 파싱 중...</div>",
            unsafe_allow_html=True,
        )
        ext = Path(path).suffix.lower()
        if ext == ".pdf":
            pdf_result = execute_read_pdf_as_text(
                pdf_path=path,
                max_pages=max_pages,
                output_mode="structured" if ocr_mode != "pymupdf" else "text_only",
                extract_financial_tables=ocr_mode != "pymupdf",
                ocr_mode=ocr_mode,
                min_text_chars=min_text_chars,
                max_ocr_pages=max_ocr_pages,
            )
            result_entry = {"pdf": pdf_result}
            if include_market_evidence:
                evidence_result = execute_extract_pdf_market_evidence(
                    pdf_path=path,
                    max_pages=max_pages,
                    max_results=20,
                )
                result_entry["market_evidence"] = evidence_result
            results[path] = result_entry
        elif ext in [".xlsx", ".xls"]:
            excel_result = execute_read_excel_as_text(
                excel_path=path,
                max_rows=80,
            )
            results[path] = {"excel": excel_result}
        elif ext == ".docx":
            docx_result = execute_read_docx_as_text(
                docx_path=path,
                max_paragraphs=200,
            )
            results[path] = {"docx": docx_result}
        else:
            results[path] = {"error": "지원되지 않는 파일 형식"}

        progress.progress(idx / total)
        st.session_state.report_preparse_progress = min(idx / max(total, 1), 0.98)
        st.session_state.report_preparse_log.append(f"완료: {filename}")

    st.session_state.report_preparse_results = results
    st.session_state.report_preparse_summary = _build_preparse_summary(results)
    st.session_state.report_preparse_at = datetime.now().isoformat()
    st.session_state.report_preparse_status = "done"
    st.session_state.report_preparse_progress = 1.0
    st.session_state.report_preparse_current = ""
    status.markdown("✅ 일괄 파싱 완료")


def save_uploaded_file(uploaded_file) -> str:
    """업로드된 파일을 temp 디렉토리에 저장"""
    user_id = st.session_state.get("user_id", "anonymous")
    all_extensions = set(ALLOWED_EXTENSIONS_PDF) | set(ALLOWED_EXTENSIONS_EXCEL) | {".docx", ".doc"}

    is_valid, error = validate_upload(
        filename=uploaded_file.name,
        file_size=uploaded_file.size,
        allowed_extensions=all_extensions,
    )
    if not is_valid:
        st.error(error)
        return None

    file_path = get_secure_upload_path(user_id=user_id, original_filename=uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # 투자심사 워크플로에서는 여러 파일을 동시에 유지해야 함
    max_files = 10
    if st.session_state.get("report_panel_enabled"):
        max_files = max(50, len(st.session_state.get("unified_files", [])) + 10)
    cleanup_user_temp_files(user_id, max_files=max_files)
    return str(file_path)


def compact_conversation(messages: list, api_key: str) -> tuple[list, bool]:
    """
    대화 히스토리를 요약하여 컴팩트

    Args:
        messages: 현재 메시지 리스트
        api_key: Claude API 키

    Returns:
        (컴팩트된 메시지 리스트, 컴팩션 성공 여부)
    """
    COMPACTION_TRIGGER = 15
    COMPACTION_TARGET = 10

    if len(messages) < COMPACTION_TRIGGER:
        return messages, False

    # 요약할 메시지 (첫 10개)
    to_compact = messages[:COMPACTION_TARGET]
    remaining = messages[COMPACTION_TARGET:]

    # 요약 생성
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)

        # 대화 내용을 텍스트로 변환 (system 메시지는 제외)
        conversation_text = "\n\n".join([
            f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content'][:500]}"  # 긴 응답 잘라내기
            for msg in to_compact
            if msg['role'] != 'system'
        ])

        # Claude에게 요약 요청
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",  # 빠르고 저렴한 모델
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": f"""다음은 VC 투자 분석 대화의 일부입니다.
이 대화를 간결하게 요약해주세요. 핵심 정보만 포함하고, 3-5문장으로 작성해주세요.

{conversation_text}

요약:"""
            }]
        )

        summary = response.content[0].text.strip()

        # 요약을 시스템 메시지로 추가
        compacted = [{
            "role": "system",
            "content": f"[이전 대화 요약]\n{summary}"
        }]

        # 나머지 메시지 추가
        compacted.extend(remaining)

        return compacted, True

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"대화 컴팩션 실패: {e}")
        # 요약 실패 시 기존 방식 (단순 삭제)
        return messages[-COMPACTION_TRIGGER:], False


use_report_panel = st.session_state.get("report_panel_enabled", False)
if use_report_panel:
    st.session_state.unified_mode = "report"
    chat_col, report_col = st.columns([1.15, 0.85], gap="large")
else:
    chat_col = st.container()
    report_col = None

report_stream_placeholder = None
report_status_placeholder = None
report_log_placeholder = None
chapter_order = []
current_chapter = None

if use_report_panel and report_col is not None:
    with report_col:
        st.markdown("## 투자심사 보고서")
        with st.expander("자료 준비/일괄 파싱", expanded=True):
            uploader_key = f"report_panel_uploader_{st.session_state.report_panel_uploader_seed}"
            uploaded_panel_files = st.file_uploader(
                "여기에 파일을 드래그앤드롭하거나 선택하세요 (PDF, 엑셀, DOCX)",
                type=["pdf", "xlsx", "xls", "docx", "doc"],
                accept_multiple_files=True,
                key=uploader_key,
                help="투자심사 보고서에 사용할 자료를 한 번에 업로드하세요."
            )

            if uploaded_panel_files:
                processed_keys = set(st.session_state.get("processed_upload_keys", []))
                new_upload_processed = False
                for uploaded_file in uploaded_panel_files:
                    upload_key = f"{uploaded_file.name}|{uploaded_file.size}"
                    if upload_key in processed_keys:
                        continue
                    processed_keys.add(upload_key)
                    file_path = save_uploaded_file(uploaded_file)
                    if file_path and file_path not in st.session_state.unified_files:
                        st.session_state.unified_files.append(file_path)
                        new_upload_processed = True
                st.session_state.processed_upload_keys = sorted(processed_keys)
                if new_upload_processed:
                    st.session_state.report_panel_uploader_seed += 1
                    st.rerun()

            files = st.session_state.get("unified_files", [])
            if st.session_state.get("report_preparse_status") == "running":
                total = st.session_state.get("report_preparse_total", 0)
                current = st.session_state.get("report_preparse_current") or "진행 중..."
                st.info(f"파싱 중: {current} ({len(st.session_state.get('report_preparse_log', []))//2}/{total})")
                st.progress(st.session_state.get("report_preparse_progress", 0.0))
                with st.expander("파싱 로그", expanded=False):
                    logs = st.session_state.get("report_preparse_log", [])
                    if logs:
                        st.markdown("\n".join([f"- {line}" for line in logs[-10:]]))
                    else:
                        st.caption("로그 없음")
            if files:
                st.caption(f"업로드 파일 {len(files)}개")
                for fpath in files:
                    st.markdown(f"- {Path(fpath).name}")

                options_cols = st.columns([1, 1])
                with options_cols[0]:
                    st.session_state.report_preparse_max_pages = st.slider(
                        "PDF 최대 페이지",
                        min_value=5,
                        max_value=80,
                        value=st.session_state.report_preparse_max_pages,
                        step=5,
                        help="페이지 수가 많을수록 정확하지만 시간이 오래 걸립니다.",
                    )
                with options_cols[1]:
                    st.session_state.report_preparse_market_evidence = st.checkbox(
                        "시장근거 추출 포함 (느림)",
                        value=st.session_state.report_preparse_market_evidence,
                        help="PDF 내 시장규모 근거 문장을 별도 추출합니다.",
                    )
                mode_options = [
                    "🚀 배치 모드 (추천)",
                    "정확도 우선 (Vision)",
                    "중간 정확도 (Hybrid)",
                    "빠른 파싱 (텍스트만)",
                ]
                current_mode = st.session_state.report_preparse_mode
                if current_mode not in mode_options:
                    current_mode = mode_options[0]
                st.session_state.report_preparse_mode = st.selectbox(
                    "파싱 모드",
                    options=mode_options,
                    index=mode_options.index(current_mode),
                    help="배치 모드: 모든 PDF를 합쳐서 한 번에 분석 (빠르고 효율적). Vision: 개별 처리.",
                )

                if st.session_state.report_preparse_mode == "중간 정확도 (Hybrid)":
                    hybrid_cols = st.columns([1, 1])
                    with hybrid_cols[0]:
                        st.session_state.report_preparse_min_text_chars = st.slider(
                            "저텍스트 기준(문자 수)",
                            min_value=50,
                            max_value=400,
                            value=st.session_state.report_preparse_min_text_chars,
                            step=25,
                            help="이 기준보다 텍스트가 적은 페이지는 OCR 보강 대상으로 간주합니다.",
                        )
                    with hybrid_cols[1]:
                        st.session_state.report_preparse_max_ocr_pages = st.slider(
                            "OCR 보강 페이지 수",
                            min_value=1,
                            max_value=15,
                            value=st.session_state.report_preparse_max_ocr_pages,
                            step=1,
                            help="보강할 최대 페이지 수를 제한합니다.",
                        )

                cols = st.columns([1, 1])
                with cols[0]:
                    if st.button("완료 (일괄 파싱)", use_container_width=True):
                        mode = st.session_state.report_preparse_mode

                        if mode == "🚀 배치 모드 (추천)":
                            # 배치 모드: 모든 PDF를 합쳐서 한 번에 처리
                            _preparse_report_files_batch(
                                max_pages=st.session_state.report_preparse_max_pages,
                                include_market_evidence=st.session_state.report_preparse_market_evidence,
                            )
                        else:
                            # 기존 개별 처리 모드
                            ocr_mode = "vision"
                            if mode == "중간 정확도 (Hybrid)":
                                ocr_mode = "hybrid"
                            elif mode == "빠른 파싱 (텍스트만)":
                                ocr_mode = "pymupdf"

                            _preparse_report_files(
                                max_pages=st.session_state.report_preparse_max_pages,
                                include_market_evidence=st.session_state.report_preparse_market_evidence,
                                ocr_mode=ocr_mode,
                                min_text_chars=st.session_state.report_preparse_min_text_chars,
                                max_ocr_pages=st.session_state.report_preparse_max_ocr_pages,
                            )
                        st.session_state.report_panel_uploader_seed += 1
                        st.rerun()
                with cols[1]:
                    if st.button("파싱 요약 새로고침", use_container_width=True):
                        st.session_state.report_preparse_summary = _build_preparse_summary(
                            st.session_state.get("report_preparse_results", {})
                        )
                        st.rerun()
            else:
                st.info("업로드된 파일이 없습니다. 위에서 드래그앤드롭하거나 MD를 업로드해 주세요.")

            if st.session_state.get("report_preparse_at"):
                st.caption(f"마지막 파싱: {st.session_state.report_preparse_at}")
            if st.session_state.get("report_md_imported_at"):
                st.caption(f"MD 복구 시각: {st.session_state.report_md_imported_at}")

            summary = st.session_state.get("report_preparse_summary", [])
            if summary:
                st.table(summary)

            md_upload = st.file_uploader(
                "MD 업로드 (복구)",
                type=["md", "markdown", "txt"],
                accept_multiple_files=False,
                key="report_md_uploader",
                help="MerryParse/Evidence Pack MD를 업로드하면 파싱 요약/컨텍스트를 복구합니다.",
            )
            if md_upload is not None:
                try:
                    md_text = md_upload.getvalue().decode("utf-8", errors="ignore")
                    _restore_from_md(md_text)
                    st.success("MD 복구 완료. 파싱 요약을 다시 확인하세요.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"MD 복구 실패: {exc}")

            evidence_pack_md = st.session_state.get("report_evidence_pack_md")
            if summary or evidence_pack_md:
                md_content, md_label = _build_preparse_md()
                if evidence_pack_md:
                    md_content = evidence_pack_md
                    md_label = st.session_state.get("report_evidence_pack_company") or _derive_company_label(files)
                quality = _extract_evidence_pack_quality(md_content)
                stale = _is_evidence_pack_stale()
                if evidence_pack_md and quality.get("evidence_count", 0) == 0:
                    st.warning(
                        "Evidence Pack에 근거 문항이 없습니다. "
                        "파싱 결과를 확인하고 필요 시 보완해 주세요."
                    )
                if stale:
                    st.warning("Evidence Pack이 최신 파싱과 연결되지 않습니다. 재생성 권장 (현재 MD 우선 사용).")
                st.download_button(
                    label="Evidence Pack MD 다운로드",
                    data=md_content,
                    file_name=f"evidence_pack_{md_label}_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
                    mime="text/markdown",
                    use_container_width=True,
                    disabled=not evidence_pack_md,
                )

            with st.expander("Evidence Pack 생성 (Opus)", expanded=False):
                if st.session_state.report_evidence_pack_raw_status == "running":
                    st.info("Evidence Pack 빠른 추출 중입니다...")
                if st.session_state.report_evidence_pack_status == "running":
                    st.info("Evidence Pack 정리 중입니다...")
                st.session_state.report_evidence_pack_company = st.text_input(
                    "기업명",
                    value=st.session_state.report_evidence_pack_company,
                    placeholder="예: 주식회사 스트레스솔루션",
                )
                extract_col, format_col = st.columns([1, 1])
                with extract_col:
                    if st.button(
                        "빠른 추출 (Raw)",
                        use_container_width=True,
                        disabled=not files or not st.session_state.report_evidence_pack_company.strip(),
                    ):
                        api_key = st.session_state.get("user_api_key") or st.secrets.get("anthropic_api_key", "")
                        if not api_key:
                            st.error("Claude API Key가 필요합니다.")
                        else:
                            st.session_state.report_evidence_pack_raw_status = "running"
                            stage1_md = st.session_state.get("report_preparse_stage1_md") or _build_stage1_markdown(
                                st.session_state.get("report_preparse_results", {})
                            )
                            condensed = _condense_stage1_for_extract(stage1_md)
                            evidence_items = _collect_market_evidence(
                                st.session_state.get("report_preparse_results", {})
                            )
                            summary_block = _build_preparse_summary_block(
                                st.session_state.get("report_preparse_summary", [])
                            )
                            structured_financial = _collect_structured_financial_data(
                                st.session_state.get("report_preparse_results", {})
                            )
                            prompt = _build_evidence_pack_extract_prompt(condensed, evidence_items, summary_block, structured_financial)
                            try:
                                from anthropic import Anthropic
                                client = Anthropic(api_key=api_key)
                                response = client.messages.create(
                                    model="claude-opus-4-5-20251101",
                                    max_tokens=3500,
                                    temperature=0.2,
                                    messages=[{"role": "user", "content": prompt}],
                                )
                                text = response.content[0].text if response.content else ""
                                st.session_state.report_evidence_pack_raw = text.strip()
                                st.session_state.report_evidence_pack_raw_at = datetime.now().isoformat()
                                st.session_state.report_evidence_pack_raw_status = "done"
                                st.success("빠른 추출 완료")
                                st.rerun()
                            except Exception as exc:
                                st.session_state.report_evidence_pack_raw_status = "idle"
                                st.error(f"빠른 추출 실패: {exc}")
                with format_col:
                    if st.button(
                        "정리해서 Evidence Pack 생성",
                        use_container_width=True,
                        disabled=not st.session_state.report_evidence_pack_raw or not st.session_state.report_evidence_pack_company.strip(),
                    ):
                        api_key = st.session_state.get("user_api_key") or st.secrets.get("anthropic_api_key", "")
                        if not api_key:
                            st.error("Claude API Key가 필요합니다.")
                        else:
                            st.session_state.report_evidence_pack_status = "running"
                            summary_block = _build_preparse_summary_block(
                                st.session_state.get("report_preparse_summary", [])
                            )
                            prompt = _build_evidence_pack_format_prompt(
                                st.session_state.report_evidence_pack_raw, summary_block
                            )
                            try:
                                from anthropic import Anthropic
                                client = Anthropic(api_key=api_key)
                                response = client.messages.create(
                                    model="claude-opus-4-5-20251101",
                                    max_tokens=6000,
                                    temperature=0.2,
                                    messages=[{"role": "user", "content": prompt}],
                                )
                                text = response.content[0].text if response.content else ""
                                st.session_state.report_evidence_pack_md = text.strip()
                                st.session_state.report_evidence_pack_at = datetime.now().isoformat()
                                st.session_state.report_evidence_pack_status = "done"
                                quality = _extract_evidence_pack_quality(st.session_state.report_evidence_pack_md)
                                if quality.get("evidence_count", 0) == 0:
                                    st.warning(
                                        "Evidence Pack 생성 완료했지만 근거 문항이 없습니다. "
                                        "파싱 결과를 확인하고 필요한 자료를 보완해 주세요."
                                    )
                                else:
                                    st.success("Evidence Pack 생성 완료")
                                st.rerun()
                            except Exception as exc:
                                st.session_state.report_evidence_pack_status = "idle"
                                st.error(f"Evidence Pack 생성 실패: {exc}")

                if st.session_state.get("report_evidence_pack_raw"):
                    with st.expander("빠른 추출 결과(JSON)", expanded=False):
                        st.code(st.session_state.report_evidence_pack_raw, language="json")

        chapter_order = _init_report_chapters()
        if chapter_order:
            st.session_state.report_chapter_index = max(
                0,
                min(st.session_state.get("report_chapter_index", 0), len(chapter_order) - 1),
            )
            current_chapter = chapter_order[st.session_state.report_chapter_index]
            status = st.session_state.get("report_chapter_status", {}).get(current_chapter, "draft")
            st.caption(f"현재 챕터: {current_chapter} · 상태: {status} · "
                       f"{st.session_state.report_chapter_index + 1}/{len(chapter_order)}")
            st.progress((st.session_state.report_chapter_index + 1) / len(chapter_order))
        else:
            st.caption("목차 정보를 불러올 수 없습니다.")

        report_status_placeholder = st.empty()
        report_log_placeholder = st.empty()
        report_status_placeholder.markdown("⏳ 상태: 대기 중")
        report_log_placeholder.markdown("도구 로그: 없음")

        report_stream_placeholder = st.empty()
        existing = st.session_state.get("report_chapters", {}).get(current_chapter, "") if current_chapter else ""
        if existing and not st.session_state.get("report_edit_buffer"):
            st.session_state.report_edit_buffer = existing
        if not existing:
            report_stream_placeholder.markdown("초안이 생성되면 여기에 표시됩니다.")

        st.text_area(
            "편집",
            key="report_edit_buffer",
            height=280,
            placeholder="챕터 내용을 편집하세요.",
        )

        if chapter_order:
            btn_cols = st.columns(3)
            idx = st.session_state.get("report_chapter_index", 0)
            idx = max(0, min(idx, len(chapter_order) - 1))
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
                    if idx < len(chapter_order) - 1:
                        st.session_state.report_chapter_index = idx + 1
                        st.session_state.report_edit_buffer = st.session_state.report_chapters.get(
                            chapter_order[idx + 1], ""
                        )
                    st.rerun()
            with btn_cols[2]:
                if st.button("다음", use_container_width=True, disabled=idx >= len(chapter_order) - 1):
                    _save_current_chapter(mark_done=False)
                    st.session_state.report_chapter_index = min(len(chapter_order) - 1, idx + 1)
                    st.session_state.report_edit_buffer = st.session_state.report_chapters.get(
                        chapter_order[st.session_state.report_chapter_index], ""
                    )
                    st.rerun()

with chat_col:
    # ========================================
    # Welcome 화면 (메시지가 없을 때만 표시)
    # ========================================
    if not st.session_state.unified_messages:
        st.markdown("""
        <div class="welcome-screen">
            <div class="welcome-screen__title">무엇을 도와드릴까요?</div>
            <div class="welcome-screen__subtitle">
                투자 분석, 기업 진단, 계약서 검토 등 다양한 기능을 자연스러운 대화로 이용하세요
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 기능 Pills
        st.markdown("### 주요 기능")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Exit 프로젝션", key="pill_exit", use_container_width=True):
                st.session_state.quick_cmd = "투자검토 엑셀 파일을 분석해서 Exit 프로젝션을 만들어줘"
                st.rerun()

        with col2:
            if st.button("Peer PER 분석", key="pill_peer", use_container_width=True):
                st.session_state.quick_cmd = "유사기업 PER을 비교 분석해줘"
                st.rerun()

        with col3:
            if st.button("기업 진단", key="pill_diagnosis", use_container_width=True):
                st.session_state.quick_cmd = "진단시트를 분석하고 컨설턴트 보고서를 작성해줘"
                st.rerun()

        col4, col5, col6 = st.columns(3)
        with col4:
            if st.button("투자보고서", key="pill_report", use_container_width=True):
                st.session_state.report_panel_enabled = True
                st.session_state.unified_mode = "report"
                st.toast("투자보고서 모드가 활성화되었습니다.")
                st.rerun()

        with col5:
            if st.button("스타트업 발굴", key="pill_discovery", use_container_width=True):
                st.session_state.quick_cmd = "정책 PDF를 분석해서 유망 산업을 추천해줘"
                st.rerun()

        with col6:
            if st.button("계약서 검토", key="pill_contract", use_container_width=True):
                st.session_state.quick_cmd = "계약서를 분석하고 주요 조항을 검토해줘"
                st.rerun()

        col7, col8 = st.columns(2)
        with col7:
            if st.button("팀 협업", key="pill_collab", use_container_width=True):
                st.session_state.quick_cmd = "팀 과업 현황을 보여줘"
                st.rerun()

        with col8:
            if st.button("공공입찰 검색", key="pill_bid", use_container_width=True):
                st.session_state.quick_cmd = "나라장터에서 관련 입찰 공고를 찾아줘"
                st.rerun()

    # ========================================
    # 대화 영역
    # ========================================
    chat_container = st.container()

    with chat_container:
        for msg in st.session_state.unified_messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            tool_logs = msg.get("tool_logs", [])

            if role == "user":
                with st.chat_message("user", avatar=user_avatar_image):
                    st.markdown(content)

            elif role == "system":
                # 시스템 메시지 (대화 요약)
                st.markdown(f"""
                <div class="system-message">
                    <strong>📝 {content.split(']')[0]}]</strong>
                    <div style="margin-top: 0.5rem; color: var(--text-secondary);">
                        {content.split(']', 1)[1] if ']' in content else content}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            elif role == "assistant":
                with st.chat_message("assistant", avatar=avatar_image):
                    # Tool logs 표시
                    if tool_logs:
                        for log in tool_logs:
                            if log.startswith("**도구:"):
                                # Tool execution 카드
                                tool_name = log.replace("**도구:", "").replace("**", "").strip()
                                st.markdown(f"""
                                <div class="tool-card tool-card--running">
                                    <div class="tool-card__header">
                                        {tool_name}
                                        <div class="tool-spinner"></div>
                                    </div>
                                    <div class="tool-card__body">
                                        실행 중...
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

                    st.markdown(content)

                    # Tool logs expander
                    if tool_logs:
                        with st.expander("실행 로그", expanded=False):
                            for line in tool_logs:
                                st.caption(line)

    # Auto-scroll to bottom
    if st.session_state.unified_messages:
        st.markdown("""
        <script>
        window.scrollTo(0, document.body.scrollHeight);
        </script>
        """, unsafe_allow_html=True)

# ========================================
# 하단 고정 영역: 파일 첨부 + 채팅 입력
# ========================================

    # 첨부된 파일 표시 (하단 고정)
    if st.session_state.unified_files:
        st.markdown('<div class="fixed-file-area">', unsafe_allow_html=True)
        for i, fpath in enumerate(st.session_state.unified_files):
            fname = Path(fpath).name
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(f"""
                <div class="file-chip">
                    {fname}
                </div>
                """, unsafe_allow_html=True)
            with col2:
                if st.button("×", key=f"remove_{i}", help="제거"):
                    removed_path = st.session_state.unified_files.pop(i)
                    try:
                        removed_name = Path(removed_path).name
                        removed_size = Path(removed_path).stat().st_size
                        removed_key = f"{removed_name}|{removed_size}"
                        processed_keys = set(st.session_state.get("processed_upload_keys", []))
                        if removed_key in processed_keys:
                            processed_keys.remove(removed_key)
                            st.session_state.processed_upload_keys = sorted(processed_keys)
                    except FileNotFoundError:
                        pass
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # 파일 첨부 버튼
    with st.expander("파일 첨부", expanded=False):
        uploader_key = f"unified_file_uploader_{st.session_state.uploader_key_seed}"
        uploaded_files = st.file_uploader(
            "분석할 파일을 선택하세요 (PDF, 엑셀, DOCX)",
            type=["pdf", "xlsx", "xls", "docx", "doc"],
            accept_multiple_files=True,
            key=uploader_key,
            help="투자검토 엑셀, 기업소개서 PDF, 진단시트, 계약서 등 모든 파일을 지원합니다"
        )

        if uploaded_files:
            processed_keys = set(st.session_state.get("processed_upload_keys", []))
            new_upload_processed = False
            for uploaded_file in uploaded_files:
                upload_key = f"{uploaded_file.name}|{uploaded_file.size}"
                if upload_key in processed_keys:
                    continue
                processed_keys.add(upload_key)
                # PDF 파일인 경우 로딩바 표시
                if uploaded_file.name.lower().endswith('.pdf'):
                    import time

                    # 로딩바 표시
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    status_text.text(f"📄 {uploaded_file.name} 업로드 중...")

                    # 30초 동안 진행
                    for percent in range(101):
                        time.sleep(0.3)  # 30초 = 100 * 0.3
                        progress_bar.progress(percent)
                        if percent < 100:
                            status_text.text(f"📄 {uploaded_file.name} 업로드 중... {percent}%")

                    # 파일 저장
                    file_path = save_uploaded_file(uploaded_file)

                    if file_path and file_path not in st.session_state.unified_files:
                        st.session_state.unified_files.append(file_path)
                        new_upload_processed = True
                        progress_bar.empty()
                        status_text.empty()

                        # 완료 토스트
                        st.toast(f"✅ {uploaded_file.name} 업로드 완료", icon="✅")

                        # 주의 문구 표시
                        st.warning(f"⚠️ **{uploaded_file.name}** 업로드가 완료되었습니다. 이제 파일 분석을 요청하실 수 있습니다.", icon="⚠️")
                        time.sleep(2)  # 2초간 표시
                else:
                    # PDF가 아닌 파일은 즉시 업로드
                    file_path = save_uploaded_file(uploaded_file)
                    if file_path and file_path not in st.session_state.unified_files:
                        st.session_state.unified_files.append(file_path)
                        st.toast(f"{uploaded_file.name} 업로드 완료")
                        new_upload_processed = True

            st.session_state.processed_upload_keys = sorted(processed_keys)
            if new_upload_processed:
                st.session_state.uploader_key_seed += 1
                st.rerun()

    # 채팅 입력
    user_input = st.chat_input("메시지를 입력하세요...", key="unified_chat_input")

with chat_col:
    # 빠른 명령어 처리
    if "quick_cmd" in st.session_state:
        user_input = st.session_state.quick_cmd
        del st.session_state.quick_cmd

    # 메시지 처리
    if user_input:
        # 파일 컨텍스트 추가
        context_info = ""
        if st.session_state.unified_files:
            paths_str = ", ".join(st.session_state.unified_files)
            if "파일" not in user_input and "분석" not in user_input:
                context_info = f"\n[업로드된 파일: {paths_str}]"

        full_message = user_input + context_info
        st.session_state.unified_messages.append({"role": "user", "content": user_input})

        if st.session_state.get("report_panel_enabled"):
            has_files = bool(st.session_state.unified_files)
            has_md = bool(st.session_state.get("report_evidence_pack_md"))
            if not has_files and not has_md:
                guidance = (
                    "투자심사 보고서를 이어서 작성하려면 자료가 필요합니다.\n"
                    "- 방법 1: 오른쪽 패널에서 파일을 드래그앤드롭 후 ‘완료(일괄 파싱)’\n"
                    "- 방법 2: Evidence Pack MD를 업로드하여 바로 이어쓰기\n"
                    "필요한 자료를 업로드하면 즉시 계속 작성할 수 있습니다."
                )
                st.session_state.unified_messages.append({
                    "role": "assistant",
                    "content": guidance,
                    "tool_logs": [],
                })
                if report_stream_placeholder is not None:
                    report_stream_placeholder.markdown(guidance)
                if report_status_placeholder is not None:
                    report_status_placeholder.markdown("ℹ️ 상태: 자료 필요")
                st.rerun()

        report_context_text = None
        if st.session_state.get("report_panel_enabled") and chapter_order:
            idx = st.session_state.get("report_chapter_index", 0)
            idx = max(0, min(idx, len(chapter_order) - 1))
            current_chapter = chapter_order[idx]
            file_context = ""
            if st.session_state.unified_files:
                file_context = f"업로드 파일: {', '.join(st.session_state.unified_files)}"
            preparse_context = _build_preparse_context(
                st.session_state.get("report_preparse_summary", [])
            )
            report_context_text = "\n".join(filter(None, [
                file_context,
                preparse_context,
                (
                    "[Evidence Pack MD]\n"
                    + st.session_state.report_evidence_pack_md
                )
                if st.session_state.get("report_evidence_pack_md") else None,
                f"현재 작성 챕터: {current_chapter}.\n"
                "이 챕터만 작성하고 다른 챕터는 출력하지 마세요.\n"
                "형식: ### 챕터 제목 → 요약/근거/심사 판단 포함.\n"
                "마지막에 ### 검증 로그(해당 챕터) 포함.",
            ]))

        with chat_container:
            with st.chat_message("assistant", avatar=avatar_image):
                response_placeholder = st.empty()

                agent = st.session_state.agent

                try:
                    if len(st.session_state.unified_messages) >= 15:
                        with st.status("📝 대화 내용 요약 중...", expanded=True) as status:
                            status.write("💬 15개 이상의 메시지를 압축하고 있습니다.")
                            status.write("⏳ Claude Haiku API로 이전 대화를 요약하는 중입니다...")
                            status.write("🔒 잠시만 기다려주세요. (중복 요청 방지)")

                            api_key = st.session_state.get("user_api_key", "")
                            compacted_messages, success = compact_conversation(
                                st.session_state.unified_messages,
                                api_key
                            )
                            st.session_state.unified_messages = compacted_messages

                            if success:
                                status.update(label="✅ 대화 요약 완료!", state="complete", expanded=False)
                                st.toast("대화가 길어져 이전 내용을 요약했습니다", icon="📝")
                            else:
                                status.update(label="⚠️ 요약 실패 (기존 방식 사용)", state="error", expanded=False)

                    if st.session_state.get("report_panel_enabled"):
                        tool_logs = []

                        async def stream_response():
                            full_response = ""
                            log_lines = []
                            if report_status_placeholder is not None:
                                report_status_placeholder.markdown("🟡 상태: 작성 중...")
                            async for chunk in agent.chat(
                                full_message,
                                mode=st.session_state.get("unified_mode", "report"),
                                context_text=report_context_text,
                                model_override="claude-opus-4-5-20251101",
                            ):
                                if "**도구:" in chunk:
                                    tool_logs.append(chunk.strip())
                                    log_lines.append(chunk.strip())
                                    if report_log_placeholder is not None:
                                        report_log_placeholder.markdown(
                                            "도구 로그:\n" + "\n".join([f"- {line}" for line in log_lines])
                                        )
                                else:
                                    full_response += chunk
                                    response_placeholder.markdown(full_response + "▌")
                                    if report_stream_placeholder is not None:
                                        report_stream_placeholder.markdown(full_response + "▌")
                            response_placeholder.markdown(full_response)
                            if report_stream_placeholder is not None:
                                report_stream_placeholder.markdown(full_response)
                            if not full_response.strip():
                                fallback_lines = [
                                    "초안 생성에 실패했습니다.",
                                    "도구 실행 결과가 비어 있거나 파싱이 실패한 것으로 보입니다.",
                                    "조치: 파싱 모드를 Hybrid/빠른 파싱으로 변경하거나, 시장근거 추출을 끈 뒤 다시 시도하세요.",
                                ]
                                if tool_logs:
                                    fallback_lines.append("")
                                    fallback_lines.append("도구 로그(요약):")
                                    for line in tool_logs[-6:]:
                                        cleaned = line.replace("**", "").strip()
                                        fallback_lines.append(f"- {cleaned}")
                                full_response = "\n".join(fallback_lines)
                                response_placeholder.markdown(full_response)
                                if report_stream_placeholder is not None:
                                    report_stream_placeholder.markdown(full_response)
                                if report_status_placeholder is not None:
                                    report_status_placeholder.markdown("⚠️ 상태: 작성 실패")
                            else:
                                if report_status_placeholder is not None:
                                    report_status_placeholder.markdown("✅ 상태: 작성 완료")
                            return full_response

                        full_response = asyncio.run(stream_response())
                    else:
                        with st.spinner("🤖 생각 중..."):
                            full_response = agent.chat_sync(
                                full_message,
                                mode=st.session_state.get("unified_mode", "unified"),
                            )
                            tool_logs = []
                except Exception as e:
                    full_response = f"오류가 발생했습니다: {str(e)}"
                    tool_logs = []

                response_placeholder.markdown(full_response)

                st.session_state.unified_messages.append({
                    "role": "assistant",
                    "content": full_response,
                    "tool_logs": tool_logs
                })

                if st.session_state.get("report_panel_enabled") and chapter_order:
                    st.session_state.report_chapters[current_chapter] = full_response
                    st.session_state.report_edit_buffer = full_response
                    st.session_state.report_chapter_status[current_chapter] = "draft"
                    st.session_state.report_draft_content = _compose_full_draft(
                        st.session_state.report_chapters,
                        chapter_order,
                    )

                try:
                    current_team = st.session_state.get("current_team", "CIC 봄날")
                    current_conv_id = st.session_state.get("current_conversation_id")
                    new_conv_id = save_conversation(
                        current_team,
                        st.session_state.unified_messages,
                        conversation_id=current_conv_id
                    )
                    if not current_conv_id and new_conv_id:
                        st.session_state.current_conversation_id = new_conv_id
                except Exception as e:
                    logger.warning(f"대화 자동 저장 실패: {e}")

        st.rerun()

# ========================================
# 팁 로테이션 배너
# ========================================
st.markdown("""
<div class="loading-tips-banner">
    <span class="loading-tips-banner__icon">💡</span>
    <div class="loading-tips-banner__text"></div>
</div>

<script>
// 팁 목록
const tips = [
    "💡 200개 한 번에 출력해달라고 하지 마세요. 최근 3-4개의 대화를 기억하고 있어서 최대 20만 토큰까지만 응답이 가능합니다.",
    "📁 파일을 먼저 업로드한 후 분석을 요청하면 더 정확한 결과를 얻을 수 있습니다.",
    "🎯 복잡한 요청은 단계별로 나누어 주시면 더 빠르게 처리할 수 있습니다.",
    "🔍 포트폴리오 조회 시 구체적인 키워드를 사용하면 검색 정확도가 높아집니다.",
    "📊 Exit 프로젝션은 투자검토 엑셀 파일이 필요합니다.",
    "🏢 Peer 분석은 기업소개서 PDF를 첨부해주세요.",
    "💬 최근 대화만 기억하므로, 이전 내용을 참조하려면 다시 언급해주세요.",
    "⚡ 대화가 15개 이상 쌓이면 자동으로 이전 내용을 요약합니다.",
    "🎨 '새 대화' 버튼으로 언제든 대화를 초기화할 수 있습니다."
];

let currentTipIndex = 0;

function rotateTips() {
    const tipElement = document.querySelector('.loading-tips-banner__text');
    if (tipElement) {
        // Fade out
        tipElement.style.opacity = '0';

        setTimeout(() => {
            // Change text
            tipElement.textContent = tips[currentTipIndex];
            currentTipIndex = (currentTipIndex + 1) % tips.length;

            // Fade in
            tipElement.style.opacity = '1';
        }, 500);
    }
}

// 페이지 로드 시 즉시 첫 번째 팁 표시
setTimeout(() => {
    const tipElement = document.querySelector('.loading-tips-banner__text');
    if (tipElement) {
        tipElement.textContent = tips[0];
        tipElement.style.opacity = '1';
        currentTipIndex = 1;
    }
}, 100);

// 7초마다 팁 변경
setInterval(rotateTips, 7000);
</script>
""", unsafe_allow_html=True)

# ========================================
# 푸터
# ========================================
st.markdown("""
<div style="text-align: center; color: #9ca3af; font-size: 0.75rem; margin-top: 4rem; padding: 2rem 0; margin-bottom: 3rem;">
    Powered by Claude Opus 4.5 | 메리 VC 에이전트 v2.0
</div>
""", unsafe_allow_html=True)
