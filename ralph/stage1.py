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


@dataclass
class PageMarkdown:
    """Single page extraction result."""

    page_num: int
    text: str
    tables_md: List[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        parts = [f"### Page {self.page_num + 1}\n"]
        if self.text.strip():
            parts.append(self.text.strip())
        for i, tbl in enumerate(self.tables_md):
            parts.append(f"\n**Table {i + 1}**\n{tbl}")
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

            # Tables
            tables_md: List[str] = []
            try:
                tables = page.find_tables()
                if tables and tables.tables:
                    for tbl in tables.tables:
                        md = _table_to_markdown(tbl)
                        if md:
                            tables_md.append(md)
            except Exception as e:
                logger.debug(f"Page {page_num} 테이블 추출 실패: {e}")

            pages.append(PageMarkdown(page_num=page_num, text=text, tables_md=tables_md))
    finally:
        doc.close()

    # 3) Combine into full markdown
    full_md = "\n\n---\n\n".join(p.to_markdown() for p in pages)

    logger.info(
        f"Stage1 완료: {len(pages)}p, "
        f"{sum(len(p.text) for p in pages):,} chars, "
        f"{sum(len(p.tables_md) for p in pages)} tables"
    )

    return Stage1Result(
        pdf_path=pdf_path,
        classification=classification,
        pages=pages,
        full_markdown=full_md,
    )
