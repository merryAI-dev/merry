"""
Financial Table Extractor

Dolphin 출력에서 재무제표 테이블을 감지하고 구조화된 데이터로 변환합니다.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from .config import FINANCIAL_TABLE_KEYWORDS

logger = logging.getLogger(__name__)


class FinancialTableExtractor:
    """재무제표 테이블 추출기

    - IS (손익계산서)
    - BS (재무상태표)
    - CF (현금흐름표)
    - Cap Table (주주현황)
    """

    def __init__(self):
        self.keywords = FINANCIAL_TABLE_KEYWORDS

    def extract_financial_tables(
        self, dolphin_output: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Dolphin 출력에서 재무제표 추출

        Args:
            dolphin_output: Dolphin 처리 결과

        Returns:
            {
                "income_statement": {...},
                "balance_sheet": {...},
                "cash_flow": {...},
                "cap_table": {...},
                "other_tables": [...]
            }
        """
        # 모든 테이블 수집
        all_tables = self._collect_all_tables(dolphin_output)

        if not all_tables:
            return {
                "income_statement": {"found": False},
                "balance_sheet": {"found": False},
                "cash_flow": {"found": False},
                "cap_table": {"found": False},
                "other_tables": [],
            }

        # 테이블 분류
        classified = self._classify_tables(all_tables)

        return {
            "income_statement": self._parse_income_statement(classified.get("is")),
            "balance_sheet": self._parse_balance_sheet(classified.get("bs")),
            "cash_flow": self._parse_cash_flow(classified.get("cf")),
            "cap_table": self._parse_cap_table(classified.get("cap")),
            "other_tables": classified.get("other", []),
        }

    def _collect_all_tables(
        self, dolphin_output: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """모든 테이블 요소 수집"""
        tables = []

        structured = dolphin_output.get("structured_content", {})
        pages = structured.get("pages", [])

        for page in pages:
            page_num = page.get("page_num", 0)
            elements = page.get("elements", [])

            for elem in elements:
                if elem.get("type") == "table":
                    tables.append({
                        "page": page_num,
                        "content": elem.get("content", {}),
                        "raw": elem,
                    })

        return tables

    def _classify_tables(
        self, tables: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """테이블을 유형별로 분류"""
        result = {"is": None, "bs": None, "cf": None, "cap": None, "other": []}

        for table in tables:
            content = table.get("content", {})
            text_content = self._table_to_text(content).lower()

            # 손익계산서 감지
            if self._matches_keywords(text_content, "income_statement"):
                if result["is"] is None:
                    result["is"] = table
                    continue

            # 재무상태표 감지
            if self._matches_keywords(text_content, "balance_sheet"):
                if result["bs"] is None:
                    result["bs"] = table
                    continue

            # 현금흐름표 감지
            if self._matches_keywords(text_content, "cash_flow"):
                if result["cf"] is None:
                    result["cf"] = table
                    continue

            # Cap Table 감지
            if self._matches_keywords(text_content, "cap_table"):
                if result["cap"] is None:
                    result["cap"] = table
                    continue

            # 분류되지 않은 테이블
            result["other"].append(table)

        return result

    def _matches_keywords(self, text: str, table_type: str) -> bool:
        """키워드 매칭 확인"""
        keywords = self.keywords.get(table_type, [])
        text_lower = text.lower()

        matched = sum(1 for kw in keywords if kw.lower() in text_lower)
        return matched >= 2  # 최소 2개 키워드 매칭

    def _table_to_text(self, content: Dict[str, Any]) -> str:
        """테이블 내용을 텍스트로 변환"""
        text_parts = []

        # Markdown 형식
        if "markdown" in content:
            text_parts.append(content["markdown"])

        # 행 데이터
        if "rows" in content:
            for row in content["rows"]:
                text_parts.append(" ".join(str(cell) for cell in row))

        return " ".join(text_parts)

    def _parse_income_statement(
        self, table: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """손익계산서 파싱"""
        if not table:
            return {"found": False}

        content = table.get("content", {})
        rows = content.get("rows", [])

        if not rows:
            return {"found": False, "page": table.get("page")}

        # 헤더에서 연도 추출
        headers = rows[0] if rows else []
        years = self._extract_years(headers)

        # 주요 지표 추출
        metrics = {}
        for row in rows[1:]:
            if len(row) < 2:
                continue

            label = str(row[0]).strip().lower()
            values = row[1:]

            if any(kw in label for kw in ["매출", "revenue", "수익"]):
                metrics["revenue"] = self._parse_numeric_values(values)
            elif any(kw in label for kw in ["영업이익", "operating"]):
                metrics["operating_income"] = self._parse_numeric_values(values)
            elif any(kw in label for kw in ["당기순이익", "순이익", "net income"]):
                metrics["net_income"] = self._parse_numeric_values(values)
            elif any(kw in label for kw in ["영업이익률", "operating margin"]):
                metrics["operating_margin"] = self._parse_numeric_values(values)

        return {
            "found": True,
            "page": table.get("page"),
            "years": years,
            "metrics": metrics,
            "raw_table": content,
        }

    def _parse_balance_sheet(
        self, table: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """재무상태표 파싱"""
        if not table:
            return {"found": False}

        content = table.get("content", {})
        rows = content.get("rows", [])

        if not rows:
            return {"found": False, "page": table.get("page")}

        headers = rows[0] if rows else []
        years = self._extract_years(headers)

        metrics = {}
        for row in rows[1:]:
            if len(row) < 2:
                continue

            label = str(row[0]).strip().lower()
            values = row[1:]

            if any(kw in label for kw in ["총자산", "total assets", "자산총계"]):
                metrics["total_assets"] = self._parse_numeric_values(values)
            elif any(kw in label for kw in ["총부채", "total liabilities", "부채총계"]):
                metrics["total_liabilities"] = self._parse_numeric_values(values)
            elif any(kw in label for kw in ["자본", "equity", "자본총계"]):
                metrics["total_equity"] = self._parse_numeric_values(values)

        return {
            "found": True,
            "page": table.get("page"),
            "years": years,
            "metrics": metrics,
            "raw_table": content,
        }

    def _parse_cash_flow(
        self, table: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """현금흐름표 파싱"""
        if not table:
            return {"found": False}

        content = table.get("content", {})
        rows = content.get("rows", [])

        if not rows:
            return {"found": False, "page": table.get("page")}

        headers = rows[0] if rows else []
        years = self._extract_years(headers)

        metrics = {}
        for row in rows[1:]:
            if len(row) < 2:
                continue

            label = str(row[0]).strip().lower()
            values = row[1:]

            if any(kw in label for kw in ["영업활동", "operating"]):
                metrics["operating_cf"] = self._parse_numeric_values(values)
            elif any(kw in label for kw in ["투자활동", "investing"]):
                metrics["investing_cf"] = self._parse_numeric_values(values)
            elif any(kw in label for kw in ["재무활동", "financing"]):
                metrics["financing_cf"] = self._parse_numeric_values(values)

        return {
            "found": True,
            "page": table.get("page"),
            "years": years,
            "metrics": metrics,
            "raw_table": content,
        }

    def _parse_cap_table(
        self, table: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Cap Table 파싱"""
        if not table:
            return {"found": False}

        content = table.get("content", {})
        rows = content.get("rows", [])

        if not rows:
            return {"found": False, "page": table.get("page")}

        # 주주 정보 추출
        shareholders = []
        total_shares = 0

        for row in rows[1:]:  # 헤더 제외
            if len(row) < 2:
                continue

            name = str(row[0]).strip()
            shares = self._parse_single_numeric(row[1]) if len(row) > 1 else 0
            ratio = self._parse_single_numeric(row[2]) if len(row) > 2 else 0

            if name and shares > 0:
                shareholders.append({
                    "name": name,
                    "shares": shares,
                    "ratio": ratio,
                })
                total_shares += shares

        return {
            "found": True,
            "page": table.get("page"),
            "shareholders": shareholders,
            "total_shares": total_shares,
            "raw_table": content,
        }

    def _extract_years(self, headers: List[str]) -> List[str]:
        """헤더에서 연도 추출"""
        years = []
        year_pattern = re.compile(r"20\d{2}[E예상]?")

        for header in headers:
            matches = year_pattern.findall(str(header))
            years.extend(matches)

        return list(dict.fromkeys(years))  # 중복 제거, 순서 유지

    def _parse_numeric_values(self, values: List[Any]) -> List[Optional[float]]:
        """숫자 값 리스트 파싱"""
        return [self._parse_single_numeric(v) for v in values]

    def _parse_single_numeric(self, value: Any) -> Optional[float]:
        """단일 숫자 값 파싱 (복합 한국어 단위 지원).

        "5억2천만" → 520,000,000
        "1조3천억" → 1,300,000,000,000
        "32억4500만원" → 3,245,000,000
        """
        if value is None:
            return None

        text = str(value).strip()

        # 빈 값
        if not text or text in ["-", "N/A", "n/a", ""]:
            return None

        # 부호 감지 후 제거
        negative = text.startswith("-") or text.startswith("△") or text.startswith("▲")
        text = text.lstrip("-△▲")

        # 통화/단위 접미사 제거
        text = re.sub(r"[원달러$%\s,]", "", text)

        # 한국어 단위가 하나라도 있으면 복합 파싱
        if re.search(r"[조억천백만]", text):
            return self._parse_korean_compound(text, negative)

        # 순수 숫자
        try:
            num_match = re.search(r"-?[\d.]+", text)
            if num_match:
                result = float(num_match.group())
                return -result if negative else result
        except ValueError:
            pass

        return None

    @staticmethod
    def _parse_coeff(num_part: str) -> float:
        """계수 문자열에서 천/백 sub-multiplier를 처리.

        "3천" → 3000, "2천5백" → 2500, "15백" → 1500, "42" → 42, "" → 1
        """
        if not num_part:
            return 1.0

        total = 0.0
        remaining = num_part

        for sub_unit, sub_mult in [("천", 1000), ("백", 100)]:
            if sub_unit in remaining:
                parts = remaining.split(sub_unit, 1)
                left = parts[0].strip()
                remaining = parts[1] if len(parts) > 1 else ""
                sub_coeff = 1.0
                if left:
                    m = re.search(r"[\d.]+", left)
                    if m:
                        sub_coeff = float(m.group())
                total += sub_coeff * sub_mult

        if remaining:
            m = re.search(r"[\d.]+", remaining)
            if m:
                total += float(m.group())

        return total if total > 0 else 1.0

    def _parse_korean_compound(self, text: str, negative: bool = False) -> Optional[float]:
        """복합 한국어 숫자를 순차 파싱.

        큰 단위부터 분리하여 누적합산:
        조(1e12) → 억(1e8) → 천만(1e7) → 백만(1e6) → 만(1e4)

        각 단위 앞의 계수는 천/백 sub-multiplier도 처리:
        "3천억" → 3000 * 1e8 = 3e11
        """
        total = 0.0
        remaining = text

        # (단위문자, 승수) — 큰 단위부터, 천만/백만은 만 앞에 처리
        units = [
            ("조", 1_000_000_000_000),
            ("억", 100_000_000),
            ("천만", 10_000_000),
            ("백만", 1_000_000),
            ("만", 10_000),
        ]

        for unit_str, multiplier in units:
            if unit_str not in remaining:
                continue
            parts = remaining.split(unit_str, 1)
            num_part = parts[0].strip()
            remaining = parts[1] if len(parts) > 1 else ""

            coeff = self._parse_coeff(num_part)
            total += coeff * multiplier

        # 잔여 숫자 (예: "5억200" 같은 경우)
        if remaining:
            m = re.search(r"[\d.]+", remaining)
            if m:
                total += float(m.group())

        if total == 0.0:
            return None

        return -total if negative else total


def extract_financial_tables(
    dolphin_output: Dict[str, Any]
) -> Dict[str, Any]:
    """재무제표 추출 편의 함수"""
    extractor = FinancialTableExtractor()
    return extractor.extract_financial_tables(dolphin_output)
