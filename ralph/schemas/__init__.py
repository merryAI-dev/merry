"""Document-type specific Pydantic schemas for extraction validation."""

from .base import ExtractionResult
from .business_reg import BusinessRegistration
from .financial_stmt import FinancialStatementSet
from .shareholder import ShareholderRegistry

# Document type → Schema class mapping
SCHEMA_MAP: dict[str, type[ExtractionResult]] = {
    "business_reg": BusinessRegistration,
    "financial_stmt": FinancialStatementSet,
    "shareholder": ShareholderRegistry,
}

__all__ = [
    "ExtractionResult",
    "BusinessRegistration",
    "FinancialStatementSet",
    "ShareholderRegistry",
    "SCHEMA_MAP",
]
