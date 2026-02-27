"""
RALPH: Retry-Adjusted Loop for Parsing Heuristics

STORM Parse 스타일 2-stage 문서 파서 + RALPH Loop (성공할 때까지 반복).
- Stage 1: PyMuPDF rule-based 마크다운 추출 (무료)
- Stage 2: Claude Vision 시맨틱 해석 + 구조화 추출
- RALPH Loop: 추출 → 스키마 검증 → 실패시 reflection → 프롬프트 조정 → 재시도
"""

from .loop import ralph_loop, RalphResult

__all__ = ["ralph_loop", "RalphResult"]
