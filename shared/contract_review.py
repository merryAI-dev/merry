"""
Contract review helpers for Term Sheet / Investment Agreement (KR)
- Text extraction (PDF/DOCX)
- Field extraction + evidence snippets
- Clause checklist detection
- Cross-document consistency checks
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

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


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.strip().split())


def _normalize_company_name(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", "", text)
    text = text.replace("주식회사", "").replace("유한회사", "")
    text = text.replace("(주)", "").replace("㈜", "")
    return text


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


def _build_segments_from_pdf(path: Path) -> List[Dict[str, str]]:
    if not fitz:
        raise ImportError("PyMuPDF(fitz)가 필요합니다.")

    segments: List[Dict[str, str]] = []
    with fitz.open(path) as doc:
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            text = page.get_text("text")
            if not text:
                continue
            segments.append({"source": f"p{page_index + 1}", "text": text})
    return segments


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


def load_document(path: Path) -> Dict[str, object]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        segments = _build_segments_from_pdf(path)
    elif ext in (".docx",):
        segments = _build_segments_from_docx(path)
    else:
        text = path.read_text(encoding="utf-8", errors="ignore")
        segments = [{"source": "text", "text": text}] if text else []

    full_text = "\n".join(seg["text"] for seg in segments if seg.get("text"))
    return {"segments": segments, "text": full_text}


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


def detect_clauses(segments: List[Dict[str, str]], doc_type: str) -> List[Dict[str, object]]:
    clauses = []
    taxonomy = CLAUSE_TAXONOMY.get(doc_type, [])
    for clause in taxonomy:
        hit = _find_clause_snippet(segments, clause["keywords"])
        clauses.append({
            "id": clause["id"],
            "label": clause["label"],
            "present": bool(hit),
            "source": hit["source"] if hit else None,
            "snippet": hit["snippet"] if hit else "",
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
