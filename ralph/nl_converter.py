"""
Natural Language Converter: structured JSON → natural language sentences.

Following STORM Parse principles, converts extraction results to
natural language for RAG/embedding optimization.
"""

import logging
from typing import Any

from .schemas import ExtractionResult

logger = logging.getLogger(__name__)


def _fmt_money(v: int | None) -> str:
    """Format money in Korean style."""
    if v is None:
        return "미상"
    if abs(v) >= 1_0000_0000:
        return f"{v / 1_0000_0000:.1f}억원"
    if abs(v) >= 1_0000:
        return f"{v / 1_0000:.0f}만원"
    return f"{v:,}원"


def convert_to_natural_language(result, doc_type: str) -> str:
    """
    구조화 데이터 → 자연어 문장 변환 (RAG 최적화).

    Args:
        result: Pydantic 모델 또는 dict
        doc_type: 문서 타입

    Returns:
        Natural language summary string
    """
    try:
        if isinstance(result, dict):
            return _nl_from_dict(result, doc_type)
        return _nl_generic(result)
    except Exception as e:
        logger.warning(f"NL 변환 실패: {e}")
        return f"[{doc_type}] 자연어 변환 중 오류 발생"


def _nl_from_dict(data: dict, doc_type: str) -> str:
    """dict 데이터에서 자연어 변환."""
    if doc_type == "business_reg":
        corp = data.get("corp_name", "회사")
        biz_num = data.get("business_number", "미상")
        rep = data.get("representative", "미상")
        parts = [f"{corp}의 사업자등록번호는 {biz_num}이며, 대표자는 {rep}입니다."]
        if data.get("business_type"):
            parts.append(f"업태는 {data['business_type']}이고 종목은 {data.get('business_item', '미상')}입니다.")
        if data.get("address"):
            parts.append(f"사업장 소재지는 {data['address']}입니다.")
        if data.get("opening_date"):
            parts.append(f"개업일은 {data['opening_date']}입니다.")
        return " ".join(parts)

    else:
        # 범용 dict 변환
        skip_keys = {"doc_type", "source_file", "extracted_at", "confidence",
                      "raw_fields", "natural_language", "statements"}
        fields = {k: v for k, v in data.items()
                  if v is not None and k not in skip_keys}
        parts = [f"[{doc_type}] 추출 결과:"]
        for k, v in list(fields.items())[:10]:
            parts.append(f"- {k}: {v}")
        return "\n".join(parts)


def _nl_generic(result: ExtractionResult) -> str:
    """Generic fallback for Pydantic models."""
    try:
        fields = {k: v for k, v in result.raw_fields.items()
                  if v is not None and not k.startswith("_")}
    except AttributeError:
        return f"[{getattr(result, 'doc_type', '?')}] 추출 결과"
    parts = [f"[{result.doc_type}] 추출 결과:"]
    for k, v in list(fields.items())[:10]:
        parts.append(f"- {k}: {v}")
    return "\n".join(parts)
