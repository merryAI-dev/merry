"""
RALPH v2 파이프라인 오케스트레이터.

Stage 0 (레이아웃 분석) → Stage 1 (규칙 기반 추출) → 스키마 검증 → 자연어 변환.
VLM은 규칙 기반 추출이 실패할 때만 사용 (미구현, 추후 Phase 5).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime

from ralph.layout.analyzer import LayoutAnalyzer
from ralph.layout.models import LayoutResult
from ralph.extraction.registry import get_extractor
from ralph.schemas import SCHEMA_MAP
from ralph.nl_converter import convert_to_natural_language


@dataclass
class ParseResult:
    """파싱 결과."""
    success: bool
    doc_type: str
    source_file: str
    data: dict                      # 추출된 구조화 데이터
    natural_language: str | None    # RAG용 자연어
    confidence: float
    elapsed_seconds: float
    api_calls: int = 0              # VLM API 호출 수 (Phase 5에서 사용)
    layout: LayoutResult | None = None
    errors: list[str] = field(default_factory=list)


def parse_document(
    pdf_path: str,
    doc_type: str,
    include_layout: bool = False,
) -> ParseResult:
    """
    문서 파싱 메인 엔트리포인트.

    Args:
        pdf_path: PDF 파일 경로
        doc_type: 문서 타입 ("business_reg", "financial_stmt" 등)
        include_layout: 결과에 레이아웃 데이터 포함 여부

    Returns:
        ParseResult
    """
    start_time = time.perf_counter()
    errors: list[str] = []

    # Stage 0: 레이아웃 분석
    analyzer = LayoutAnalyzer()
    try:
        layout = analyzer.analyze(pdf_path)
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        return ParseResult(
            success=False,
            doc_type=doc_type,
            source_file=pdf_path,
            data={},
            natural_language=None,
            confidence=0.0,
            elapsed_seconds=elapsed,
            errors=[f"레이아웃 분석 실패: {e}"],
        )

    # Stage 1: 규칙 기반 추출
    extractor = get_extractor(doc_type)
    if extractor is None:
        elapsed = time.perf_counter() - start_time
        return ParseResult(
            success=False,
            doc_type=doc_type,
            source_file=pdf_path,
            data={},
            natural_language=None,
            confidence=0.0,
            elapsed_seconds=elapsed,
            layout=layout if include_layout else None,
            errors=[f"지원하지 않는 문서 타입: {doc_type}"],
        )

    try:
        raw_data, confidence = extractor.extract(layout)
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        return ParseResult(
            success=False,
            doc_type=doc_type,
            source_file=pdf_path,
            data={},
            natural_language=None,
            confidence=0.0,
            elapsed_seconds=elapsed,
            layout=layout if include_layout else None,
            errors=[f"추출 실패: {e}"],
        )

    # 스키마 검증
    schema_cls = SCHEMA_MAP.get(doc_type)
    if schema_cls and confidence >= extractor.min_confidence:
        try:
            validation_data = {
                "doc_type": doc_type,
                "source_file": pdf_path,
                "extracted_at": datetime.now().isoformat(),
                "confidence": confidence,
                "raw_fields": raw_data,
                **raw_data,
            }
            validated = schema_cls.model_validate(validation_data)
            data = validated.model_dump()
        except Exception as e:
            errors.append(f"스키마 검증 경고: {e}")
            data = raw_data
    else:
        data = raw_data

    # 자연어 변환
    nl = None
    try:
        nl = convert_to_natural_language(raw_data, doc_type)
    except Exception:
        pass

    elapsed = time.perf_counter() - start_time

    return ParseResult(
        success=confidence >= extractor.min_confidence,
        doc_type=doc_type,
        source_file=pdf_path,
        data=data,
        natural_language=nl,
        confidence=confidence,
        elapsed_seconds=elapsed,
        layout=layout if include_layout else None,
        errors=errors,
    )
