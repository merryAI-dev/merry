"""
Schema validation for RALPH extraction results.

Validates Stage 2 output against document-type-specific Pydantic schemas.
Returns structured error reports for the reflector.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from .schemas import SCHEMA_MAP, ExtractionResult

logger = logging.getLogger(__name__)


def validate_extraction(
    raw: Dict[str, Any],
    doc_type: str,
    source_file: str = "",
) -> Tuple[Optional[ExtractionResult], List[Dict[str, str]]]:
    """
    Validate extraction result against schema.

    Args:
        raw: Stage 2 raw JSON output
        doc_type: Document type key
        source_file: Source PDF filename

    Returns:
        (result, errors) - result is None if validation failed
        errors is a list of {"field": ..., "message": ...} dicts
    """
    errors: List[Dict[str, str]] = []

    # Check for Stage 2 parse errors
    if "_parse_error" in raw:
        errors.append({
            "field": "_json",
            "message": f"JSON 파싱 실패: {raw['_parse_error']}",
            "raw_text": raw.get("_raw_text", "")[:500],
        })
        return None, errors

    # Get schema class
    schema_cls = SCHEMA_MAP.get(doc_type)
    if not schema_cls:
        errors.append({
            "field": "_schema",
            "message": f"Unknown doc_type: {doc_type}. Available: {list(SCHEMA_MAP.keys())}",
        })
        return None, errors

    # Strip metadata fields before validation
    clean = {k: v for k, v in raw.items() if not k.startswith("_")}

    # Add required base fields
    clean.setdefault("doc_type", doc_type)
    clean.setdefault("source_file", source_file)
    clean.setdefault("raw_fields", raw)

    # Validate with Pydantic
    try:
        result = schema_cls.model_validate(clean)
        logger.info(f"검증 통과: {doc_type}")
        return result, []
    except ValidationError as e:
        for err in e.errors():
            field_path = " → ".join(str(loc) for loc in err["loc"])
            errors.append({
                "field": field_path,
                "message": err["msg"],
                "type": err["type"],
            })
        logger.warning(f"검증 실패: {doc_type}, {len(errors)}개 오류")
        return None, errors


def format_errors_for_reflection(errors: List[Dict[str, str]]) -> str:
    """Format validation errors as a readable string for the reflector."""
    lines = []
    for i, err in enumerate(errors, 1):
        field = err.get("field", "unknown")
        msg = err.get("message", "unknown error")
        lines.append(f"{i}. [{field}] {msg}")
    return "\n".join(lines)
