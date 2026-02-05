"""
Contract review helpers for Term Sheet / Investment Agreement (KR)
- Text extraction (PDF/DOCX)
- Field extraction + evidence snippets
- Clause checklist detection
- Cross-document consistency checks
"""

from __future__ import annotations

import re
import base64
import io
import json
import math
from pathlib import Path
from collections import Counter
from typing import Callable, Dict, List, Optional

from shared.logging_config import get_logger

logger = get_logger("contract_review")

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    from docx import Document
except Exception:
    Document = None

try:
    from PIL import Image
except Exception:
    Image = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from anthropic import Anthropic
except Exception:
    Anthropic = None


FIELD_DEFINITIONS = [
    {
        "name": "company_name",
        "label": "회사명",
        "type": "company",
        "patterns": [
            r"(회사명|발행회사|발행인)\s*[:：]?\s*(?P<value>[^\n\r]+)",
            r"(주식회사|유한회사)\s*(?P<value>[가-힣A-Za-z0-9\(\)\s㈜]+)",
        ],
    },
    {
        "name": "investor_name",
        "label": "투자자",
        "type": "company",
        "patterns": [
            r"(투자자|투자기관|인수인|매수인)\s*[:：]?\s*(?P<value>[^\n\r]+)",
        ],
    },
    {
        "name": "investment_amount",
        "label": "투자금액",
        "type": "amount",
        "patterns": [
            r"(투자금액|투자금|총\s*투자금액|투자대금|매수대금)\s*[:：]?\s*(?P<value>[0-9,\.\s억천만만원원]+)",
        ],
    },
    {
        "name": "pre_money",
        "label": "Pre-money",
        "type": "amount",
        "patterns": [
            r"(Pre\-?Money|투자\s*전\s*기업가치|투자\s*전\s*가치)\s*[:：]?\s*(?P<value>[0-9,\.\s억천만만원원]+)",
        ],
    },
    {
        "name": "post_money",
        "label": "Post-money",
        "type": "amount",
        "patterns": [
            r"(Post\-?Money|투자\s*후\s*기업가치|투자\s*후\s*가치)\s*[:：]?\s*(?P<value>[0-9,\.\s억천만만원원]+)",
        ],
    },
    {
        "name": "share_price",
        "label": "주당 발행가",
        "type": "amount",
        "patterns": [
            r"(주당\s*발행가|주당\s*가격|주당\s*인수가|발행가|인수가)\s*[:：]?\s*(?P<value>[0-9,\.\s원]+)",
        ],
    },
    {
        "name": "share_count",
        "label": "주식수",
        "type": "count",
        "patterns": [
            r"(발행\s*주식수|매수\s*주식수|인수\s*주식수|주식수)\s*[:：]?\s*(?P<value>[0-9,\s]+)주",
        ],
    },
    {
        "name": "closing_date",
        "label": "종결일",
        "type": "date",
        "patterns": [
            r"(거래\s*종결일|종결일|Closing\s*Date|체결일|계약일)\s*[:：]?\s*(?P<value>[^\n\r]+)",
        ],
    },
    {
        "name": "governing_law",
        "label": "준거법",
        "type": "text",
        "patterns": [
            r"(준거법|Governing\s*Law)\s*[:：]?\s*(?P<value>[^\n\r]+)",
        ],
    },
]

