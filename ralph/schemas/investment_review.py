"""투자검토자료 스키마."""
from __future__ import annotations

from pydantic import Field

from .base import ExtractionResult


class InvestmentReview(ExtractionResult):
    """투자검토자료 추출 결과."""
    doc_type: str = "investment_review"

    # 기업 기본정보
    corp_name: str | None = Field(default=None, description="회사명")
    representative: str | None = Field(default=None, description="대표자")
    product_name: str | None = Field(default=None, description="제품/서비스명")
    address: str | None = Field(default=None, description="소재지")
    business_number: str | None = Field(default=None, description="사업자등록번호")
    corp_reg_number: str | None = Field(default=None, description="법인등록번호")
    founded_date: str | None = Field(default=None, description="설립일자")
    capital: str | None = Field(default=None, description="자본금")
    employee_count: str | None = Field(default=None, description="직원수")
    homepage: str | None = Field(default=None, description="홈페이지")

    # 섹션별 구조화 콘텐츠
    sections: list[dict] = Field(default_factory=list, description="섹션별 XML 구조")

    # 핵심 테이블 (별도 추출)
    cap_table: list[dict] = Field(default_factory=list, description="주주현황")
    capital_history: list[dict] = Field(default_factory=list, description="증자이력")
    historical_financials: dict = Field(default_factory=dict, description="과거 재무현황")
    projected_financials: dict = Field(default_factory=dict, description="손익추정")
    image_count: int = Field(default=0, description="이미지 수")
