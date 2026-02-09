"""
Document classifier for PDF processing.

Classifies PDF documents based on PyMuPDF metadata (no API calls needed).
Determines optimal processing strategy for each document type.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class DocType(Enum):
    """Document types based on content characteristics."""

    PURE_TEXT = "pure_text"  # 정관, 계약서 (이미지 0, 텍스트 多)
    TEXT_WITH_TABLES = "text_tables"  # 재무제표증명 (텍스트+테이블)
    MIXED_RICH = "mixed_rich"  # 투자검토자료 (텍스트+이미지+테이블)
    IMAGE_HEAVY = "image_heavy"  # IR자료 (이미지 위주, 50+ images/page)
    FULLY_SCANNED = "fully_scanned"  # 법인등기부등본 (OCR 필요)
    SIMPLE_FORM = "simple_form"  # 인증서, 사업자등록증 (1-4p 양식)
    SMALL_TABLE = "small_table"  # 주주명부 (PyMuPDF 직접 추출)


@dataclass
class ClassificationResult:
    """Document classification result."""

    doc_type: DocType
    total_pages: int
    total_size_bytes: int
    per_page_text: List[str]  # Raw page text from PyMuPDF (for debugging/QA)
    text_chars: int  # Total characters from PyMuPDF
    image_count: int  # Embedded images
    table_count: int  # PyMuPDF find_tables() count
    scanned_page_ratio: float  # Ratio of pages with < 50 chars
    estimated_base64_mb: float  # Estimated base64 size
    avg_images_per_page: float
    confidence: float  # 0.0-1.0, classification confidence


def classify_document(pdf_path: str) -> ClassificationResult:
    """Classify a PDF document based on metadata.

    Args:
        pdf_path: Path to PDF file

    Returns:
        ClassificationResult with doc_type and metadata

    Raises:
        FileNotFoundError: PDF file not found
        ValueError: Invalid PDF file
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise ValueError(f"Invalid PDF: {e}")

    try:
        # Collect metadata
        total_pages = len(doc)
        total_size = path.stat().st_size
        text_chars = 0
        per_page_text: List[str] = []
        image_count = 0
        table_count = 0
        scanned_pages = 0

        for page_num in range(total_pages):
            page = doc[page_num]

            # Text extraction
            text = page.get_text("text")
            text_chars += len(text)
            per_page_text.append(text)

            # Scanned page detection (< 50 chars)
            if len(text) < 50:
                scanned_pages += 1

            # Image count
            images = page.get_images()
            image_count += len(images)

            # Table detection
            try:
                tables = page.find_tables()
                if tables:
                    table_count += len(tables.tables)
            except Exception:
                # PyMuPDF find_tables() may fail on some PDFs
                pass

        doc.close()

        # Calculate metrics
        scanned_page_ratio = scanned_pages / total_pages if total_pages > 0 else 0.0
        avg_images_per_page = image_count / total_pages if total_pages > 0 else 0.0

        # Estimate base64 size (rough approximation)
        # Typical PNG conversion: 1 page ≈ 500KB base64 for 150 DPI
        estimated_base64_mb = (total_pages * 0.5)  # MB

        # Classification decision tree
        doc_type, confidence = _determine_doc_type(
            text_chars=text_chars,
            image_count=image_count,
            table_count=table_count,
            total_pages=total_pages,
            scanned_page_ratio=scanned_page_ratio,
            avg_images_per_page=avg_images_per_page,
        )

        return ClassificationResult(
            doc_type=doc_type,
            total_pages=total_pages,
            total_size_bytes=total_size,
            per_page_text=per_page_text,
            text_chars=text_chars,
            image_count=image_count,
            table_count=table_count,
            scanned_page_ratio=scanned_page_ratio,
            estimated_base64_mb=estimated_base64_mb,
            avg_images_per_page=avg_images_per_page,
            confidence=confidence,
        )

    except Exception as e:
        logger.error(f"Failed to classify {pdf_path}: {e}", exc_info=True)
        raise


def classify(pdf_path: str) -> ClassificationResult:
    """Backward-compatible alias for older imports/tests."""
    return classify_document(pdf_path)


def _determine_doc_type(
    text_chars: int,
    image_count: int,
    table_count: int,
    total_pages: int,
    scanned_page_ratio: float,
    avg_images_per_page: float,
) -> tuple:
    """Determine document type using decision tree.

    Returns:
        (DocType, confidence_score)
    """
    # Decision tree logic
    confidence = 1.0

    # Rule 1: Fully scanned (no text)
    if text_chars == 0:
        return DocType.FULLY_SCANNED, 1.0

    # Rule 2: Mostly scanned (> 80% pages have < 50 chars)
    if scanned_page_ratio > 0.8:
        return DocType.FULLY_SCANNED, 0.9

    # Rule 3: Pure text (no images)
    if image_count == 0:
        if table_count > 0:
            return DocType.TEXT_WITH_TABLES, 0.95
        else:
            return DocType.PURE_TEXT, 0.95

    # Rule 4: Simple form (1-4 pages, few tables)
    if total_pages <= 4 and table_count <= 2:
        return DocType.SIMPLE_FORM, 0.85

    # Rule 5: Small table (1 page, 1 table)
    if total_pages == 1 and table_count == 1:
        return DocType.SMALL_TABLE, 0.9

    # Rule 5.5: Table-heavy text PDFs (e.g., financial statements) even if they embed a few images.
    # Keep this narrow so rich decks/review docs aren't misclassified.
    if table_count > 0 and total_pages <= 10 and scanned_page_ratio < 0.2 and avg_images_per_page <= 10:
        return DocType.TEXT_WITH_TABLES, 0.85

    # Rule 6: Image-heavy (> 50 images per page average)
    if avg_images_per_page > 50:
        return DocType.IMAGE_HEAVY, 0.85

    # Rule 7: Mixed rich content (default for complex documents)
    return DocType.MIXED_RICH, 0.7


def classify_and_log(pdf_path: str) -> ClassificationResult:
    """Classify document and log result.

    Convenience function for debugging.
    """
    result = classify_document(pdf_path)
    logger.info(
        f"Classified {Path(pdf_path).name}: {result.doc_type.value} "
        f"({result.confidence:.2f} confidence, "
        f"{result.total_pages}p, {result.text_chars:,} chars, "
        f"{result.image_count} images, {result.table_count} tables)"
    )
    return result


# Example usage
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python classifier.py <pdf_path>")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO)
    pdf_path = sys.argv[1]

    try:
        result = classify_and_log(pdf_path)
        print(f"\nClassification Result:")
        print(f"  Type: {result.doc_type.value}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Pages: {result.total_pages}")
        print(f"  Size: {result.total_size_bytes / (1024*1024):.2f} MB")
        print(f"  Text chars: {result.text_chars:,}")
        print(f"  Images: {result.image_count}")
        print(f"  Tables: {result.table_count}")
        print(f"  Scanned ratio: {result.scanned_page_ratio:.2%}")
        print(f"  Estimated base64: {result.estimated_base64_mb:.2f} MB")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
