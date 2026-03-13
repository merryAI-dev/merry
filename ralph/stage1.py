"""
Stage 1: Rule-based markdown extraction using PyMuPDF.

No API cost. Extracts raw text + tables as markdown.
Classification reuses dolphin_service/classifier.py.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

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
class ClassifiedTable:
    """테이블 마크다운 + 키워드 기반 카테고리 분류 결과."""
    markdown: str
    category: str  # financial_statement, cap_table, investment_terms, etc.
    bbox: Optional[Tuple[float, float, float, float]] = None  # (x0, y0, x1, y1)
    page_num: int = 0


@dataclass
class PageImage:
    """페이지 내 의미 있는 이미지 (로고/도장 제외)."""
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    width: int   # px
    height: int  # px
    xref: int    # PyMuPDF cross-reference (이미지 추출용)
    page_num: int


# 이미지 필터링 임계값 (포인트 단위, 72pt = 1inch)
_IMG_MIN_WIDTH_PTS = 100   # ~35mm
_IMG_MIN_HEIGHT_PTS = 80   # ~28mm
_IMG_MIN_AREA_PTS = 8000   # ~100mm²
_IMG_MAX_PAGE_RATIO = 0.95  # 페이지 95% 이상이면 배경


def _filter_images(page: "fitz.Page") -> List[PageImage]:
    """페이지에서 의미 있는 이미지만 추출. 로고/도장/배경 제외."""
    result: List[PageImage] = []
    page_w, page_h = page.rect.width, page.rect.height

    for img in page.get_images(full=True):
        xref = img[0]
        px_w, px_h = img[2], img[3]

        rects = page.get_image_rects(xref)
        if not rects:
            continue
        r = rects[0]  # 첫 번째 위치

        w, h = r.width, r.height
        # 너무 작음 → 로고/아이콘
        if w < _IMG_MIN_WIDTH_PTS or h < _IMG_MIN_HEIGHT_PTS:
            continue
        if w * h < _IMG_MIN_AREA_PTS:
            continue
        # 페이지 거의 전체 → 배경
        if w / page_w > _IMG_MAX_PAGE_RATIO and h / page_h > _IMG_MAX_PAGE_RATIO:
            continue

        result.append(PageImage(
            bbox=(r.x0, r.y0, r.x1, r.y1),
            width=px_w, height=px_h,
            xref=xref, page_num=page.number,
        ))
    return result


@dataclass
class PageMarkdown:
    """Single page extraction result."""

    page_num: int
    text: str
    tables: List[ClassifiedTable] = field(default_factory=list)
    images: List[PageImage] = field(default_factory=list)

    def to_markdown(self) -> str:
        parts = [f"### Page {self.page_num + 1}\n"]
        if self.text.strip():
            parts.append(self.text.strip())
        for i, tbl in enumerate(self.tables):
            label = f" [{tbl.category}]" if tbl.category != "other" else ""
            parts.append(f"\n**Table {i + 1}{label}**\n{tbl.markdown}")
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

            # Tables with category classification + bbox
            table_infos: List[ClassifiedTable] = []
            try:
                tables = page.find_tables()
                if tables and tables.tables:
                    for tbl in tables.tables:
                        md = _table_to_markdown(tbl)
                        if md:
                            category = _classify_table(md)
                            table_infos.append(ClassifiedTable(
                                markdown=md,
                                category=category,
                                bbox=tbl.bbox,
                                page_num=page_num,
                            ))
            except Exception as e:
                logger.debug(f"Page {page_num} 테이블 추출 실패: {e}")

            # Images: 의미 있는 이미지만 (로고/도장/배경 제외)
            page_images: List[PageImage] = []
            try:
                page_images = _filter_images(page)
            except Exception as e:
                logger.debug(f"Page {page_num} 이미지 추출 실패: {e}")

            pages.append(PageMarkdown(
                page_num=page_num, text=text,
                tables=table_infos, images=page_images,
            ))
    finally:
        doc.close()

    # 3) Combine into full markdown
    full_md = "\n\n---\n\n".join(p.to_markdown() for p in pages)

    total_tables = sum(len(p.tables) for p in pages)
    categorized = [t for p in pages for t in p.tables if t.category != "other"]
    total_images = sum(len(p.images) for p in pages)
    logger.info(
        f"Stage1 완료: {len(pages)}p, "
        f"{sum(len(p.text) for p in pages):,} chars, "
        f"{total_tables} tables ({len(categorized)} categorized), "
        f"{total_images} images"
    )

    return Stage1Result(
        pdf_path=pdf_path,
        classification=classification,
        pages=pages,
        full_markdown=full_md,
    )
