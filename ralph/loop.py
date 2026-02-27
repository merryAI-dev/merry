"""
RALPH Loop: Retry-Adjusted Loop for Parsing Heuristics.

Core orchestrator that runs:
  Parse → Validate → Reflect → Adjust → Retry
until extraction succeeds or max retries exhausted.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .schemas import ExtractionResult
from .stage1 import Stage1Result, extract_stage1
from .stage2 import extract_stage2
from .validator import validate_extraction
from .reflector import reflect_and_adjust
from .nl_converter import convert_to_natural_language
from .prompt_log import log_prompt_iteration

logger = logging.getLogger(__name__)


@dataclass
class IterationLog:
    """Single RALPH loop iteration record."""

    attempt: int
    raw_output: Dict[str, Any]
    errors: List[Dict[str, str]]
    prompt_used: str  # "default" or adjusted prompt summary
    timestamp: datetime = field(default_factory=datetime.now)
    duration_seconds: float = 0.0
    model: str = ""
    usage: Dict[str, int] = field(default_factory=dict)


@dataclass
class RalphResult:
    """RALPH Loop final result."""

    success: bool
    result: Optional[ExtractionResult]
    attempts: int
    history: List[IterationLog]
    stage1: Optional[Stage1Result] = None
    total_duration_seconds: float = 0.0

    @property
    def cost_summary(self) -> Dict[str, Any]:
        """Estimate API cost from usage data."""
        total_input = sum(it.usage.get("input_tokens", 0) for it in self.history)
        total_output = sum(it.usage.get("output_tokens", 0) for it in self.history)
        return {
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "attempts": self.attempts,
        }


def ralph_loop(
    pdf_path: str,
    doc_type: str,
    max_retries: int = 3,
    on_iteration: Optional[Callable[[IterationLog], None]] = None,
) -> RalphResult:
    """
    RALPH Loop: Parse → Validate → Reflect → Adjust → Retry.

    Args:
        pdf_path: PDF 파일 경로
        doc_type: 문서 타입 (business_reg, financial_stmt, shareholder)
        max_retries: 최대 재시도 횟수 (default: 3)
        on_iteration: 각 이터레이션 완료 시 콜백

    Returns:
        RalphResult with success/failure and full history
    """
    loop_start = time.time()
    source_file = Path(pdf_path).name

    logger.info(f"RALPH Loop 시작: {source_file} (type={doc_type}, max_retries={max_retries})")

    # Stage 1: Rule-based extraction (1회만, 무료)
    stage1 = extract_stage1(pdf_path)

    prompt_override: Optional[str] = None
    history: List[IterationLog] = []

    for attempt in range(1, max_retries + 1):
        iter_start = time.time()
        logger.info(f"--- Attempt {attempt}/{max_retries} ---")

        # Stage 2: VLM extraction
        try:
            raw = extract_stage2(pdf_path, stage1, doc_type, prompt_override)
        except Exception as e:
            logger.error(f"Stage2 실패: {e}")
            iteration = IterationLog(
                attempt=attempt,
                raw_output={"_error": str(e)},
                errors=[{"field": "_stage2", "message": str(e)}],
                prompt_used="error",
                duration_seconds=time.time() - iter_start,
            )
            history.append(iteration)
            if on_iteration:
                on_iteration(iteration)
            continue

        # Extract metadata
        model = raw.pop("_model", "")
        usage = raw.pop("_usage", {})

        # Validate against schema
        result, errors = validate_extraction(raw, doc_type, source_file)

        iteration = IterationLog(
            attempt=attempt,
            raw_output=raw,
            errors=errors,
            prompt_used="default" if prompt_override is None else f"adjusted_v{attempt}",
            duration_seconds=time.time() - iter_start,
            model=model,
            usage=usage,
        )
        history.append(iteration)

        if on_iteration:
            on_iteration(iteration)

        # Success!
        if not errors and result is not None:
            # Natural language conversion
            try:
                nl = convert_to_natural_language(result, doc_type)
                result.natural_language = nl
            except Exception as e:
                logger.warning(f"자연어 변환 실패 (무시): {e}")

            total_duration = time.time() - loop_start
            logger.info(
                f"RALPH Loop 성공: {attempt}회 시도, {total_duration:.1f}초"
            )

            # Log to prompt log
            log_prompt_iteration(pdf_path, doc_type, history, success=True)

            return RalphResult(
                success=True,
                result=result,
                attempts=attempt,
                history=history,
                stage1=stage1,
                total_duration_seconds=total_duration,
            )

        # Reflect and adjust prompt for next attempt
        if attempt < max_retries:
            logger.info(f"검증 실패 ({len(errors)}개 오류), 리플렉션 시작...")
            try:
                prompt_override = reflect_and_adjust(
                    errors=errors,
                    raw_output=raw,
                    stage1_md=stage1.full_markdown,
                    doc_type=doc_type,
                    attempt=attempt,
                )
            except Exception as e:
                logger.error(f"리플렉션 실패: {e}")

    # Max retries exhausted
    total_duration = time.time() - loop_start
    logger.warning(
        f"RALPH Loop 실패: {max_retries}회 시도 소진, {total_duration:.1f}초"
    )

    log_prompt_iteration(pdf_path, doc_type, history, success=False)

    return RalphResult(
        success=False,
        result=None,
        attempts=max_retries,
        history=history,
        stage1=stage1,
        total_duration_seconds=total_duration,
    )
