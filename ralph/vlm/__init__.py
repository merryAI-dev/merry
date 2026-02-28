"""
VLM (Vision Language Model) 폴백 모듈.

규칙 기반 추출 실패 시 이미지 PDF를 VLM으로 처리.
백엔드 교체: RALPH_VLM_BACKEND 환경변수로 제어.
"""
from __future__ import annotations

import os

from .base import BaseVLMCaller, VLMResult


def get_vlm_caller(backend: str | None = None) -> BaseVLMCaller:
    """
    VLM 백엔드 팩토리.

    Args:
        backend: "bedrock_claude" | "sagemaker_qwen" | "bedrock_custom_qwen"
                 None이면 RALPH_VLM_BACKEND 환경변수 참조 (기본: bedrock_claude)

    Returns:
        BaseVLMCaller 인스턴스
    """
    backend = backend or os.getenv("RALPH_VLM_BACKEND", "nova_lite_hybrid")

    if backend == "bedrock_claude":
        from .bedrock_caller import BedrockClaudeVLMCaller
        return BedrockClaudeVLMCaller()

    if backend == "nova_lite_hybrid":
        from .nova_caller import NovaLiteHybridCaller
        return NovaLiteHybridCaller()

    raise ValueError(f"Unknown VLM backend: {backend}")


__all__ = ["BaseVLMCaller", "VLMResult", "get_vlm_caller", "NovaLiteHybridCaller"]
