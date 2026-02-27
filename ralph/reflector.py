"""
RALPH Reflector: Analyzes extraction failures and adjusts prompts.

Uses Claude Haiku for cost-efficient reflection.
"""

import json
import logging
import os
from typing import Any, Dict, List

from .stage2 import get_ralph_prompt
from .validator import format_errors_for_reflection

logger = logging.getLogger(__name__)


def _get_anthropic_client():
    """Get Anthropic API client."""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다")
    return anthropic.Anthropic(api_key=api_key)


def reflect_and_adjust(
    errors: List[Dict[str, str]],
    raw_output: Dict[str, Any],
    stage1_md: str,
    doc_type: str,
    attempt: int,
) -> str:
    """
    검증 실패 분석 후 보강 프롬프트 생성.

    Claude Haiku로 저비용 리플렉션:
    1. 어떤 필드가 실패했는지 분석
    2. Stage 1 마크다운에서 해당 데이터가 어디에 있는지 파악
    3. 보강된 지시사항 생성

    Args:
        errors: 검증 오류 목록
        raw_output: Stage 2의 원래 출력
        stage1_md: Stage 1 마크다운
        doc_type: 문서 타입
        attempt: 현재 시도 횟수

    Returns:
        조정된 system prompt (기본 프롬프트 + 추가 지시사항)
    """
    client = _get_anthropic_client()

    error_text = format_errors_for_reflection(errors)

    # Truncate long fields for cost efficiency
    stage1_truncated = stage1_md[:3000] if len(stage1_md) > 3000 else stage1_md
    raw_truncated = json.dumps(raw_output, ensure_ascii=False, default=str)
    if len(raw_truncated) > 2000:
        raw_truncated = raw_truncated[:2000] + "..."

    reflection_prompt = f"""당신은 문서 파서 디버거입니다.

이전 추출 시도에서 다음 검증 오류가 발생했습니다:

## 검증 오류
{error_text}

## 원본 문서 마크다운 (Stage 1 PyMuPDF 추출)
{stage1_truncated}

## 이전 추출 결과 (Stage 2)
{raw_truncated}

## 작업
위 오류를 해결하기 위한 구체적인 추가 지시사항을 작성하세요.
예: "사업자등록번호는 문서 우측 상단에 있으며 XXX-XX-XXXXX 형식입니다"
예: "매출액은 '수익(매출액)' 행에서 찾을 수 있습니다"

간결하게, 지시사항만 작성하세요. 3-5줄 이내."""

    logger.info(f"Reflection 호출 (attempt {attempt})")

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": reflection_prompt}],
    )

    reflection = response.content[0].text.strip()
    logger.info(f"Reflection 결과: {reflection[:200]}")

    # Combine base prompt with reflection adjustments
    base_prompts = get_ralph_prompt(doc_type)
    adjusted_system = (
        base_prompts["system"]
        + f"\n\n## 추가 지시사항 (attempt {attempt + 1}, 이전 오류 기반)\n"
        + reflection
    )

    return adjusted_system
