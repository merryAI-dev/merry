"""사업자등록증 (Business Registration Certificate) schema."""

import re

from pydantic import Field, field_validator

from .base import ExtractionResult


class BusinessRegistration(ExtractionResult):
    """사업자등록증 추출 스키마."""

    doc_type: str = "business_reg"

    business_number: str = Field(description="사업자등록번호 (XXX-XX-XXXXX)")
    corp_name: str = Field(description="상호 (법인명)")
    representative: str = Field(description="대표자 성명")
    corp_reg_number: str | None = Field(default=None, description="법인등록번호")
    business_type: str | None = Field(default=None, description="업태")
    business_item: str | None = Field(default=None, description="종목")
    address: str | None = Field(default=None, description="사업장 소재지")
    head_office_address: str | None = Field(default=None, description="본점 소재지")
    registration_date: str | None = Field(default=None, description="사업자등록일")
    opening_date: str | None = Field(default=None, description="개업연월일")
    tax_office: str | None = Field(default=None, description="관할 세무서")

    @field_validator("business_number")
    @classmethod
    def validate_biz_number(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) != 10:
            raise ValueError(f"사업자등록번호는 10자리여야 합니다 (현재 {len(digits)}자리: {v})")
        return v

    @field_validator("corp_name")
    @classmethod
    def validate_corp_name(cls, v: str) -> str:
        if not v or len(v.strip()) < 2:
            raise ValueError("상호(법인명)는 2글자 이상이어야 합니다")
        return v.strip()

    @field_validator("representative")
    @classmethod
    def validate_representative(cls, v: str) -> str:
        if not v or len(v.strip()) < 2:
            raise ValueError("대표자명은 2글자 이상이어야 합니다")
        return v.strip()
