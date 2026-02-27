"""추출기 베이스 클래스."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ralph.layout.models import LayoutResult


class BaseExtractor(ABC):
    """문서 타입별 추출기의 베이스."""

    @property
    @abstractmethod
    def doc_type(self) -> str:
        """이 추출기가 처리하는 문서 타입 식별자."""
        ...

    @abstractmethod
    def extract(self, layout: LayoutResult) -> tuple[dict, float]:
        """
        구조화 데이터 추출.

        Returns:
            (raw_dict, confidence): 추출 결과와 신뢰도 (0.0~1.0)
        """
        ...

    @property
    def min_confidence(self) -> float:
        """이 이상이면 VLM 폴백 불필요."""
        return 0.7
