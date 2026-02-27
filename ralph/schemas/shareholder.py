"""주주명부 (Shareholder Registry) schema."""

from pydantic import BaseModel, Field, field_validator, model_validator

from .base import ExtractionResult


class Shareholder(BaseModel):
    """개별 주주 정보."""

    name: str = Field(description="주주명")
    shares: int = Field(description="보유 주식수")
    ratio: float = Field(description="지분율 (%)")
    share_type: str | None = Field(default=None, description="주식 종류 (보통주/우선주)")
    note: str | None = Field(default=None, description="비고")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or len(v.strip()) < 1:
            raise ValueError("주주명이 비어있습니다")
        return v.strip()

    @field_validator("shares")
    @classmethod
    def validate_shares(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"주식수는 음수일 수 없습니다: {v}")
        return v


class ShareholderRegistry(ExtractionResult):
    """주주명부 추출 스키마."""

    doc_type: str = "shareholder"

    corp_name: str = Field(description="법인명")
    shareholders: list[Shareholder] = Field(description="주주 목록")
    total_shares: int = Field(description="발행주식 총수")
    base_date: str | None = Field(default=None, description="기준일")
    capital: int | None = Field(default=None, description="자본금 (원)")

    @field_validator("shareholders")
    @classmethod
    def validate_shareholders(cls, v: list[Shareholder]) -> list[Shareholder]:
        if not v:
            raise ValueError("최소 1명의 주주가 필요합니다")
        return v

    @model_validator(mode="after")
    def check_ratio_sum(self) -> "ShareholderRegistry":
        total_ratio = sum(s.ratio for s in self.shareholders)
        if total_ratio < 90.0 or total_ratio > 110.0:
            raise ValueError(
                f"지분율 합계 {total_ratio:.1f}%는 비정상입니다 (90-110% 범위 벗어남)"
            )
        return self

    @model_validator(mode="after")
    def check_shares_sum(self) -> "ShareholderRegistry":
        total = sum(s.shares for s in self.shareholders)
        if self.total_shares > 0 and abs(total - self.total_shares) > self.total_shares * 0.05:
            raise ValueError(
                f"주식수 합계 {total:,}주와 발행주식총수 {self.total_shares:,}주가 5% 이상 차이"
            )
        return self