CLAUSE_TAXONOMY = {
    "term_sheet": [
        {"id": "investment_amount", "label": "투자금액", "keywords": ["투자금액", "투자금", "총 투자금액"]},
        {"id": "valuation", "label": "기업가치", "keywords": ["기업가치", "pre-money", "post-money", "투자 전", "투자 후"]},
        {"id": "price", "label": "주당 발행가", "keywords": ["주당", "발행가", "인수가"]},
        {"id": "liquidation", "label": "청산우선권", "keywords": ["청산우선", "liquidation preference"]},
        {"id": "anti_dilution", "label": "희석방지", "keywords": ["희석", "anti-dilution", "anti dilution"]},
        {"id": "option_pool", "label": "스톡옵션 풀", "keywords": ["스톡옵션", "옵션풀", "option pool"]},
        {"id": "board", "label": "이사회", "keywords": ["이사회", "board"]},
        {"id": "info_rights", "label": "정보권", "keywords": ["정보권", "보고", "information rights"]},
        {"id": "pro_rata", "label": "우선참여", "keywords": ["우선참여", "pro rata"]},
        {"id": "closing_conditions", "label": "종결조건", "keywords": ["종결조건", "conditions precedent", "CP"]},
        {"id": "confidentiality", "label": "비밀유지", "keywords": ["비밀", "confidential"]},
        {"id": "exclusivity", "label": "독점협상", "keywords": ["독점", "exclusivity"]},
        {"id": "governing_law", "label": "준거법", "keywords": ["준거법", "governing law"]},
        {"id": "non_binding", "label": "구속력", "keywords": ["구속", "비구속", "binding", "non-binding"]},
    ],
    "investment_agreement": [
        {"id": "representations", "label": "진술 및 보장", "keywords": ["진술", "보장", "representations", "warranties"]},
        {"id": "conditions", "label": "선행조건", "keywords": ["선행조건", "conditions precedent", "CP"]},
        {"id": "covenants", "label": "약정", "keywords": ["약정", "covenant"]},
        {"id": "indemnification", "label": "면책/보상", "keywords": ["면책", "보상", "indemn"]},
        {"id": "dispute", "label": "분쟁해결", "keywords": ["분쟁", "중재", "재판", "dispute", "arbitration"]},
        {"id": "governing_law", "label": "준거법", "keywords": ["준거법", "governing law"]},
        {"id": "confidentiality", "label": "비밀유지", "keywords": ["비밀", "confidential"]},
        {"id": "assignment", "label": "양도금지", "keywords": ["양도", "transfer", "assignment"]},
        {"id": "transfer_restriction", "label": "지분양도 제한", "keywords": ["지분", "양도 제한", "transfer restriction"]},
        {"id": "rofr", "label": "우선매수권/우선협상권", "keywords": ["우선매수", "우선협상", "ROFR", "ROFO"]},
        {"id": "drag_tag", "label": "동반매도/매수청구", "keywords": ["동반매도", "매수청구", "drag", "tag"]},
        {"id": "liquidation", "label": "청산우선권", "keywords": ["청산우선", "liquidation preference"]},
        {"id": "anti_dilution", "label": "희석방지", "keywords": ["희석", "anti-dilution", "anti dilution"]},
        {"id": "protective", "label": "보호조항", "keywords": ["보호", "protective provisions", "동의사항"]},
        {"id": "board", "label": "이사회", "keywords": ["이사회", "board"]},
        {"id": "info_rights", "label": "정보권", "keywords": ["정보권", "보고", "information rights"]},
    ],
}

FIELD_LABEL_TO_NAME = {field["label"]: field["name"] for field in FIELD_DEFINITIONS}

MASK_TOKEN_MAP = {
    "company_name": "[COMPANY]",
    "investor_name": "[INVESTOR]",
    "investment_amount": "[AMOUNT]",
    "pre_money": "[AMOUNT]",
    "post_money": "[AMOUNT]",
    "share_price": "[AMOUNT]",
    "share_count": "[COUNT]",
    "closing_date": "[DATE]",
    "governing_law": "[MASKED]",
}

OCR_DEFAULT_MODEL = "claude-opus-4-5-20251101"
OCR_DEFAULT_DPI = 200
OCR_DENSITY_DPI = 36
OCR_FAST_DPI = 150
OCR_FAST_LANG = "kor+eng"
OCR_MIN_CHARS_PER_PAGE = 200
OCR_SINGLE_HANGUL_RATIO_THRESHOLD = 0.35
OCR_SYMBOL_RATIO_THRESHOLD = 0.02
OCR_PROMPT = (
    "You are a precise OCR engine. Extract all visible text from the image. "
    "Preserve reading order. Output plain text only with line breaks. "
    "Do not summarize or add commentary."
)

OCR_REFINE_PROMPT = (
    "You are an OCR cleanup engine for Korean legal documents. "
    "Fix spacing, broken characters, and obvious OCR artifacts while preserving the original meaning. "
    "Do NOT add, remove, or interpret content. Keep numbers, dates, and clause numbering. "
    "Return plain text only."
)

SEVERITY_ORDER = ["높음", "중간", "낮음", "정보"]

FIELD_SEVERITY = {
    "company_name": "높음",
    "investor_name": "중간",
    "investment_amount": "높음",
    "pre_money": "중간",
    "post_money": "중간",
    "share_price": "중간",
    "share_count": "중간",
    "closing_date": "낮음",
    "governing_law": "낮음",
}

CLAUSE_SEVERITY = {
    "term_sheet": {
        "investment_amount": "높음",
        "valuation": "중간",
        "price": "중간",
        "liquidation": "중간",
        "anti_dilution": "중간",
        "board": "낮음",
        "info_rights": "낮음",
        "governing_law": "낮음",
        "non_binding": "중간",
    },
    "investment_agreement": {
        "representations": "높음",
        "conditions": "중간",
        "covenants": "중간",
        "indemnification": "중간",
        "transfer_restriction": "중간",
        "protective": "중간",
        "liquidation": "중간",
        "anti_dilution": "중간",
        "board": "낮음",
        "info_rights": "낮음",
        "governing_law": "낮음",
    },
}

SECTION_HEADING_PATTERN = re.compile(r"(제\\s*\\d+\\s*조|Article\\s*\\d+)", re.IGNORECASE)

