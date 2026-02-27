"""정관(Articles of Incorporation) 스키마."""
from __future__ import annotations

from pydantic import Field

from .base import ExtractionResult


class Articles(ExtractionResult):
    """정관."""
    doc_type: str = "articles"
    corp_name: str | None = Field(default=None, description="회사 상호")
    corp_name_en: str | None = Field(default=None, description="영문 상호")
    established_date: str | None = Field(default=None, description="제정일 (최초 시행일)")
    latest_revision_date: str | None = Field(default=None, description="최신 개정일")
    revision_history: list[dict] | None = Field(default=None, description="개정 이력 [{date, action}]")
    total_shares_authorized: int | None = Field(default=None, description="발행할 주식 총수")
    par_value: int | None = Field(default=None, description="1주 액면금 (원)")
    initial_shares: int | None = Field(default=None, description="설립시 발행 주식수")
    headquarters_location: str | None = Field(default=None, description="본점 소재지")
    business_purposes: list[str] | None = Field(default=None, description="사업 목적 목록")
    stock_types: list[str] | None = Field(default=None, description="주식 종류 (보통주, 우선주 등)")
    has_stock_options: bool | None = Field(default=None, description="주식매수선택권 조항 여부")
    has_convertible_bonds: bool | None = Field(default=None, description="전환사채 조항 여부")
    director_term_years: int | None = Field(default=None, description="이사 임기 (년)")
    auditor_term_years: int | None = Field(default=None, description="감사 임기 (년)")
    chapter_count: int | None = Field(default=None, description="총 장수")
    article_count: int | None = Field(default=None, description="총 조문수")
    fiscal_year_end: str | None = Field(default=None, description="사업연도 종료 (예: 12월 31일)")
