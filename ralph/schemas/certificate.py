"""인증서 스키마 (중소기업확인서, 벤처기업확인서, 기업부설연구소 등)."""
from __future__ import annotations

from pydantic import Field

from .base import ExtractionResult


class CertificateItem(ExtractionResult):
    """개별 인증서."""
    doc_type: str = "certificate_item"
    cert_type: str = Field(description="인증서 종류")
    corp_name: str | None = Field(default=None, description="기업명")
    issue_number: str | None = Field(default=None, description="발급번호")
    valid_from: str | None = Field(default=None, description="유효기간 시작")
    valid_to: str | None = Field(default=None, description="유효기간 종료")


class CertificateSet(ExtractionResult):
    """인증서 모음."""
    doc_type: str = "certificate"
    corp_name: str | None = Field(default=None, description="기업명")
    certificates: list[CertificateItem] = Field(default_factory=list)