SENSITIVE_PATTERNS = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}"), "[EMAIL]"),
    (re.compile(r"\\b(01[016789])[-.\\s]?\\d{3,4}[-.\\s]?\\d{4}\\b"), "[PHONE]"),
    (re.compile(r"\\b0\\d{1,2}[-.\\s]?\\d{3,4}[-.\\s]?\\d{4}\\b"), "[PHONE]"),
    (re.compile(r"\\b\\d{6}-\\d{7}\\b"), "[ID]"),
    (re.compile(r"\\b\\d{3}-\\d{2}-\\d{5}\\b"), "[BIZ_ID]"),
    (re.compile(r"\\b\\d{13}\\b"), "[ID]"),
    (re.compile(r"\\b\\d{2,6}-\\d{2,6}-\\d{2,6}\\b"), "[ACCOUNT]"),
    (re.compile(r"\\b\\d{4}[./-]\\d{1,2}[./-]\\d{1,2}\\b"), "[DATE]"),
    (re.compile(r"\\d{4}\\s*년\\s*\\d{1,2}\\s*월\\s*\\d{1,2}\\s*일"), "[DATE]"),
    (re.compile(r"[0-9][0-9,\\.]*\\s*(원|억원|만원|천만원|십억원|KRW|USD|US\\$|\\$)"), "[AMOUNT]"),
]

ADDRESS_LABEL_PATTERN = re.compile(r"(주소|Address)\\s*[:：]?\\s*([^\\n\\r]+)", re.IGNORECASE)
PERSON_LABEL_PATTERN = re.compile(r"(대표이사|대표|담당자|성명)\\s*[:：]?\\s*([^\\n\\r]+)")


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.strip().split())


