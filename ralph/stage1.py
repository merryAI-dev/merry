"""
Stage 1: Rule-based markdown extraction using PyMuPDF.

No API cost. Extracts raw text + tables as markdown.
Classification reuses dolphin_service/classifier.py.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import fitz  # PyMuPDF

from dolphin_service.classifier import ClassificationResult, classify_document

logger = logging.getLogger(__name__)


TABLE_CATEGORIES = {
    "financial_statement": ["매출", "영업이익", "당기순이익", "자산총계", "부채총계", "자본총계", "매출액", "매출원가"],
    "cap_table": ["주주", "지분", "주식수", "보통주", "우선주", "발행주식"],
    "investment_terms": ["투자금액", "투자단가", "밸류에이션", "Pre-money", "Post-money"],
    "comparison": ["비교", "대비", "증감", "전년", "YoY"],
    "performance": ["KPI", "실적", "목표", "달성", "성장률"],
    "pricing": ["단가", "요금", "가격", "수수료"],
    "schedule": ["일정", "기간", "시작일", "종료일", "마감"],
}


def _classify_table(table_md: str) -> str:
    """키워드 기반 테이블 카테고리 분류. 비용 0원."""
    text = table_md.lower()
    best_cat = "other"
    best_score = 0
    for category, keywords in TABLE_CATEGORIES.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > best_score:
            best_score = score
            best_cat = category
    return best_cat if best_score >= 2 else "other"


@dataclass
class TableInfo:
    """테이블 추출 결과 + 카테고리."""
    markdown: str
    category: str  # financial_statement, cap_table, investment_terms, etc.


@dataclass
class PageMarkdown:
    """Single page extraction result."""

    page_num: int
    text: str
    tables_md: List[str] = field(default_factory=list)
    tables: List[TableInfo] = field(default_factory=list)

    def to_markdown(self) -> str:
        parts = [f"### Page {self.page_num + 1}\n"]
        if self.text.strip():
            parts.append(self.text.strip())
        for i, tbl in enumerate(self.tables):
            label = f" [{tbl.category}]" if tbl.category != "other" else ""
            parts.append(f"\n**Table {i + 1}{label}**\n{tbl.markdown}")
        # Legacy: tables_md without category info
        for i, tbl in enumerate(self.tables_md):
            parts.append(f"\n**Table {len(self.tables) + i + 1}**\n{tbl}")
        return "\n\n".join(parts)


@dataclass
class Stage1Result:
    """Stage 1 extraction result."""

    pdf_path: str
    classification: ClassificationResult
    pages: List[PageMarkdown]
    full_markdown: str


def _table_to_markdown(table) -> str:
    """Convert a PyMuPDF table to markdown."""
    try:
        rows = table.extract()
    except Exception:
        return ""
    if not rows:
        return ""

    lines = []
    for i, row in enumerate(rows):
        cells = [str(c).strip() if c is not None else "" for c in row]
        lines.append("| " + " | ".join(cells) + " |")
        if i == 0:
            lines.append("| " + " | ".join(["---"] * len(cells)) + " |")
    return "\n".join(lines)


def extract_stage1(pdf_path: str) -> Stage1Result:
    """
    PyMuPDF로 rule-based 마크다운 추출. API 비용 0원.

    1) dolphin_service classifier로 문서 분류
    2) PyMuPDF로 페이지별 텍스트 + 테이블 추출
    3) 마크다운으로 합쳐서 반환 (Stage 2 입력)
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # 1) Classify document
    classification = classify_document(pdf_path)
    logger.info(
        f"Stage1 분류: {classification.doc_type.value} "
        f"({classification.total_pages}p, {classification.confidence:.2f} conf)"
    )

    # 2) Extract text + tables per page
    doc = fitz.open(pdf_path)
    pages: List[PageMarkdown] = []

    try:
        for page_num in range(len(doc)):
            page = doc[page_num]

            # Text
            text = page.get_text("text")

            # Tables with category classification
            table_infos: List[TableInfo] = []
            try:
                tables = page.find_tables()
                if tables and tables.tables:
                    for tbl in tables.tables:
                        md = _table_to_markdown(tbl)
                        if md:
                            category = _classify_table(md)
                            table_infos.append(TableInfo(markdown=md, category=category))
            except Exception as e:
                logger.debug(f"Page {page_num} 테이블 추출 실패: {e}")

            pages.append(PageMarkdown(page_num=page_num, text=text, tables=table_infos))
    finally:
        doc.close()

    # 3) Combine into full markdown
    full_md = "\n\n---\n\n".join(p.to_markdown() for p in pages)

    total_tables = sum(len(p.tables) for p in pages)
    categorized = [t for p in pages for t in p.tables if t.category != "other"]
    logger.info(
        f"Stage1 완료: {len(pages)}p, "
        f"{sum(len(p.text) for p in pages):,} chars, "
        f"{total_tables} tables ({len(categorized)} categorized)"
    )

    return Stage1Result(
        pdf_path=pdf_path,
        classification=classification,
        pages=pages,
        full_markdown=full_md,
    )
