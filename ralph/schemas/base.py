"""Base extraction result schema shared by all document types."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExtractionResult(BaseModel):
    """Base class for all document extraction results."""

    doc_type: str = Field(description="Document type identifier")
    source_file: str = Field(description="Source PDF filename")
    extracted_at: datetime = Field(default_factory=datetime.now)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Extraction confidence")
    raw_fields: dict[str, Any] = Field(default_factory=dict, description="Raw extracted key-value pairs")
    natural_language: str | None = Field(default=None, description="Natural language summary for RAG")