def _normalize_company_name(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", "", text)
    text = text.replace("주식회사", "").replace("유한회사", "")
    text = text.replace("(주)", "").replace("㈜", "")
    return text


def _count_symbol_ratio(text: str) -> float:
    if not text:
        return 1.0
    symbols = text.count("●") + text.count("■") + text.count("□") + text.count("�")
    return symbols / max(1, len(text))


def _tokenize_text(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9가-힣]+", text.lower())


def _extract_section_title(text: str) -> str:
    match = SECTION_HEADING_PATTERN.search(text or "")
    return match.group(1) if match else ""


def _single_hangul_ratio(text: str) -> float:
    tokens = [t for t in re.split(r"\s+", text) if t]
    if not tokens:
        return 1.0
    hangul_tokens = [t for t in tokens if re.search(r"[가-힣]", t)]
    if not hangul_tokens:
        return 0.0
    single_hangul = sum(1 for t in hangul_tokens if len(t) == 1 and re.match(r"[가-힣]", t))
    return single_hangul / max(1, len(hangul_tokens))


def _needs_ocr(segments: List[Dict[str, str]], page_count: int) -> bool:
    if page_count <= 0:
        return False
    full_text = "\n".join(seg.get("text", "") for seg in segments if seg.get("text"))
    if not full_text.strip():
        return True
    if len(full_text.strip()) < OCR_MIN_CHARS_PER_PAGE * page_count:
        return True
    if _single_hangul_ratio(full_text) >= OCR_SINGLE_HANGUL_RATIO_THRESHOLD:
        return True
    if _count_symbol_ratio(full_text) >= OCR_SYMBOL_RATIO_THRESHOLD:
        return True
    return False


def _token_label(token: str) -> str:
    label = token.strip("[]")
    return label or "MASKED"


def build_mask_replacements(field_sets: List[Dict[str, Dict[str, object]]]) -> Dict[str, str]:
    replacements: Dict[str, str] = {}
    counters: Dict[str, int] = {}

    for fields in field_sets:
        if not fields:
            continue
        for field in FIELD_DEFINITIONS:
            entry = fields.get(field["name"])
            if not entry:
                continue
            value = entry.get("value")
            if value is None:
                continue
            normalized = _normalize_whitespace(str(value))
            if not normalized or normalized in replacements:
                continue
            base_token = MASK_TOKEN_MAP.get(field["name"], "[MASKED]")
            label = _token_label(base_token)
            counters[label] = counters.get(label, 0) + 1
            replacements[normalized] = f"[{label}_{counters[label]}]"

    return replacements


def _mask_label_value(text: str, pattern: re.Pattern[str], token: str) -> str:
    def _repl(match: re.Match[str]) -> str:
        label = match.group(1).strip()
        return f"{label}: {token}"

    return pattern.sub(_repl, text)


def mask_sensitive_text(text: str, replacements: Optional[Dict[str, str]] = None) -> str:
    if not text:
        return ""

    masked = text
    if replacements:
        for original in sorted(replacements, key=len, reverse=True):
            if original:
                masked = masked.replace(original, replacements[original])

    masked = _mask_label_value(masked, ADDRESS_LABEL_PATTERN, "[ADDRESS]")
    masked = _mask_label_value(masked, PERSON_LABEL_PATTERN, "[PERSON]")

    for pattern, token in SENSITIVE_PATTERNS:
        masked = pattern.sub(token, masked)

    return masked


def mask_field_value(value: Optional[str], replacements: Optional[Dict[str, str]] = None) -> str:
    if value is None:
        return ""
    normalized = _normalize_whitespace(str(value))
    return mask_sensitive_text(normalized, replacements)


def mask_analysis(doc: Dict[str, object], replacements: Dict[str, str]) -> Dict[str, object]:
    if not doc:
        return {}

    masked_doc = dict(doc)
    fields = doc.get("fields", {}) if isinstance(doc.get("fields"), dict) else {}
    masked_fields: Dict[str, Dict[str, object]] = {}
    for name, entry in fields.items():
        if not isinstance(entry, dict):
            continue
        masked_entry = dict(entry)
        masked_entry["value"] = mask_field_value(entry.get("value"), replacements)
        masked_entry["snippet"] = mask_sensitive_text(entry.get("snippet", ""), replacements)
        masked_fields[name] = masked_entry
    masked_doc["fields"] = masked_fields

    clauses = doc.get("clauses", []) if isinstance(doc.get("clauses"), list) else []
    masked_clauses = []
    for clause in clauses:
        if not isinstance(clause, dict):
            continue
        masked_clause = dict(clause)
        masked_clause["snippet"] = mask_sensitive_text(clause.get("snippet", ""), replacements)
        masked_clauses.append(masked_clause)
    masked_doc["clauses"] = masked_clauses

    return masked_doc


def mask_comparisons(comparisons: List[Dict[str, object]], replacements: Dict[str, str]) -> List[Dict[str, object]]:
    masked = []
    for entry in comparisons:
        if not isinstance(entry, dict):
            continue
        masked_entry = dict(entry)
        masked_entry["term_sheet"] = mask_field_value(entry.get("term_sheet"), replacements)
        masked_entry["investment_agreement"] = mask_field_value(entry.get("investment_agreement"), replacements)
        masked_entry["note"] = mask_sensitive_text(entry.get("note", ""), replacements)
        masked.append(masked_entry)
    return masked


def mask_search_hits(hits: List[Dict[str, str]], replacements: Dict[str, str]) -> List[Dict[str, str]]:
    masked_hits = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        masked_hits.append({
            "source": hit.get("source"),
            "snippet": mask_sensitive_text(hit.get("snippet", ""), replacements),
        })
    return masked_hits


def _clause_label_map(doc_type: str) -> Dict[str, str]:
    taxonomy = CLAUSE_TAXONOMY.get(doc_type, [])
    return {entry["id"]: entry["label"] for entry in taxonomy}


def build_review_opinion(
    term_sheet: Optional[Dict[str, object]],
    investment_agreement: Optional[Dict[str, object]],
    comparisons: List[Dict[str, object]],
) -> Dict[str, object]:
    items: List[Dict[str, str]] = []
    questions: List[str] = []

    def _add_item(severity: str, issue: str, detail: str = "", action: str = "") -> None:
        items.append({
            "severity": severity,
            "issue": issue,
            "detail": detail,
            "action": action,
        })

    if not term_sheet and not investment_agreement:
        return {
            "summary": ["업로드된 문서가 없습니다."],
            "items": [],
            "questions": [],
        }

    if not comparisons:
        missing = []
        if not term_sheet:
            missing.append("텀싯")
        if not investment_agreement:
            missing.append("투자계약서")
        uploaded = []
        if term_sheet:
            uploaded.append("텀싯")
        if investment_agreement:
            uploaded.append("투자계약서")
        detail = "한쪽 문서만 업로드되어 비교할 수 없습니다."
        if missing:
            detail = f"업로드된 문서: {', '.join(uploaded) if uploaded else '없음'} / 추가 필요: {', '.join(missing)}"
        _add_item("정보", "문서 간 비교 미수행", detail, "두 문서를 모두 업로드하세요.")

    for comp in comparisons:
        status = comp.get("status")
        if status in ("일치", "-"):
            continue
        label = comp.get("field", "")
        field_name = FIELD_LABEL_TO_NAME.get(label, "")
        severity = FIELD_SEVERITY.get(field_name, "중간")
        if status == "불일치":
            _add_item(
                "높음" if severity == "높음" else "중간",
                f"{label} 불일치",
                f"텀싯: {comp.get('term_sheet', '')} / 투자계약서: {comp.get('investment_agreement', '')}",
                "두 문서의 기준값을 합의해 일치시키세요.",
            )
            questions.append(f"{label}의 최종 확정 값은 무엇인가요?")
        elif status == "누락":
            _add_item(
                severity,
                f"{label} 누락",
                "한쪽 문서에만 기재됨",
                "누락된 문서에도 동일 조건을 반영하세요.",
            )
            questions.append(f"{label}이(가) 누락된 문서에 동일 조건을 반영할까요?")
        elif status == "검토 필요":
            _add_item(
                "중간",
                f"{label} 파싱 실패",
                comp.get("note", "파싱 오류"),
                "원문을 직접 확인하세요.",
            )
            questions.append(f"{label} 표기가 원문에서 어떻게 되어 있나요?")

    for doc, doc_type, label in (
        (term_sheet, "term_sheet", "텀싯"),
        (investment_agreement, "investment_agreement", "투자계약서"),
    ):
        if not doc:
            continue
        clause_map = _clause_label_map(doc_type)
        present_map = {entry.get("id"): entry.get("present") for entry in doc.get("clauses", []) if isinstance(entry, dict)}
        for clause_id, severity in CLAUSE_SEVERITY.get(doc_type, {}).items():
            if not present_map.get(clause_id):
                clause_label = clause_map.get(clause_id, clause_id)
                _add_item(
                    severity,
                    f"{label}에서 {clause_label} 조항 미확인",
                    "조항 존재 여부 확인 필요",
                    "해당 조항이 실제로 포함되어 있는지 확인하세요.",
                )
                questions.append(f"{label}의 {clause_label} 조항은 포함되어 있나요?")

        if doc.get("ocr_error"):
            _add_item(
                "중간",
                f"{label} OCR 실패",
                doc.get("ocr_error", ""),
                "OCR 재시도 또는 텍스트 원본 업로드를 권장합니다.",
            )
        elif doc.get("ocr_used"):
            _add_item(
                "정보",
                f"{label} OCR 사용됨",
                "스캔본 처리로 일부 인식 오류 가능",
                "핵심 항목은 원문과 대조하세요.",
            )

    summary_counts = {severity: 0 for severity in SEVERITY_ORDER}
    for item in items:
        summary_counts[item["severity"]] = summary_counts.get(item["severity"], 0) + 1

    summary_lines = []
    for severity in SEVERITY_ORDER:
        count = summary_counts.get(severity, 0)
        if count:
            summary_lines.append(f"{severity} {count}건")
    if not summary_lines:
        summary_lines.append("중대한 이슈가 감지되지 않았습니다.")

    return {
        "summary": summary_lines,
        "items": items,
        "questions": questions[:6],
    }


def generate_contract_opinion_llm(
    opinion: Dict[str, object],
    api_key: str,
    model: str = OCR_DEFAULT_MODEL,
) -> str:
    if not Anthropic:
        raise ImportError("anthropic SDK가 필요합니다.")
    if not api_key:
        raise ValueError("Claude API 키가 필요합니다.")

    client = Anthropic(api_key=api_key)
    payload = json.dumps(opinion, ensure_ascii=False, indent=2)
    response = client.messages.create(
        model=model,
        max_tokens=900,
        temperature=0.2,
        messages=[
            {
                "role": "user",
                "content": (
                    "You are a legal review assistant for KR venture investment contracts. "
                    "Think step-by-step internally but only output the final answer. "
                    "Use ONLY the provided issues; do not invent. "
                    "Return output in Korean with the following sections:\n"
                    "1) 종합 의견 (2~4문장)\n"
                    "2) 핵심 리스크/이슈 (최대 5개, 심각도 포함)\n"
                    "3) 확인 질문 (최대 5개)\n\n"
                    f"입력 데이터(JSON):\n{payload}"
                ),
            }
        ],
    )
    return _extract_claude_text(response)


def _parse_korean_amount(text: str) -> Optional[int]:
    if not text:
        return None

    cleaned = text.replace(",", "").replace("원", "").strip()
    total = 0

    def _add_unit(pattern: str, multiplier: int):
        nonlocal total, cleaned
        match = re.search(pattern, cleaned)
        if match:
            value = float(match.group(1))
            total += int(value * multiplier)

    _add_unit(r"([0-9]+(?:\.[0-9]+)?)\s*억", 100_000_000)
    _add_unit(r"([0-9]+(?:\.[0-9]+)?)\s*천만", 10_000_000)
    _add_unit(r"([0-9]+(?:\.[0-9]+)?)\s*만", 10_000)

    if total > 0:
        return total

    digits = re.sub(r"[^0-9]", "", cleaned)
    if digits:
        try:
            return int(digits)
        except ValueError:
            return None
    return None


def _parse_count(text: str) -> Optional[int]:
    if not text:
        return None
    digits = re.sub(r"[^0-9]", "", text)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _build_snippet(segment_text: str, match_start: int, match_end: int, window: int = 80) -> str:
    start = max(match_start - window, 0)
    end = min(match_end + window, len(segment_text))
    snippet = segment_text[start:end]
    return _normalize_whitespace(snippet)


def _build_segments_from_pdf(path: Path) -> tuple[List[Dict[str, str]], int]:
    if not fitz:
        raise ImportError("PyMuPDF(fitz)가 필요합니다.")

    segments: List[Dict[str, str]] = []
    with fitz.open(path) as doc:
        page_count = doc.page_count
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            text = page.get_text("text")
            if not text:
                continue
            segments.append({"source": f"p{page_index + 1}", "text": text})
    return segments, page_count


def _build_segments_from_docx(path: Path) -> List[Dict[str, str]]:
    if not Document:
        raise ImportError("python-docx가 필요합니다.")

    segments: List[Dict[str, str]] = []
    doc = Document(path)
    for idx, paragraph in enumerate(doc.paragraphs, start=1):
        text = paragraph.text
        if not text:
            continue
        segments.append({"source": f"para{idx}", "text": text})
    return segments


def _source_sort_key(source: Optional[str]) -> tuple:
    if not source:
        return (2, "")
    if source.startswith("p"):
        try:
            return (0, int(source[1:]))
        except ValueError:
            return (0, 0)
    return (1, source)


def _merge_segments_by_source(
    base_segments: List[Dict[str, str]],
    override_segments: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    merged: Dict[str, Dict[str, str]] = {}
    for seg in base_segments:
        source = seg.get("source") or ""
        if source:
            merged[source] = seg
    for seg in override_segments:
        source = seg.get("source") or ""
        if source:
            merged[source] = seg
    return [merged[source] for source in sorted(merged.keys(), key=_source_sort_key)]


def _score_segments(segments: List[Dict[str, str]]) -> Dict[str, object]:
    token_lists: List[List[str]] = []
    texts: List[str] = []
    for seg in segments:
        text = seg.get("text", "")
        texts.append(text)
        token_lists.append(_tokenize_text(text))

    if not token_lists:
        return {"scores_by_source": {}, "ranked": []}

    df_counter: Counter = Counter()
    for tokens in token_lists:
        df_counter.update(set(tokens))

    total_docs = len(token_lists)
    idf = {
        token: math.log((total_docs + 1) / (df + 1)) + 1.0
        for token, df in df_counter.items()
    }

    raw_scores = []
    scores_by_source: Dict[str, float] = {}
    for idx, seg in enumerate(segments):
        tokens = token_lists[idx]
        text = texts[idx]
        if not tokens:
            score = 0.0
        else:
            tf_counts = Counter(tokens)
            tfidf_sum = 0.0
            for token, count in tf_counts.items():
                tf = count / max(1, len(tokens))
                tfidf_sum += tf * idf.get(token, 1.0)
            tfidf_avg = tfidf_sum / max(1, len(tf_counts))
            numeric_density = len(re.findall(r"\\d", text)) / max(1, len(text))
            length_score = min(len(text) / 800.0, 1.0)
            score = tfidf_avg + (0.4 * numeric_density) + (0.2 * length_score)

        source = seg.get("source") or f"seg{idx}"
        raw_scores.append((source, score, text))
        scores_by_source[source] = score

    if not raw_scores:
        return {"scores_by_source": {}, "ranked": []}

    scores_only = [score for _, score, _ in raw_scores]
    min_score = min(scores_only)
    max_score = max(scores_only)
    scale = max_score - min_score if max_score != min_score else 1.0

    ranked = []
    for source, score, text in raw_scores:
        normalized = (score - min_score) / scale
        ranked.append({
            "source": source,
            "weight": round(normalized, 3),
            "section": _extract_section_title(text),
            "snippet": _normalize_whitespace(text)[:180],
        })

    ranked.sort(key=lambda item: item["weight"], reverse=True)
    return {
        "scores_by_source": {item["source"]: item["weight"] for item in ranked},
        "ranked": ranked,
    }


def _select_ocr_pages(
    path: Path,
    strategy: str,
    page_budget: int,
) -> List[int]:
    if not fitz:
        raise ImportError("PyMuPDF(fitz)가 필요합니다.")

    with fitz.open(path) as doc:
        page_count = doc.page_count
        if page_budget <= 0 or page_budget >= page_count:
            return list(range(page_count))

        if strategy == "front_back":
            pages = []
            if page_count > 0:
                pages.append(0)
            if page_count > 1:
                pages.append(1)
            if page_count > 2:
                pages.append(page_count - 1)
            if page_count > 3:
                pages.append(page_count - 2)
            pages = list(dict.fromkeys(pages))
            remaining = page_budget - len(pages)
            if remaining > 0:
                step = page_count / (remaining + 1)
                for i in range(1, remaining + 1):
                    idx = int(round(i * step))
                    if idx >= page_count:
                        idx = page_count - 1
                    if idx not in pages:
                        pages.append(idx)
            return sorted(pages[:page_budget])

        if strategy == "uniform":
            step = max(1, page_count // page_budget)
            pages = list(range(0, page_count, step))[:page_budget]
            return sorted(set(pages))

        ratios = []
        zoom = OCR_DENSITY_DPI / 72
        mat = fitz.Matrix(zoom, zoom)
        for page_index in range(page_count):
            page = doc.load_page(page_index)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            samples = pix.samples
            if not samples:
                ratios.append((0.0, page_index))
                continue
            dark = 0
            total_pixels = pix.width * pix.height
            for idx in range(0, len(samples), 3):
                if samples[idx] + samples[idx + 1] + samples[idx + 2] < 540:
                    dark += 1
            ratio = dark / max(1, total_pixels)
            ratios.append((ratio, page_index))

        ratios.sort(reverse=True)
        selected = sorted([page_index for _, page_index in ratios[:page_budget]])
        return selected


def _render_pdf_page_to_png(doc: "fitz.Document", page_index: int, dpi: int) -> bytes:
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    page = doc.load_page(page_index)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return pix.tobytes("png")


def local_ocr_available() -> bool:
    if not Image or not pytesseract:
        return False
    try:
        pytesseract.get_tesseract_version()
    except Exception:
        return False
    return True


def _local_ocr_from_png(png_bytes: bytes, lang: str) -> str:
    if not Image or not pytesseract:
        raise ImportError("로컬 OCR 라이브러리가 필요합니다.")
    with Image.open(io.BytesIO(png_bytes)) as img:
        return pytesseract.image_to_string(img, lang=lang, config="--oem 1 --psm 6")


def _ocr_pdf_fast_local(
    path: Path,
    dpi: int = OCR_FAST_DPI,
    lang: str = OCR_FAST_LANG,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    page_indices: Optional[List[int]] = None,
) -> List[Dict[str, str]]:
    if not fitz:
        raise ImportError("PyMuPDF(fitz)가 필요합니다.")
    if not Image or not pytesseract:
        raise ImportError("로컬 OCR 라이브러리가 필요합니다.")

    segments: List[Dict[str, str]] = []
    with fitz.open(path) as doc:
        pages = page_indices or list(range(doc.page_count))
        if progress_callback:
            progress_callback(0, len(pages), "로컬 OCR 시작")
        for idx, page_index in enumerate(pages, start=1):
            png_bytes = _render_pdf_page_to_png(doc, page_index, dpi)
            text = _local_ocr_from_png(png_bytes, lang=lang)
            segments.append({"source": f"p{page_index + 1}", "text": text})
            if progress_callback:
                progress_callback(idx, len(pages), "로컬 OCR 진행 중")
    return segments


def _extract_claude_text(response: object) -> str:
    parts = []
    for block in getattr(response, "content", []) or []:
        text = getattr(block, "text", "")
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _refine_ocr_text_with_claude(
    text: str,
    api_key: str,
    model: str = OCR_DEFAULT_MODEL,
) -> str:
    if not Anthropic:
        raise ImportError("anthropic SDK가 필요합니다.")
    if not api_key:
        raise ValueError("Claude API 키가 필요합니다.")

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=2000,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": f"{OCR_REFINE_PROMPT}\n\n[OCR TEXT]\n{text}",
            }
        ],
    )
    return _extract_claude_text(response)


