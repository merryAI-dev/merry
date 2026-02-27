"""재무제표증명 (Financial Statement Certificate) schema."""

from pydantic import BaseModel, Field, field_validator

from .base import ExtractionResult


class FinancialStatement(BaseModel):
    """단일 연도 재무제표."""

    year: int = Field(description="회계연도")
    revenue: int | None = Field(default=None, description="매출액 (원)")
    cost_of_revenue: int | None = Field(default=None, description="매출원가 (원)")
    gross_profit: int | None = Field(default=None, description="매출총이익 (원)")
    operating_income: int | None = Field(default=None, description="영업이익 (원)")
    net_income: int | None = Field(default=None, description="당기순이익 (원)")
    total_assets: int | None = Field(default=None, description="자산총계 (원)")
    total_liabilities: int | None = Field(default=None, description="부채총계 (원)")
    equity: int | None = Field(default=None, description="자본총계 (원)")

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: int) -> int:
        if v < 2000 or v > 2030:
            raise ValueError(f"회계연도 {v}는 유효 범위(2000-2030) 밖입니다")
        return v


class FinancialStatementSet(ExtractionResult):
    """연도별 재무제표 세트 (재무제표증명 1건에 여러 연도 포함 가능)."""

    doc_type: str = "financial_stmt"

    corp_name: str | None = Field(default=None, description="법인명")
    statements: list[FinancialStatement] = Field(description="연도별 재무제표 목록")
    statement_type: str | None = Field(
        default=None,
        description="재무제표 유형 (표준재무제표, 간편재무제표 등)",
    )
    issuer: str | None = Field(default=None, description="발급기관 (국세청 등)")
    issue_date: str | None = Field(default=None, description="발급일")

    @field_validator("statements")
    @classmethod
    def validate_statements(cls, v: list[FinancialStatement]) -> list[FinancialStatement]:
        if not v:
            raise ValueError("최소 1개 연도의 재무제표가 필요합니다")
        return v

    @field_validator("corp_name")
    @classmethod
    def validate_corp_name(cls, v: str | None) -> str | None:
        if v is not None and len(v.strip()) < 2:
            raise ValueError("법인명은 2글자 이상이어야 합니다")
        return v.strip() if v else v
