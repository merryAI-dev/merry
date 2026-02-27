"""Document-type specific Pydantic schemas for extraction validation."""

from .base import ExtractionResult

# Document type → Schema class mapping
SCHEMA_MAP: dict[str, type[ExtractionResult]] = {}

__all__ = [
    "ExtractionResult",
    "SCHEMA_MAP",
]