def _ocr_pdf_with_claude(
    path: Path,
    api_key: str,
    model: str = OCR_DEFAULT_MODEL,
    dpi: int = OCR_DEFAULT_DPI,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    page_indices: Optional[List[int]] = None,
) -> List[Dict[str, str]]:
    if not fitz:
        raise ImportError("PyMuPDF(fitz)가 필요합니다.")
    if not Anthropic:
        raise ImportError("anthropic SDK가 필요합니다.")
    if not api_key:
        raise ValueError("Claude API 키가 필요합니다.")

    client = Anthropic(api_key=api_key)
    segments: List[Dict[str, str]] = []
    with fitz.open(path) as doc:
        pages = page_indices or list(range(doc.page_count))
        if progress_callback:
            progress_callback(0, len(pages), "OCR 시작")
        for idx, page_index in enumerate(pages, start=1):
            png_bytes = _render_pdf_page_to_png(doc, page_index, dpi)
            encoded = base64.b64encode(png_bytes).decode("ascii")
            response = client.messages.create(
                model=model,
                max_tokens=4000,
                temperature=0,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": OCR_PROMPT},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": encoded,
                                },
                            },
                        ],
                    }
                ],
            )
            text = _extract_claude_text(response)
            segments.append({"source": f"p{page_index + 1}", "text": text})
            if progress_callback:
                progress_callback(idx, len(pages), "OCR 진행 중")
    return segments


