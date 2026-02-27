"""4대보험 가입자 명부 (임직원명부) 스키마."""
from __future__ import annotations

from pydantic import Field

from .base import ExtractionResult


class Employee(ExtractionResult):
    """개별 직원 정보."""
    doc_type: str = "employee"
    name: str = Field(description="성명")
    national_pension: str | None = Field(default=None, description="국민연금 취득일")
    health_insurance: str | None = Field(default=None, description="건강보험 취득일")
    industrial_accident: str | None = Field(default=None, description="산재보험 취득일")
    employment_insurance: str | None = Field(default=None, description="고용보험 취득일")


class EmployeeList(ExtractionResult):
    """임직원 명부."""
    doc_type: str = "employee_list"
    corp_name: str | None = Field(default=None, description="사업장 명칭")
    business_number: str | None = Field(default=None, description="사업자등록번호")
    issue_date: str | None = Field(default=None, description="발급일시")
    employee_count: int = Field(default=0, description="총 직원수")
    employees: list[Employee] = Field(default_factory=list, description="직원 목록")
