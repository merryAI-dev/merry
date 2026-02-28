"""
배치 파이프라인 — 다건 문서 일괄 추출.

document_extraction 워커 핸들러에서 호출.
문서별: parse_document() → confidence < 0.7이면 VLM 폴백.
결과: per-doc JSON + 전체 ZIP.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path


class _JSONEncoder(json.JSONEncoder):
    """datetime/date를 ISO 문자열로 직렬화."""
    def default(self, o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return super().default(o)

from ralph.pipeline import parse_document, ParseResult
from ralph.vlm import get_vlm_caller, VLMResult

logger = logging.getLogger(__name__)

# VLM 폴백 임계값
VLM_CONFIDENCE_THRESHOLD = float(os.getenv("RALPH_VLM_THRESHOLD", "0.7"))


@dataclass
class BatchDocInput:
    """배치 파이프라인 입력 문서."""
    file_id: str
    filename: str
    pdf_path: str
    doc_type: str  # 사용자 확정 문서 타입


@dataclass
class DocResult:
    """개별 문서 처리 결과."""
    file_id: str
    filename: str
    doc_type: str
    success: bool
    data: dict
    natural_language: str | None
    confidence: float
    method: str  # "rule" | "vlm" | "failed"
    elapsed_seconds: float
    vlm_usage: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


@dataclass
class BatchResult:
    """배치 처리 전체 결과."""
    total: int
    success_count: int
    failed_count: int
    results: list[DocResult]
    zip_path: str | None  # ZIP 아티팩트 경로
    total_elapsed_seconds: float


def process_single(doc: BatchDocInput) -> DocResult:
    """
    단일 문서 처리: 규칙 기반 → VLM 폴백.
    """
    start = time.perf_counter()

    # Stage 1: 규칙 기반 추출
    parse_result = parse_document(doc.pdf_path, doc.doc_type)

    if parse_result.success and parse_result.confidence >= VLM_CONFIDENCE_THRESHOLD:
        elapsed = time.perf_counter() - start
        return DocResult(
            file_id=doc.file_id,
            filename=doc.filename,
            doc_type=doc.doc_type,
            success=True,
            data=parse_result.data,
            natural_language=parse_result.natural_language,
            confidence=parse_result.confidence,
            method="rule",
            elapsed_seconds=elapsed,
            errors=parse_result.errors,
        )

    # Stage 2: VLM 폴백
    logger.info(
        f"VLM 폴백: {doc.filename} (규칙 confidence={parse_result.confidence:.2f})"
    )
    try:
        vlm = get_vlm_caller()
        vlm_result = vlm.extract(doc.pdf_path, doc.doc_type)
        if vlm_result.success:
            elapsed = time.perf_counter() - start
            return DocResult(
                file_id=doc.file_id,
                filename=doc.filename,
                doc_type=doc.doc_type,
                success=True,
                data=vlm_result.data,
                natural_language=None,
                confidence=vlm_result.confidence,
                method="vlm",
                elapsed_seconds=elapsed,
                vlm_usage=vlm_result.usage,
            )
        else:
            logger.warning(f"VLM도 실패: {doc.filename} — {vlm_result.error}")
    except Exception as e:
        logger.error(f"VLM 호출 예외: {doc.filename} — {e}")

    # 규칙 기반 결과라도 반환 (저신뢰이지만 데이터는 있을 수 있음)
    elapsed = time.perf_counter() - start
    return DocResult(
        file_id=doc.file_id,
        filename=doc.filename,
        doc_type=doc.doc_type,
        success=False,
        data=parse_result.data if parse_result.data else {},
        natural_language=parse_result.natural_language,
        confidence=parse_result.confidence,
        method="failed",
        elapsed_seconds=elapsed,
        errors=parse_result.errors + ["VLM 폴백 실패"],
    )


def process_batch(
    docs: list[BatchDocInput],
    output_dir: str | None = None,
) -> BatchResult:
    """
    다건 문서 배치 처리.

    Args:
        docs: 처리할 문서 리스트
        output_dir: 결과 JSON/ZIP 저장 디렉토리 (None이면 임시 디렉토리)

    Returns:
        BatchResult
    """
    batch_start = time.perf_counter()

    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="ralph_batch_")
    os.makedirs(output_dir, exist_ok=True)

    results: list[DocResult] = []
    for doc in docs:
        logger.info(f"처리 중: {doc.filename} [{doc.doc_type}]")
        result = process_single(doc)
        results.append(result)

        # 개별 JSON 저장
        json_path = os.path.join(output_dir, f"{doc.file_id}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                    "file_id": result.file_id,
                    "filename": result.filename,
                    "doc_type": result.doc_type,
                    "success": result.success,
                    "data": result.data,
                    "natural_language": result.natural_language,
                    "confidence": result.confidence,
                    "method": result.method,
                    "elapsed_seconds": result.elapsed_seconds,
                    "errors": result.errors,
                },
                f,
                cls=_JSONEncoder,
                ensure_ascii=False,
                indent=2,
            )

    # ZIP 패키징
    zip_path = os.path.join(output_dir, "all_results.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for result in results:
            json_file = os.path.join(output_dir, f"{result.file_id}.json")
            if os.path.exists(json_file):
                arcname = f"{result.filename.rsplit('.', 1)[0]}.json"
                zf.write(json_file, arcname)

    batch_elapsed = time.perf_counter() - batch_start
    success_count = sum(1 for r in results if r.success)

    return BatchResult(
        total=len(docs),
        success_count=success_count,
        failed_count=len(docs) - success_count,
        results=results,
        zip_path=zip_path,
        total_elapsed_seconds=batch_elapsed,
    )