def load_document(
    path: Path,
    ocr_mode: str = "off",
    api_key: str = "",
    ocr_model: str = OCR_DEFAULT_MODEL,
    ocr_page_budget: int = 0,
    ocr_strategy: str = "density",
    ocr_refine: bool = True,
    ocr_refine_model: str = OCR_DEFAULT_MODEL,
    ocr_fast_lang: str = OCR_FAST_LANG,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Dict[str, object]:
    ext = path.suffix.lower()
    page_count = 0
    ocr_used = False
    ocr_error = ""
    ocr_pages_used: List[int] = []
    ocr_engine = ""
    ocr_refined = False
    ocr_refine_error = ""
    if ext == ".pdf":
        segments, page_count = _build_segments_from_pdf(path)
        if ocr_mode in ("auto", "force"):
            if not api_key:
                ocr_error = "Claude API 키가 없습니다."
            else:
                try:
                    ocr_pages = _select_ocr_pages(path, ocr_strategy, ocr_page_budget)
                    ocr_segments = _ocr_pdf_with_claude(
                        path,
                        api_key=api_key,
                        model=ocr_model,
                        progress_callback=progress_callback,
                        page_indices=ocr_pages,
                    )
                    ocr_engine = "claude_image"

                    segments = _merge_segments_by_source(segments, ocr_segments)
                    ocr_used = True
                    ocr_pages_used = ocr_pages
                except Exception as exc:
                    ocr_error = str(exc)
                    logger.warning("OCR 실패: %s", exc)
    elif ext in (".docx",):
        segments = _build_segments_from_docx(path)
    else:
        text = path.read_text(encoding="utf-8", errors="ignore")
        segments = [{"source": "text", "text": text}] if text else []

    scoring = _score_segments(segments)
    full_text = "\n".join(seg["text"] for seg in segments if seg.get("text"))
    return {
        "segments": segments,
        "text": full_text,
        "page_count": page_count,
        "ocr_used": ocr_used,
        "ocr_error": ocr_error,
        "ocr_pages_used": ocr_pages_used,
        "ocr_engine": ocr_engine,
        "ocr_refined": ocr_refined,
        "ocr_refine_error": ocr_refine_error,
        "segment_scores": scoring.get("scores_by_source", {}),
        "priority_segments": scoring.get("ranked", []),
    }


def extract_fields(segments: List[Dict[str, str]]) -> Dict[str, Dict[str, object]]:
    results: Dict[str, Dict[str, object]] = {}

    for field in FIELD_DEFINITIONS:
        for pattern in field["patterns"]:
            regex = re.compile(pattern, re.IGNORECASE)
            for segment in segments:
                text = segment.get("text", "")
                match = regex.search(text)
                if not match:
                    continue

                raw_value = (match.group("value") or "").strip()
                value = _normalize_whitespace(raw_value)
                normalized = value

                if field["type"] == "company":
                    normalized = _normalize_company_name(value)
                elif field["type"] == "amount":
                    normalized = _parse_korean_amount(value)
                elif field["type"] == "count":
                    normalized = _parse_count(value)

                snippet = _build_snippet(text, match.start(), match.end())
                results[field["name"]] = {
                    "label": field["label"],
                    "value": value,
                    "normalized": normalized,
                    "source": segment.get("source"),
                    "snippet": snippet,
                }
                break
            if field["name"] in results:
                break

    return results


def _find_clause_snippet(segments: List[Dict[str, str]], keywords: List[str]) -> Optional[Dict[str, str]]:
    keywords_lower = [kw.lower() for kw in keywords]
    for segment in segments:
        text = segment.get("text", "")
        lower_text = text.lower()
        for keyword in keywords_lower:
            idx = lower_text.find(keyword)
            if idx >= 0:
                snippet = _build_snippet(text, idx, idx + len(keyword))
                return {"source": segment.get("source"), "snippet": snippet}
    return None


def detect_clauses(
    segments: List[Dict[str, str]],
    doc_type: str,
    scores_by_source: Optional[Dict[str, float]] = None,
) -> List[Dict[str, object]]:
    clauses = []
    taxonomy = CLAUSE_TAXONOMY.get(doc_type, [])
    for clause in taxonomy:
        hit = _find_clause_snippet(segments, clause["keywords"])
        weight = 0.0
        if hit and scores_by_source:
            weight = scores_by_source.get(hit.get("source", ""), 0.0)
        clauses.append({
            "id": clause["id"],
            "label": clause["label"],
            "present": bool(hit),
            "source": hit["source"] if hit else None,
            "snippet": hit["snippet"] if hit else "",
            "weight": round(weight, 3),
        })
    return clauses


def compare_fields(fields_a: Dict[str, Dict[str, object]], fields_b: Dict[str, Dict[str, object]]) -> List[Dict[str, object]]:
    comparisons = []
    for field in FIELD_DEFINITIONS:
        name = field["name"]
        label = field["label"]
        a = fields_a.get(name)
        b = fields_b.get(name)

        status = "-"
        note = ""
        if a and b:
            if field["type"] in ("amount", "count"):
                a_val = a.get("normalized")
                b_val = b.get("normalized")
                if a_val is None or b_val is None:
                    status = "검토 필요"
                    note = "금액 파싱 실패"
                else:
                    tolerance = max(1000, int(0.01 * max(a_val, b_val)))
                    status = "일치" if abs(a_val - b_val) <= tolerance else "불일치"
                    if status == "불일치":
                        note = f"차이 {abs(a_val - b_val):,}"
            else:
                a_norm = a.get("normalized") or _normalize_whitespace(a.get("value", ""))
                b_norm = b.get("normalized") or _normalize_whitespace(b.get("value", ""))
                status = "일치" if a_norm and b_norm and a_norm == b_norm else "불일치"
        elif a or b:
            status = "누락"
            note = "한쪽 문서에만 존재"

        comparisons.append({
            "field": label,
            "term_sheet": a.get("value") if a else "",
            "investment_agreement": b.get("value") if b else "",
            "status": status,
            "note": note,
        })

    return comparisons


def search_segments(segments: List[Dict[str, str]], query: str, max_hits: int = 20) -> List[Dict[str, str]]:
    if not query:
        return []

    hits = []
    query_lower = query.lower()
    for segment in segments:
        text = segment.get("text", "")
        lower_text = text.lower()
        if query_lower in lower_text:
            idx = lower_text.find(query_lower)
            snippet = _build_snippet(text, idx, idx + len(query))
            hits.append({
                "source": segment.get("source"),
                "snippet": snippet,
            })
            if len(hits) >= max_hits:
                break
    return hits
