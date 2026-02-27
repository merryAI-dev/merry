"""Document-type specific Pydantic schemas for extraction validation."""

from .base import ExtractionResult
from .business_reg import BusinessRegistration
from .financial_stmt import FinancialStatementSet

# Document type → Schema class mapping
SCHEMA_MAP: dict[str, type[ExtractionResult]] = {
    "business_reg": BusinessRegistration,
    "financial_stmt": FinancialStatementSet,
}

__all__ = [
    "ExtractionResult",
    "BusinessRegistration",
    "FinancialStatementSet",
    "SCHEMA_MAP",
]
