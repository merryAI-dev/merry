"""
주주명부 전용 추출기.

find_tables()로 추출한 테이블에서 주주 정보를 매핑.
API 호출 없이 모든 필드 추출.
"""
from __future__ import annotations

import re

from ralph.layout.models import LayoutResult, ZoneType, TableInfo
from ralph.utils.korean_text import parse_korean_number, normalize_date
from .base import BaseExtractor


class ShareholderExtractor(BaseExtractor):
    """주주명부 추출기 — 0 API 호출."""

    @property
    def doc_type(self) -> str:
        return "shareholder"

    # 헤더 키워드 → 필드명 매핑
    HEADER_MAP: dict[str, list[str]] = {
        "name": ["주주명", "성명", "주주"],
        "shares": ["주식수", "인수", "보유주식수", "소유주식수"],
        "ratio": ["지분율", "지분비율", "비율", "소유비율"],
        "share_type": ["주식종류", "주식의종류", "종류"],
        "note": ["비고", "기타"],
    }

    # 합계 행 감지 키워드
    TOTAL_ROW_KEYWORDS = ["합계", "합 계", "총계", "Total", "TOTAL", "소계"]

    def extract(self, layout: LayoutResult) -> tuple[dict, float]:
        """주주명부 필드 추출."""
        result: dict = {
            "corp_name": None,
            "shareholders": [],
            "total_shares": 0,
            "base_date": None,
            "capital": None,
        }

        all_tables = layout.all_tables()

        # 1) 주주 테이블 찾기
        sh_table = self._find_shareholder_table(all_tables)
        if sh_table is None:
            return result, 0.0

        # 2) 헤더에서 컬럼 인덱스 매핑
        col_map = self._map_columns(sh_table)

        # 3) 데이터 행 파싱
        shareholders, total_shares, capital = self._parse_rows(sh_table, col_map)
        result["shareholders"] = shareholders
        result["total_shares"] = total_shares
        if capital:
            result["capital"] = capital

        # 4) 메타데이터 추출 (법인명, 기준일)
        self._extract_metadata(layout, result)

        # 신뢰도 계산
        confidence = self._compute_confidence(result)
        return result, confidence

    def _find_shareholder_table(self, tables: list[TableInfo]) -> TableInfo | None:
        """주주 테이블 식별."""
        for table in tables:
            if table.row_count < 2:
                continue
            # 헤더 행 텍스트 확인
            header_text = " ".join(
                str(cell or "") for cell in table.cells[0]
            ).replace(" ", "")

            if any(kw.replace(" ", "") in header_text
                   for kw in ["주주명", "주주", "성명", "주식수"]):
                return table
        return None

    def _map_columns(self, table: TableInfo) -> dict[str, int]:
        """헤더 행에서 컬럼 인덱스 매핑."""
        col_map: dict[str, int] = {}
        if not table.cells:
            return col_map

        header_row = table.cells[0]
        for ci, cell in enumerate(header_row):
            if not cell:
                continue
            cell_text = str(cell).replace(" ", "").replace("\n", "")
            for field, keywords in self.HEADER_MAP.items():
                if field in col_map:
                    continue
                for kw in keywords:
                    if kw in cell_text:
                        col_map[field] = ci
                        break

        return col_map

    def _parse_rows(
        self, table: TableInfo, col_map: dict[str, int]
    ) -> tuple[list[dict], int, int | None]:
        """데이터 행에서 주주 정보 + 합계 추출."""
        shareholders: list[dict] = []
        total_shares = 0
        capital: int | None = None

        name_col = col_map.get("name", 0)
        shares_col = col_map.get("shares", 3)
        ratio_col = col_map.get("ratio", 4)
        share_type_col = col_map.get("share_type")
        note_col = col_map.get("note")

        # 납입금액 컬럼 찾기 (capital 추출용)
        paid_col = self._find_paid_column(table)

        for ri, row in enumerate(table.cells):
            if ri == 0:
                continue  # 헤더 스킵

            # 이름 셀 확인
            name_cell = str(row[name_col] or "").strip() if len(row) > name_col else ""
            if not name_cell:
                continue

            # 합계 행 감지
            name_nospace = name_cell.replace(" ", "")
            if any(kw.replace(" ", "") in name_nospace for kw in self.TOTAL_ROW_KEYWORDS):
                # 합계 행에서 total_shares 추출
                if len(row) > shares_col:
                    shares_text = str(row[shares_col] or "").strip()
                    total_shares = self._parse_shares(shares_text) or 0

                # 합계 행에서 자본금 (납입금액 합계) 추출
                # 셀 병합으로 컬럼 위치가 다를 수 있으므로 유연하게 탐색
                if paid_col is not None:
                    for col_offset in [paid_col, paid_col - 1]:
                        if 0 <= col_offset < len(row):
                            paid_text = str(row[col_offset] or "").strip()
                            cap = self._parse_money(paid_text)
                            if cap is not None and cap > total_shares:
                                capital = cap
                                break

                continue

            # 개별 주주 파싱
            name = name_cell.replace("\n", " ").strip()

            shares = 0
            if len(row) > shares_col:
                shares_text = str(row[shares_col] or "").strip()
                shares = self._parse_shares(shares_text) or 0

            ratio = 0.0
            if len(row) > ratio_col:
                ratio_text = str(row[ratio_col] or "").strip()
                ratio = self._parse_ratio(ratio_text) or 0.0

            share_type = None
            if share_type_col is not None and len(row) > share_type_col:
                st = str(row[share_type_col] or "").strip()
                if st:
                    share_type = st

            note = None
            if note_col is not None and len(row) > note_col:
                n = str(row[note_col] or "").strip()
                if n:
                    note = n

            if shares > 0 or ratio > 0:
                shareholders.append({
                    "name": name,
                    "shares": shares,
                    "ratio": ratio,
                    "share_type": share_type,
                    "note": note,
                })

        # total_shares가 합계 행에 없었으면 개별 합산
        if total_shares == 0 and shareholders:
            total_shares = sum(s["shares"] for s in shareholders)

        return shareholders, total_shares, capital

    def _find_paid_column(self, table: TableInfo) -> int | None:
        """납입금액 컬럼 인덱스 찾기."""
        if not table.cells:
            return None
        header_row = table.cells[0]
        for ci, cell in enumerate(header_row):
            if not cell:
                continue
            text = str(cell).replace(" ", "").replace("\n", "")
            if "납입" in text or "납입금" in text:
                return ci
        return None

    @staticmethod
    def _parse_shares(text: str) -> int | None:
        """주식수 파싱. '50,895주' → 50895."""
        if not text:
            return None
        text = text.replace("주", "").replace(",", "").replace(" ", "").strip()
        try:
            return int(text)
        except ValueError:
            return None

    @staticmethod
    def _parse_ratio(text: str) -> float | None:
        """지분율 파싱. '81%' → 81.0, '5.25%' → 5.25."""
        if not text:
            return None
        text = text.replace("%", "").replace(" ", "").strip()
        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def _parse_money(text: str) -> int | None:
        """금액 파싱. '금 314,930,000원' → 314930000."""
        if not text:
            return None
        text = text.replace("금", "").replace("원", "").replace(",", "").replace(" ", "").strip()
        try:
            return int(text)
        except ValueError:
            return None

    def _extract_metadata(self, layout: LayoutResult, result: dict) -> None:
        """본문 텍스트에서 법인명, 기준일 추출."""
        full_text = layout.full_text

        # 법인명: "주식회사 XXX" 패턴 우선 (후행 노이즈 정리)
        m = re.search(r"주식회사\s+(\S+(?:\s\S+){0,3})", full_text)
        if m:
            corp_name = m.group(1)
            corp_name = re.sub(
                r"\s*(사내이사|대표이사|대표|이사|감사|인감|법인).*$", "", corp_name
            )
            corp_name = corp_name.strip()
            if len(corp_name) >= 2:
                result["corp_name"] = corp_name

        # "(주)XXX" 패턴
        if not result["corp_name"]:
            m = re.search(r"\(주\)\s*(\S+(?:\s\S+){0,3})", full_text)
            if m:
                corp_name = m.group(1)
                corp_name = re.sub(
                    r"\s*(사내이사|대표이사|대표|이사|감사).*$", "", corp_name
                )
                if len(corp_name.strip()) >= 2:
                    result["corp_name"] = corp_name.strip()

        # 기준일: "2025년 11월 19일" 패턴
        m = re.search(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", full_text)
        if m:
            result["base_date"] = normalize_date(m.group(0))

    def _compute_confidence(self, result: dict) -> float:
        """추출 결과 신뢰도 계산."""
        score = 0.0
        total = 6.0

        if result["corp_name"]:
            score += 1.0
        if result["shareholders"]:
            score += 1.0
        if len(result["shareholders"]) >= 2:
            score += 1.0
        if result["total_shares"] > 0:
            score += 1.0
        if result["base_date"]:
            score += 1.0
        # 지분율 합계 검증 (~100%)
        ratio_sum = sum(s["ratio"] for s in result["shareholders"])
        if 95 <= ratio_sum <= 105:
            score += 1.0

        return min(score / total, 1.0)
