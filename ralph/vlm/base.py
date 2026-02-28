"""
VLM 추상 인터페이스.

규칙 기반 추출이 실패한 이미지 PDF에 대해 VLM으로 폴백할 때 사용.
백엔드 교체 가능: Bedrock Claude 3 Haiku → SageMaker Qwen VL → Bedrock Custom.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class VLMResult:
    """VLM 추출 결과."""
    success: bool
    data: dict
    confidence: float
    model_id: str
    usage: dict[str, int] = field(default_factory=dict)
    error: str | None = None


class BaseVLMCaller(ABC):
    """VLM 호출 추상 베이스 클래스."""

    @abstractmethod
    def extract(
        self,
        pdf_path: str,
        doc_type: str,
        max_pages: int = 5,
    ) -> VLMResult:
        """
        이미지 PDF에서 VLM으로 구조화 데이터 추출.

        Args:
            pdf_path: PDF 파일 경로
            doc_type: 문서 타입 ("business_reg", "financial_stmt" 등)
            max_pages: 최대 처리 페이지 수

        Returns:
            VLMResult
        """
        ...

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """백엔드 식별자 (예: "bedrock_claude", "sagemaker_qwen")."""
        ...
