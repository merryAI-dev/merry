"""Document-type specific Pydantic schemas for extraction validation."""

from .base import ExtractionResult
from .business_reg import BusinessRegistration

# Document type → Schema class mapping
SCHEMA_MAP: dict[str, type[ExtractionResult]] = {
    "business_reg": BusinessRegistration,
}

__all__ = [
    "ExtractionResult",
    "BusinessRegistration",
    "SCHEMA_MAP",
]
