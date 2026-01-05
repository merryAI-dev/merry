"""
Document Parsing Service

Claude Vision API를 기본으로 사용하여 PDF를 구조화된 데이터로 추출합니다.
테이블, 재무제표를 자동으로 인식하고 추출합니다.
"""

from .config import DOLPHIN_CONFIG
from .processor import ClaudeVisionProcessor, DolphinProcessor, process_pdf_with_claude
from .table_extractor import FinancialTableExtractor
from .output_converter import OutputConverter

__all__ = [
    "DOLPHIN_CONFIG",
    "ClaudeVisionProcessor",
    "DolphinProcessor",  # 하위 호환성
    "FinancialTableExtractor",
    "OutputConverter",
    "process_pdf_with_claude",
]

__version__ = "1.1.0"
