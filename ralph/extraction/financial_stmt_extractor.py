"""
재무제표 전용 추출기.

두 가지 포맷 지원:
1. 표준재무제표증명 (3페이지, 좌우 2열 구조)
2. 재무제표확인 (8페이지, 멀티라인 셀, 당기/전기 2개년)

find_tables()로 추출한 테이블에서 한국어 재무 항목을 매핑.
API 호출 없이 모든 필드 추출.
"""
from __future__ import annotations

import re

from ralph.layout.models import LayoutResult, ZoneType, TableInfo
from ralph.utils.korean_text import parse_korean_number, normalize_business_number
from .base import BaseExtractor


# 멀티라인 셀에서 라벨 분류용 패턴
_ROMAN_PREFIX = re.compile(r"^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩIVXivx]+\.")
_PAREN_PREFIX = re.compile(r"^\(\d+\)")
_SUMMARY_SUFFIX = re.compile(r"총계$|총이익$|총손익$|총손실$|매출원가$|제조원가$")
_HEADER_LABELS = {"자산", "부채", "자본", "손익"}


class FinancialStmtExtractor(BaseExtractor):
    """재무제표 추출기 — 0 API 호출."""

    @property
    def doc_type(self) -> str:
        return "financial_stmt"

    # 손익계산서 행 라벨 → 스키마 필드 매핑
    INCOME_STMT_MAP: dict[str, list[str]] = {
        "revenue": ["I.매출액", "Ⅰ.매출액", "매출액"],
        "cost_of_revenue": ["Ⅱ.매출원가", "II.매출원가", "매출원가"],
        "gross_profit": ["Ⅲ.매출총손익", "III.매출총손익", "매출총이익", "매출총손익"],
        "operating_income": [
            "Ⅴ.영업손익", "V.영업손익", "영업이익", "영업손익",
            "Ⅴ.영업손실", "V.영업손실", "영업손실",
        ],
        "net_income": [
            "Ⅹ.당기순손익", "X.당기순손익", "당기순이익", "당기순손익",
            "Ⅹ.당기순손실", "X.당기순손실", "당기순손실",
        ],
    }

    # 손실 키워드 — 이 라벨로 매치되면 값을 음수로 변환
    LOSS_KEYWORDS = {"영업손실", "당기순손실"}

    # 재무상태표 행 라벨 → 스키마 필드 매핑
    BALANCE_SHEET_MAP: dict[str, list[str]] = {
        "total_assets": ["자산총계"],
        "total_liabilities": ["부채총계"],
        "equity": ["자본총계"],
    }

    # 이 패턴이 포함된 라벨은 매칭 제외
    BALANCE_SHEET_EXCLUDES: dict[str, list[str]] = {
        "equity": ["부채와자본총계", "부채및자본총계"],
    }

    def extract(self, layout: LayoutResult) -> tuple[dict, float]:
        """재무제표 필드 추출."""
        result: dict = {
            "corp_name": None,
            "statement_type": None,
            "issuer": "국세청",
            "issue_date": None,
            "statements": [],
        }

        all_tables = layout.all_tables()

        # 포맷 감지
        fmt = self._detect_format(all_tables)
        result["statement_type"] = fmt

        if fmt == "재무제표확인":
            return self._extract_confirmation_format(all_tables, layout, result)
        else:
            return self._extract_standard_format(all_tables, layout, result)

    # ──────────────────────────────────────────────
    # 포맷 감지
    # ──────────────────────────────────────────────

    def _detect_format(self, tables: list[TableInfo]) -> str:
        if not tables:
            return "표준재무제표증명"
        cover_text = "".join(
            str(cell).replace(" ", "")
            for row in tables[0].cells for cell in row if cell
        )
        if "재무제표확인" in cover_text:
            return "재무제표확인"
        return "표준재무제표증명"

    # ──────────────────────────────────────────────
    # 표준재무제표증명 (3페이지, 좌우 2열)
    # ──────────────────────────────────────────────

    def _extract_standard_format(
        self, all_tables: list[TableInfo], layout: LayoutResult, result: dict
    ) -> tuple[dict, float]:
        if all_tables:
            self._extract_cover_metadata(all_tables[0], result)

        statement: dict = {}
        for table in all_tables:
            table_type = self._classify_financial_table(table)
            if table_type == "balance_sheet":
                statement.update(self._extract_balance_sheet_standard(table))
            elif table_type == "income_statement":
                statement.update(self._extract_income_statement_standard(table))

        year = self._extract_year(all_tables, layout)
        if year:
            statement["year"] = year

        if statement:
            result["statements"] = [statement]

        key_fields = ["revenue", "operating_income", "net_income",
                      "total_assets", "total_liabilities", "equity"]
        found = sum(1 for f in key_fields if statement.get(f) is not None)
        return result, found / len(key_fields)

    # ──────────────────────────────────────────────
    # 재무제표확인 (8페이지, 멀티라인 셀, 당기/전기)
    # ──────────────────────────────────────────────

    def _extract_confirmation_format(
        self, all_tables: list[TableInfo], layout: LayoutResult, result: dict
    ) -> tuple[dict, float]:
        if all_tables:
            self._extract_cover_metadata(all_tables[0], result)

        current_period: dict = {}
        prior_period: dict = {}

        for table in all_tables:
            table_type = self._classify_financial_table(table)
            if table_type == "balance_sheet":
                cur, pri = self._extract_multiline_table(table, self.BALANCE_SHEET_MAP)
                current_period.update(cur)
                prior_period.update(pri)
            elif table_type == "income_statement":
                cur, pri = self._extract_multiline_table(table, self.INCOME_STMT_MAP)
                current_period.update(cur)
                prior_period.update(pri)

        years = self._extract_years_from_periods(all_tables)

        statements = []
        if current_period:
            current_period["year"] = years.get("current", 0)
            statements.append(current_period)
        if prior_period:
            prior_period["year"] = years.get("prior", 0)
            statements.append(prior_period)

        result["statements"] = statements

        key_fields = ["revenue", "operating_income", "net_income",
                      "total_assets", "total_liabilities", "equity"]
        total_found = 0
        for stmt in statements:
            total_found += sum(1 for f in key_fields if stmt.get(f) is not None)
        max_possible = len(key_fields) * max(len(statements), 1)
        return result, total_found / max_possible

    def _extract_multiline_table(
        self, table: TableInfo, field_map: dict[str, list[str]]
    ) -> tuple[dict, dict]:
        """멀티라인 셀 테이블에서 당기/전기 데이터 추출.

        핵심: 라벨은 한 행의 col 0에 모여있고, summary 값은 여러 행에 분산됨.
        1) 가장 많은 라벨을 가진 행에서 전체 라벨 수집
        2) 모든 행에서 summary 값 수집 (순서대로)
        3) 라벨 분류(header/summary/detail)로 순차 매칭
        """
        current_data: dict = {}
        prior_data: dict = {}

        # 1) 라벨 수집 — 가장 많은 라인을 가진 col 0 셀
        all_labels: list[str] = []
        for row in table.cells:
            if not row or not row[0]:
                continue
            lines = str(row[0]).split("\n")
            if len(lines) > len(all_labels):
                all_labels = lines

        if len(all_labels) < 3:
            return current_data, prior_data

        # 2) Summary 컬럼 위치 결정 (첫 데이터 행에서)
        cur_col, pri_col = self._find_summary_col_indices(table)

        # 3) 모든 행에서 summary 값 수집
        all_cur_values: list[str] = []
        all_pri_values: list[str] = []

        for row in table.cells:
            if not row:
                continue
            # 당기 summary
            if cur_col is not None and cur_col < len(row) and row[cur_col]:
                text = str(row[cur_col]).strip()
                if re.search(r"\d", text) and "금액" not in text.replace(" ", ""):
                    all_cur_values.extend(text.split("\n"))
            # 전기 summary
            if pri_col is not None and pri_col < len(row) and row[pri_col]:
                text = str(row[pri_col]).strip()
                if re.search(r"\d", text) and "금액" not in text.replace(" ", ""):
                    all_pri_values.extend(text.split("\n"))

        # 4) 라벨 ↔ summary 값 순차 매칭
        cur_idx = 0
        pri_idx = 0

        for label in all_labels:
            clean = label.replace(" ", "")
            if not clean:
                continue
            label_type = self._classify_label(clean)

            if label_type == "header":
                continue
            elif label_type == "summary":
                cur_val = all_cur_values[cur_idx] if cur_idx < len(all_cur_values) else None
                pri_val = all_pri_values[pri_idx] if pri_idx < len(all_pri_values) else None
                cur_idx += 1
                pri_idx += 1

                field = self._match_field_label(clean, field_map)
                if field:
                    is_loss = any(lk in clean for lk in self.LOSS_KEYWORDS)
                    if cur_val:
                        parsed = parse_korean_number(cur_val)
                        if parsed is not None:
                            current_data[field] = -abs(parsed) if is_loss else parsed
                    if pri_val:
                        parsed = parse_korean_number(pri_val)
                        if parsed is not None:
                            prior_data[field] = -abs(parsed) if is_loss else parsed

        return current_data, prior_data

    def _find_summary_col_indices(self, table: TableInfo) -> tuple[int | None, int | None]:
        """멀티라인 테이블에서 당기/전기 summary 컬럼 인덱스 결정.

        규칙: 각 기간 그룹에서 가장 오른쪽(높은 인덱스) 값 컬럼이 summary.
        """
        # 가장 많은 값 컬럼이 있는 행 찾기
        best_row = None
        best_count = 0
        for row in table.cells:
            if not row:
                continue
            count = sum(1 for ci in range(1, len(row))
                       if row[ci] and re.search(r"\d", str(row[ci])))
            if count > best_count:
                best_count = count
                best_row = row

        if not best_row or best_count < 2:
            return None, None

        # 값이 있는 컬럼 인덱스 수집
        value_col_indices: list[int] = []
        for ci in range(1, len(best_row)):
            cell = best_row[ci]
            if cell and re.search(r"\d", str(cell)):
                text = str(cell).replace(" ", "")
                if "금액" not in text and "당기" not in text and "전기" not in text:
                    value_col_indices.append(ci)

        if len(value_col_indices) < 2:
            return value_col_indices[0] if value_col_indices else None, None

        # 앞쪽 절반 = 당기, 뒤쪽 절반 = 전기
        mid = len(value_col_indices) // 2
        cur_group = value_col_indices[:mid]
        pri_group = value_col_indices[mid:]

        # 각 그룹의 오른쪽(최대 인덱스) = summary
        cur_col = max(cur_group) if cur_group else None
        pri_col = max(pri_group) if pri_group else None

        return cur_col, pri_col

    @staticmethod
    def _classify_label(clean_label: str) -> str:
        """멀티라인 셀 라벨 → header/summary/detail 분류."""
        if clean_label in _HEADER_LABELS:
            return "header"
        if _ROMAN_PREFIX.search(clean_label):
            return "summary"
        if _PAREN_PREFIX.search(clean_label):
            return "summary"
        if _SUMMARY_SUFFIX.search(clean_label):
            return "summary"
        return "detail"

    def _extract_years_from_periods(self, tables: list[TableInfo]) -> dict[str, int]:
        """테이블 헤더에서 당기/전기 연도 추출."""
        years: dict[str, int] = {}
        for table in tables:
            for row in table.cells:
                for cell in row:
                    if not cell:
                        continue
                    text = str(cell).replace(" ", "")

                    # "제4(당)기2025년..." or "당기2025년..."
                    m = re.search(r"당\)?기(\d{4})년", text)
                    if m and "current" not in years:
                        years["current"] = int(m.group(1))

                    m = re.search(r"전\)?기(\d{4})년", text)
                    if m and "prior" not in years:
                        years["prior"] = int(m.group(1))

                    # "제4기 2025년 06월 30일 현재"
                    if "현재" in text and "current" not in years:
                        m = re.search(r"(\d{4})년", text)
                        if m:
                            years["current"] = int(m.group(1))

        return years

    # ──────────────────────────────────────────────
    # 공통 유틸
    # ──────────────────────────────────────────────

    def _classify_financial_table(self, table: TableInfo) -> str:
        """테이블 유형 분류: cover, balance_sheet, income_statement."""
        all_text = "".join(
            str(cell).replace(" ", "")
            for row in table.cells for cell in row if cell
        )

        # 1) cover 우선 (재무제표 명칭 목록에 "재무상태표" 등이 포함되어 오분류 방지)
        if "발급번호" in all_text or "처리기간" in all_text:
            return "cover"

        # 2) 합계잔액시산표 / 결손금처리계산서 제외
        if "합계잔액시산표" in all_text or "시산표" in all_text:
            return "unknown"
        if "결손금처리" in all_text or "이익잉여금처분" in all_text:
            return "unknown"

        # 3) 명시적 제목
        if "재무상태표" in all_text or "대차대조표" in all_text:
            return "balance_sheet"
        if "손익계산서" in all_text:
            return "income_statement"

        # 4) 내용 추론 — B/S 키워드 우선 (자본총계/부채총계는 B/S 고유)
        if any(kw in all_text for kw in ["자본총계", "부채총계", "자산총계",
                                          "유동자산", "비유동자산"]):
            return "balance_sheet"
        if any(kw in all_text for kw in ["매출액", "영업손익", "영업손실",
                                          "매출원가", "매출총이익"]):
            return "income_statement"

        return "unknown"

    def _extract_cover_metadata(self, table: TableInfo, result: dict) -> None:
        """표지 테이블에서 메타데이터 추출."""
        for row in table.cells:
            for ci, cell in enumerate(row):
                if not cell:
                    continue
                cell_text = str(cell).strip()
                cell_nospace = cell_text.replace(" ", "")

                if "상호" in cell_nospace or "법인명" in cell_nospace:
                    for ni in range(ci + 1, len(row)):
                        val = str(row[ni] or "").strip()
                        if val:
                            val = re.sub(r"\(합산\)", "", val).strip()
                            result["corp_name"] = val.replace("\n", " ")
                            break

                if "사업자" in cell_nospace and "등록" in cell_nospace and "번호" in cell_nospace:
                    for ni in range(ci + 1, len(row)):
                        val = str(row[ni] or "").strip()
                        if val:
                            result["business_number"] = normalize_business_number(val) or val
                            break

                if "대표자" in cell_nospace or "성명" in cell_nospace:
                    for ni in range(ci + 1, len(row)):
                        val = str(row[ni] or "").strip()
                        if val and "등록번호" not in val:
                            result["representative"] = val
                            break

                if "신고일" in cell_nospace or "발급일" in cell_nospace:
                    for ni in range(ci + 1, len(row)):
                        val = str(row[ni] or "").strip()
                        if val:
                            m = re.search(r"(\d{4})\.\s*(\d{2})\.\s*(\d{2})", val)
                            if m:
                                result["issue_date"] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                            break

    # ── 표준재무제표증명 전용 ──

    def _extract_income_statement_standard(self, table: TableInfo) -> dict:
        """표준손익계산서 (좌우 2열 구조)."""
        data = {}
        for row in table.cells:
            left_label = str(row[0] or "").strip() if len(row) > 0 else ""
            left_value = str(row[3] or "").strip() if len(row) > 3 else ""
            if left_label:
                field = self._match_field_label(left_label, self.INCOME_STMT_MAP)
                if field and left_value:
                    parsed = parse_korean_number(left_value)
                    if parsed is not None:
                        data[field] = parsed

            right_label = ""
            right_value = ""
            if len(row) > 4:
                right_label = str(row[4] or "").strip()
                if not right_label and len(row) > 5:
                    right_label = str(row[5] or "").strip()
            if len(row) > 7:
                right_value = str(row[7] or "").strip()
                if not right_value and len(row) > 6:
                    right_value = str(row[6] or "").strip()
            if right_label:
                field = self._match_field_label(right_label, self.INCOME_STMT_MAP)
                if field and right_value:
                    parsed = parse_korean_number(right_value)
                    if parsed is not None:
                        data[field] = parsed
        return data

    def _extract_balance_sheet_standard(self, table: TableInfo) -> dict:
        """표준재무상태표 (좌우 2열 구조)."""
        data = {}
        for row in table.cells:
            left_label = str(row[0] or "").strip() if len(row) > 0 else ""
            left_value = str(row[3] or "").strip() if len(row) > 3 else ""
            if left_label:
                field = self._match_field_label(left_label, self.BALANCE_SHEET_MAP)
                if field and left_value:
                    parsed = parse_korean_number(left_value)
                    if parsed is not None:
                        data[field] = parsed

            if len(row) > 4:
                right_label = str(row[4] or "").strip()
                if not right_label and len(row) > 5:
                    right_label = str(row[5] or "").strip()
                right_value = ""
                if len(row) > 8:
                    right_value = str(row[8] or "").strip()
                elif len(row) > 7:
                    right_value = str(row[7] or "").strip()
                if right_label:
                    field = self._match_field_label(right_label, self.BALANCE_SHEET_MAP)
                    if field and right_value:
                        parsed = parse_korean_number(right_value)
                        if parsed is not None:
                            data[field] = parsed
        return data

    def _extract_year(self, tables: list[TableInfo], layout: LayoutResult) -> int | None:
        """사업 연도 추출 (표준재무제표증명용)."""
        for table in tables:
            for row in table.cells:
                for cell in row:
                    if not cell:
                        continue
                    text = str(cell)
                    m = re.search(r"(\d{4})년\s*12월\s*31일", text)
                    if m:
                        return int(m.group(1))
                    m = re.search(r"(\d{4})\.01\.01\s*[~～]\s*\d{4}\.12\.31", text)
                    if m:
                        return int(m.group(1))
                    m = re.search(r"(\d{4})\.\d{2}\.\d{2}\s*[~～\n]\s*(\d{4})\.\d{2}\.\d{2}", text)
                    if m:
                        return int(m.group(2))

        full_text = layout.full_text
        m = re.search(r"(\d{4})년\s*\d{1,2}월\s*\d{1,2}일\s*부터", full_text)
        if m:
            return int(m.group(1))
        return None

    @classmethod
    def _match_field_label(
        cls, label: str, field_map: dict[str, list[str]]
    ) -> str | None:
        """라벨 텍스트를 필드명으로 매핑."""
        label_clean = re.sub(r"\s+", "", label)
        for field_name, keywords in field_map.items():
            excludes = cls.BALANCE_SHEET_EXCLUDES.get(field_name, [])
            if any(re.sub(r"\s+", "", ex) in label_clean for ex in excludes):
                continue
            for kw in keywords:
                kw_clean = re.sub(r"\s+", "", kw)
                if kw_clean in label_clean:
                    return field_name
        return None
