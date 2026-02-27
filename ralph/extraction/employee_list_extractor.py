"""
4대보험 가입자 명부 (임직원명부) 추출기.

find_tables()로 직원 테이블을 찾아 성명, 4대보험 취득일 추출.
API 호출 없이 모든 필드 추출.
"""
from __future__ import annotations

import re

from ralph.layout.models import LayoutResult, TableInfo
from .base import BaseExtractor


class EmployeeListExtractor(BaseExtractor):
    """임직원명부 추출기 — 0 API 호출."""

    @property
    def doc_type(self) -> str:
        return "employee_list"

    def extract(self, layout: LayoutResult) -> tuple[dict, float]:
        result: dict = {
            "corp_name": None,
            "business_number": None,
            "issue_date": None,
            "employee_count": 0,
            "employees": [],
        }

        all_tables = layout.all_tables()

        # 메타 테이블에서 사업장 정보 추출
        self._extract_meta(all_tables, result)

        # 직원 테이블 찾아서 파싱
        employees = self._extract_employees(all_tables)
        result["employees"] = employees
        result["employee_count"] = len(employees)

        confidence = self._compute_confidence(result)
        return result, confidence

    def _extract_meta(self, tables: list[TableInfo], result: dict) -> None:
        """메타 테이블(첫 테이블)에서 사업장 정보 추출."""
        for table in tables:
            for row in table.cells:
                for ci, cell in enumerate(row):
                    if not cell:
                        continue
                    text = str(cell).strip()

                    # 사업장명칭
                    if "사업장" in text and "명칭" in text:
                        # 다음 셀에서 값
                        for j in range(ci + 1, len(row)):
                            val = str(row[j] or "").strip()
                            if val and val != text:
                                result["corp_name"] = val
                                break

                    # 사업자등록번호
                    if "사업자등록번호" in text.replace(" ", ""):
                        for j in range(ci + 1, len(row)):
                            val = str(row[j] or "").strip()
                            if val and re.match(r"\d{3}-\d{2}-\d{5}", val):
                                result["business_number"] = val
                                break

                    # 발급일시
                    if "발급일시" in text.replace(" ", ""):
                        for j in range(ci + 1, len(row)):
                            val = str(row[j] or "").strip()
                            if val and re.match(r"\d{4}-\d{2}-\d{2}", val):
                                result["issue_date"] = val
                                break

    def _extract_employees(self, tables: list[TableInfo]) -> list[dict]:
        """직원 테이블에서 직원 목록 추출."""
        employees: list[dict] = []

        for table in tables:
            if table.row_count < 3:
                continue

            # 헤더에 "연번" + "성명"이 있는 테이블 찾기
            header_text = " ".join(
                str(cell or "") for row in table.cells[:2] for cell in row
            ).replace(" ", "")

            if "연번" not in header_text or "성명" not in header_text:
                continue

            # 컬럼 인덱스 찾기: 2행 헤더 구조
            # row 0: 연번, 주민등록번호, 성명, 자격취득일(merged)
            # row 1: (empty), (empty), (empty), 국민연금, 건강보험, 산재보험, 고용보험
            name_col = 2  # 기본값
            pension_col = 3
            health_col = 4
            accident_col = 5
            employ_col = 6

            # 실제 헤더에서 찾기
            if table.row_count >= 2:
                row1 = table.cells[1] if len(table.cells) > 1 else []
                for ci, cell in enumerate(row1):
                    if not cell:
                        continue
                    ct = str(cell).replace(" ", "")
                    if "국민연금" in ct:
                        pension_col = ci
                    elif "건강보험" in ct:
                        health_col = ci
                    elif "산재보험" in ct:
                        accident_col = ci
                    elif "고용보험" in ct:
                        employ_col = ci

            # 데이터 행 파싱 (row 2부터)
            start_row = 2
            for ri in range(start_row, table.row_count):
                row = table.cells[ri]

                # 연번 확인
                seq = str(row[0] or "").strip() if row else ""
                if not seq or not seq.isdigit():
                    # "이하 여 백" 등 종료 행
                    continue

                name = str(row[name_col] or "").strip() if len(row) > name_col else ""
                if not name:
                    continue

                def _get_date(col_idx: int) -> str | None:
                    if len(row) > col_idx:
                        val = str(row[col_idx] or "").strip()
                        if val and val != "-":
                            return val
                    return None

                employees.append({
                    "name": name,
                    "national_pension": _get_date(pension_col),
                    "health_insurance": _get_date(health_col),
                    "industrial_accident": _get_date(accident_col),
                    "employment_insurance": _get_date(employ_col),
                })

        return employees

    def _compute_confidence(self, result: dict) -> float:
        score = 0.0
        total = 4.0

        if result["corp_name"]:
            score += 1.0
        if result["business_number"]:
            score += 1.0
        if result["employees"]:
            score += 1.0
        if result["employee_count"] >= 2:
            score += 1.0

        return min(score / total, 1.0)
