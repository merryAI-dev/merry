"""문서 타입별 추출기 레지스트리."""
from __future__ import annotations

from .base import BaseExtractor
from .business_reg_extractor import BusinessRegExtractor
from .financial_stmt_extractor import FinancialStmtExtractor
from .shareholder_extractor import ShareholderExtractor


# 추출기 레지스트리: doc_type → 추출기 인스턴스
_EXTRACTORS: dict[str, BaseExtractor] = {
    "business_reg": BusinessRegExtractor(),
    "financial_stmt": FinancialStmtExtractor(),
    "shareholder": ShareholderExtractor(),
}


def get_extractor(doc_type: str) -> BaseExtractor | None:
    """문서 타입에 맞는 추출기 반환."""
    return _EXTRACTORS.get(doc_type)


def list_supported_types() -> list[str]:
    """지원하는 문서 타입 목록."""
    return list(_EXTRACTORS.keys())
