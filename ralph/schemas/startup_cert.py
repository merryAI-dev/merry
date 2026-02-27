"""창업기업확인서 스키마."""
from __future__ import annotations

from pydantic import Field

from .base import ExtractionResult


class StartupCertificate(ExtractionResult):
    """창업기업확인서."""
    doc_type: str = "startup_cert"
    corp_name: str | None = Field(default=None, description="기업명")
    business_number: str | None = Field(default=None, description="사업자등록번호")
    corp_reg_number: str | None = Field(default=None, description="법인등록번호")
    representative: str | None = Field(default=None, description="대표자")
    address: str | None = Field(default=None, description="주소")
    startup_date: str | None = Field(default=None, description="창업일")
    valid_from: str | None = Field(default=None, description="유효기간 시작")
    valid_to: str | None = Field(default=None, description="유효기간 종료")
    issue_number: str | None = Field(default=None, description="발급번호")
