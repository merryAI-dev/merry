"""
Processing strategy router for PDF documents.

Maps DocType to optimal ProcessingStrategy (model, DPI, prompts, chunking).
"""

import logging
from dataclasses import dataclass
from typing import Optional

from .classifier import DocType

logger = logging.getLogger(__name__)


@dataclass
class ProcessingStrategy:
    """Processing strategy for a document type."""

    use_vision: bool  # False = PyMuPDF only, True = Claude Vision
    model: Optional[str]  # None if use_vision=False
    dpi: int  # Image conversion DPI (0 if use_vision=False)
    prompt_type: str  # Key for prompts registry
    max_tokens: int  # API response max_tokens
    chunk_pages: int  # Maximum pages per chunk
    max_chunk_mb: float  # Maximum MB per chunk (base64)


# Strategy mapping for each document type
STRATEGY_MAP = {
    DocType.PURE_TEXT: ProcessingStrategy(
        use_vision=False,
        model=None,
        dpi=0,
        prompt_type="none",
        max_tokens=0,
        chunk_pages=999,  # No chunking needed
        max_chunk_mb=0,
    ),
    DocType.TEXT_WITH_TABLES: ProcessingStrategy(
        use_vision=False,
        model=None,
        dpi=0,
        prompt_type="none",
        max_tokens=0,
        chunk_pages=999,
        max_chunk_mb=0,
    ),
    DocType.SMALL_TABLE: ProcessingStrategy(
        use_vision=False,
        model=None,
        dpi=0,
        prompt_type="none",
        max_tokens=0,
        chunk_pages=999,
        max_chunk_mb=0,
    ),
    DocType.SIMPLE_FORM: ProcessingStrategy(
        use_vision=True,
        model="claude-haiku-4-5-20251001",  # Cheapest for simple forms
        dpi=100,  # Lower DPI for simple forms
        prompt_type="certificate_extraction",
        max_tokens=2048,
        chunk_pages=4,  # 1-4 pages typical
        max_chunk_mb=10,
    ),
    DocType.MIXED_RICH: ProcessingStrategy(
        use_vision=True,
        model="claude-sonnet-4-5-20250929",  # Best quality for complex docs
        dpi=150,  # Standard DPI
        prompt_type="financial_structured",
        max_tokens=16384,
        chunk_pages=8,
        max_chunk_mb=40,
    ),
    DocType.IMAGE_HEAVY: ProcessingStrategy(
        use_vision=True,
        model="claude-sonnet-4-5-20250929",
        dpi=120,  # Lower DPI to reduce size
        prompt_type="financial_structured",
        max_tokens=16384,
        chunk_pages=5,  # Fewer pages per chunk (images are large)
        max_chunk_mb=40,
    ),
    DocType.FULLY_SCANNED: ProcessingStrategy(
        use_vision=True,
        model="claude-sonnet-4-5-20250929",  # OCR needs good model
        dpi=200,  # Higher DPI for OCR accuracy
        prompt_type="legal_extraction",
        max_tokens=8192,
        chunk_pages=4,
        max_chunk_mb=40,
    ),
}


def get_strategy(doc_type: DocType) -> ProcessingStrategy:
    """Get processing strategy for a document type.

    Args:
        doc_type: Classified document type

    Returns:
        ProcessingStrategy for this document type

    Raises:
        ValueError: Unknown document type
    """
    if doc_type not in STRATEGY_MAP:
        raise ValueError(f"Unknown document type: {doc_type}")

    strategy = STRATEGY_MAP[doc_type]
    logger.info(
        f"Selected strategy for {doc_type.value}: "
        f"vision={strategy.use_vision}, model={strategy.model}, "
        f"dpi={strategy.dpi}, prompt={strategy.prompt_type}"
    )
    return strategy


def get_cost_order(doc_type: DocType) -> int:
    """Get relative cost order for a document type (for sorting).

    Lower = cheaper, higher = more expensive.
    Used to process documents in cost-efficient order.

    Returns:
        0: Free (PyMuPDF only)
        1: Cheap (Haiku)
        2: Medium (Sonnet)
    """
    strategy = get_strategy(doc_type)

    if not strategy.use_vision:
        return 0  # Free

    if strategy.model and "haiku" in strategy.model.lower():
        return 1  # Cheap

    return 2  # Medium/Expensive


# Cost order map for sorting
COST_ORDER = {doc_type: get_cost_order(doc_type) for doc_type in DocType}


# Example usage
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python strategy.py <doc_type>")
        print(f"Available types: {[dt.value for dt in DocType]}")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO)
    doc_type_str = sys.argv[1]

    try:
        doc_type = DocType(doc_type_str)
        strategy = get_strategy(doc_type)
        print(f"\nProcessing Strategy for {doc_type.value}:")
        print(f"  Use Vision API: {strategy.use_vision}")
        print(f"  Model: {strategy.model}")
        print(f"  DPI: {strategy.dpi}")
        print(f"  Prompt Type: {strategy.prompt_type}")
        print(f"  Max Tokens: {strategy.max_tokens}")
        print(f"  Chunk Pages: {strategy.chunk_pages}")
        print(f"  Max Chunk MB: {strategy.max_chunk_mb}")
        print(f"  Cost Order: {get_cost_order(doc_type)}")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
