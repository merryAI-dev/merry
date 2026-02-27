"""
투자검토자료 추출기.

워드 형식 PDF를 페이지 순회하며 섹션별 XML 구조로 추출.
텍스트 순차 추출 + 테이블 구조 추출 + 이미지 위치 감지.
API 호출 없이 모든 텍스트/테이블 필드 추출.
"""
from __future__ import annotations

import re
from typing import Any

import fitz

from ralph.layout.models import LayoutResult, TableInfo
from .base import BaseExtractor


# 로마숫자 섹션 제목 패턴
_SECTION_PAT = re.compile(
    r"^(I{1,3}V?|VI{0,3}|IX|X{1,3})\.\s+(.+)$"
)

# 소제목 패턴 (❍, 1., 2. 등)
_SUBSECTION_PAT = re.compile(r"^(\d+)\.\s+(.+)$")
_BULLET_PAT = re.compile(r"^[❍●⚫•◆▶]\s*(.+)$")


class InvestmentReviewExtractor(BaseExtractor):
    """투자검토자료 추출기 — 0 API 호출."""

    @property
    def doc_type(self) -> str:
        return "investment_review"

    def extract(self, layout: LayoutResult) -> tuple[dict, float]:
        result: dict = {
            "corp_name": None,
            "representative": None,
            "product_name": None,
            "address": None,
            "business_number": None,
            "corp_reg_number": None,
            "founded_date": None,
            "capital": None,
            "employee_count": None,
            "homepage": None,
            "sections": [],
            "cap_table": [],
            "capital_history": [],
            "historical_financials": {},
            "projected_financials": {},
            "image_count": 0,
        }

        pdf_path = layout.source_path
        doc = fitz.open(pdf_path)
        try:
            # 이미지 카운트
            total_images = 0
            for page in doc:
                total_images += len(page.get_images())
            result["image_count"] = total_images

            # 1) 표지 + 기업개요 KV 추출
            self._extract_cover(doc, result)
            self._extract_company_overview(doc, result)

            # 2) 전체 페이지 순회 → 섹션별 XML 구조
            sections = self._build_sections(doc)
            result["sections"] = sections

            # 3) 핵심 테이블 별도 추출
            self._extract_cap_table(doc, result)
            self._extract_financials(doc, result)
            self._extract_projections(doc, result)
        finally:
            doc.close()

        confidence = self._compute_confidence(result)
        return result, confidence

    # ── 표지 추출 ──

    def _extract_cover(self, doc: fitz.Document, result: dict) -> None:
        """표지(p0) 테이블에서 기본 정보."""
        if doc.page_count < 1:
            return
        tables = doc[0].find_tables()
        for tb in tables.tables:
            rows = tb.extract()
            for row in rows:
                cells = [str(c or "").strip() for c in row]
                joined = " ".join(cells)
                nospace = joined.replace(" ", "")

                if "회사명" in nospace and not result["corp_name"]:
                    for c in cells[1:]:
                        if c and "회사명" not in c.replace(" ", ""):
                            result["corp_name"] = c
                            break
                if "대표자" in nospace and not result["representative"]:
                    for c in cells[1:]:
                        if c and "대표" not in c.replace(" ", ""):
                            result["representative"] = c
                            break
                if "제품명" in nospace and not result["product_name"]:
                    for c in cells[1:]:
                        if c and "제품" not in c.replace(" ", ""):
                            result["product_name"] = c
                            break
                if "소재지" in nospace and not result["address"]:
                    for c in cells[1:]:
                        if c and "소재지" not in c.replace(" ", ""):
                            result["address"] = c
                            break

    def _extract_company_overview(self, doc: fitz.Document, result: dict) -> None:
        """기업개요 테이블(p1)에서 상세 정보."""
        if doc.page_count < 2:
            return

        # 라벨 셋 (값이 아닌 것들)
        _LABELS = {
            "회사명", "설립일자", "사업자등록번호", "법인등록번호",
            "자본금", "액면가", "직원수", "고용인원", "홈페이지",
            "주요제품/서비스", "주요업태", "주요업종", "표준산업분류",
            "표준산업분류코드", "결산월", "대표(회사)번호", "본점주소",
            "(지점주소)", "대표자명", "연락처,", "E-mail)", "기타기업인증",
            "기타회사정보", "기술개발참여실적", "벤처(인증)기업여부",
            "지정일/종료일,", "벤처확인번호",
        }

        kv_map = {
            "설립일자": "founded_date",
            "사업자등록번호": "business_number",
            "법인등록번호": "corp_reg_number",
            "자본금": "capital",
            "직원수": "employee_count",
            "고용인원": "employee_count",
            "홈페이지": "homepage",
        }

        tables = doc[1].find_tables()
        for tb in tables.tables:
            rows = tb.extract()
            for row in rows:
                cells = [str(c or "").strip() for c in row]

                for ci, cell in enumerate(cells):
                    cell_nospace = cell.replace(" ", "")
                    for label, field in kv_map.items():
                        if label in cell_nospace and not result.get(field):
                            # 라벨 이후 셀에서 첫 번째 유효값
                            for j in range(ci + 1, len(cells)):
                                val = cells[j]
                                val_nospace = val.replace(" ", "")
                                if val_nospace and val_nospace not in _LABELS:
                                    result[field] = val
                                    break

    # ── 섹션 빌드 ──

    def _build_sections(self, doc: fitz.Document) -> list[dict]:
        """전체 페이지를 순회하며 섹션 기반 XML 구조 생성."""
        sections: list[dict] = []
        current_section: dict | None = None

        for page_idx in range(doc.page_count):
            page = doc[page_idx]
            text = page.get_text()
            page_tables = page.find_tables()
            page_images = page.get_images()

            lines = text.split("\n")
            for line in lines:
                line_stripped = line.strip()
                if not line_stripped:
                    continue

                # Confidential + 페이지 번호 스킵
                if line_stripped.startswith("Confidential") or line_stripped.isdigit():
                    continue

                # 섹션 제목 감지
                m = _SECTION_PAT.match(line_stripped)
                if m:
                    if current_section:
                        sections.append(current_section)
                    current_section = {
                        "number": m.group(1),
                        "title": m.group(2).strip(),
                        "start_page": page_idx,
                        "content": [],
                    }
                    continue

                # 현재 섹션이 없으면 "표지" 섹션
                if current_section is None:
                    current_section = {
                        "number": "0",
                        "title": "표지",
                        "start_page": 0,
                        "content": [],
                    }

                # 텍스트 추가
                current_section["content"].append({
                    "type": "text",
                    "page": page_idx,
                    "value": line_stripped,
                })

            # 테이블 추가
            if current_section is not None:
                for tb in page_tables.tables:
                    rows = tb.extract()
                    # None 정리
                    clean_rows = []
                    for row in rows:
                        clean_row = [str(c).strip() if c else "" for c in row]
                        if any(c for c in clean_row):
                            clean_rows.append(clean_row)
                    if clean_rows:
                        current_section["content"].append({
                            "type": "table",
                            "page": page_idx,
                            "rows": clean_rows,
                        })

            # 이미지 메타
            if current_section is not None and page_images:
                for img in page_images:
                    current_section["content"].append({
                        "type": "image",
                        "page": page_idx,
                        "xref": img[0],
                        "width": img[2],
                        "height": img[3],
                    })

        if current_section:
            sections.append(current_section)

        return sections

    # ── 핵심 테이블 추출 ──

    def _extract_cap_table(self, doc: fitz.Document, result: dict) -> None:
        """주주현황 테이블 추출 (보통 p11 부근)."""
        for page_idx in range(doc.page_count):
            text = doc[page_idx].get_text()
            if "주주현황" not in text.replace(" ", "") and "주주명" not in text:
                continue

            tables = doc[page_idx].find_tables()
            for tb in tables.tables:
                rows = tb.extract()
                if len(rows) < 3:
                    continue

                # 헤더에 "주주명" + "지분율" 있는지
                header_text = " ".join(
                    str(c or "") for row in rows[:2] for c in row
                ).replace(" ", "")
                if "주주명" not in header_text:
                    continue

                # 데이터 행 파싱
                shareholders = []
                for ri in range(2, len(rows)):
                    cells = [str(c or "").strip() for c in rows[ri]]
                    # 첫 번째 non-empty 셀이 이름
                    name = ""
                    for c in cells:
                        if c and not c.replace(",", "").replace("%", "").replace(".", "").isdigit():
                            name = c
                            break
                    if not name or name in ("합계", "합 계", "소계"):
                        continue

                    # 숫자가 전혀 없는 행 = 이전 주주의 이름 연속행
                    has_numbers = any(
                        c.replace(",", "").replace("-", "").replace(".", "").replace("%", "").replace("주", "").strip().isdigit()
                        for c in cells if c
                    )
                    if not has_numbers and shareholders:
                        # 이전 주주 이름에 병합
                        shareholders[-1]["name"] += " " + name
                        continue

                    # 숫자 셀들에서 주식수/지분율 추출
                    sh: dict[str, Any] = {"name": name}

                    # 주식수 — 쉼표 포함 정수
                    for c in cells:
                        c_clean = c.replace(",", "").replace("주", "").strip()
                        if c_clean.isdigit() and int(c_clean) > 100:
                            sh["shares_before"] = int(c_clean)
                            break

                    # 지분율 — % 포함 셀
                    for c in cells:
                        if "%" in c:
                            try:
                                sh["ratio_before"] = float(c.replace("%", "").strip())
                                break
                            except ValueError:
                                pass

                    # 주식종류
                    for c in cells:
                        if "보통주" in c or "우선주" in c or "RCPS" in c:
                            sh["share_type"] = c
                            break

                    shareholders.append(sh)

                if shareholders:
                    result["cap_table"] = shareholders
                    break
            if result["cap_table"]:
                break

        # 증자이력
        for page_idx in range(doc.page_count):
            text = doc[page_idx].get_text()
            if "증자" not in text and "자금변동" not in text.replace(" ", ""):
                continue

            tables = doc[page_idx].find_tables()
            for tb in tables.tables:
                rows = tb.extract()
                header_text = " ".join(
                    str(c or "") for row in rows[:3] for c in row
                ).replace(" ", "")
                if "변동사항" not in header_text and "증자" not in header_text:
                    continue

                history = []
                for ri in range(2, len(rows)):
                    cells = [str(c or "").strip() for c in rows[ri]]
                    joined = " ".join(cells)
                    # 날짜 감지
                    date_match = re.search(r"(\d{4}\.\d{2})", joined)
                    if date_match:
                        entry: dict[str, Any] = {"date": date_match.group(1)}
                        if "유상" in joined:
                            entry["type"] = "유상증자"
                        if "보통주" in joined:
                            entry["share_type"] = "보통주"
                        elif "우선주" in joined:
                            entry["share_type"] = "우선주"
                        # 금액
                        money_match = re.search(r"([\d,]+)\s*원", joined)
                        if money_match:
                            entry["amount"] = money_match.group(1).replace(",", "")
                        history.append(entry)

                if history:
                    result["capital_history"] = history
                    break
            if result["capital_history"]:
                break

    def _extract_financials(self, doc: fitz.Document, result: dict) -> None:
        """재무현황 테이블(B/S + P/L) 추출."""
        for page_idx in range(doc.page_count):
            text = doc[page_idx].get_text()
            if "재무현황" not in text.replace(" ", ""):
                continue

            tables = doc[page_idx].find_tables()
            for tb in tables.tables:
                rows = tb.extract()
                if len(rows) < 3:
                    continue

                header_text = " ".join(
                    str(c or "") for c in rows[0]
                ).replace(" ", "")

                # 연도 추출
                years = re.findall(r"(\d{4})년", header_text)
                if not years:
                    continue

                # B/S 또는 P/L 판별
                all_text = " ".join(
                    str(c or "") for row in rows for c in row
                ).replace(" ", "")

                is_bs = "자산총계" in all_text or "유동자산" in all_text
                is_pl = "매출액" in all_text or "영업이익" in all_text

                table_type = "balance_sheet" if is_bs else "income_statement" if is_pl else None
                if not table_type:
                    continue

                # 데이터 추출
                data: dict[str, dict[str, int | None]] = {y: {} for y in years}

                for ri in range(1, len(rows)):
                    cells = [str(c or "").strip() for c in rows[ri]]
                    label = cells[0].strip() if cells else ""
                    if not label:
                        # 두 번째 셀에서 라벨
                        for c in cells:
                            if c and not c.replace(",", "").replace("-", "").isdigit():
                                label = c
                                break

                    label_clean = label.replace(" ", "")
                    if not label_clean:
                        continue

                    # 라벨 → 필드명 매핑
                    field = self._map_financial_label(label_clean, table_type)
                    if not field:
                        continue

                    # 연도별 값 추출
                    value_cells = [c for c in cells if c and (
                        c.replace(",", "").replace("-", "").isdigit() or
                        c.startswith("-")
                    )]
                    for yi, year in enumerate(years):
                        if yi < len(value_cells):
                            val = self._parse_number(value_cells[yi])
                            if val is not None:
                                data[year][field] = val

                if any(data[y] for y in years):
                    result["historical_financials"][table_type] = data

    def _extract_projections(self, doc: fitz.Document, result: dict) -> None:
        """손익추정 5개년 테이블 추출."""
        # "손익 추정" 텍스트가 있는 페이지 ~ +2페이지 범위에서 탐색
        target_pages = []
        for page_idx in range(doc.page_count):
            text = doc[page_idx].get_text()
            if "손익추정" in text.replace(" ", "") or "손익 추정" in text:
                for offset in range(3):  # 해당 페이지 + 다음 2페이지
                    pi = page_idx + offset
                    if pi < doc.page_count and pi not in target_pages:
                        target_pages.append(pi)

        for page_idx in target_pages:
            page_text = doc[page_idx].get_text()
            # 페이지 텍스트에서 천원 단위 감지
            page_has_unit = "천 원" in page_text or "천원" in page_text.replace(" ", "")

            tables = doc[page_idx].find_tables()
            for tb in tables.tables:
                rows = tb.extract()
                if len(rows) < 3:
                    continue

                header_text = " ".join(str(c or "") for c in rows[0])

                # "E" 접미사가 있는 연도가 있어야 추정치 (2026E, 2027E)
                has_estimate = bool(re.search(r"\d{4}[Ee]", header_text))
                all_text = " ".join(str(c or "") for row in rows for c in row)
                has_unit = page_has_unit or "천 원" in all_text or "천원" in all_text

                if not has_estimate and not has_unit:
                    continue

                years = re.findall(r"(\d{4})[AaEe]?", header_text)
                if len(years) < 3:
                    continue

                # P/L 항목인지 확인 (매출액, 영업이익 등)
                if "매출액" not in all_text.replace(" ", ""):
                    continue

                data: dict[str, dict[str, int | None]] = {y: {} for y in years}

                for ri in range(1, len(rows)):
                    cells = [str(c or "").strip() for c in rows[ri]]
                    label = ""
                    for c in cells:
                        if c and not c.replace(",", "").replace("-", "").isdigit():
                            label = c.replace(" ", "").replace("\n", "")
                            break
                    if not label:
                        continue

                    field = self._map_financial_label(label, "income_statement")
                    if not field:
                        continue

                    value_cells = [c for c in cells if c and (
                        c.replace(",", "").replace("-", "").isdigit() or
                        c.startswith("-")
                    )]
                    for yi, year in enumerate(years):
                        if yi < len(value_cells):
                            val = self._parse_number(value_cells[yi])
                            if val is not None:
                                # 천원 단위면 ×1000
                                if has_unit:
                                    val *= 1000
                                data[year][field] = val

                if any(data[y] for y in years):
                    result["projected_financials"] = data
                    return

    # ── 유틸리티 ──

    @staticmethod
    def _map_financial_label(label: str, table_type: str) -> str | None:
        """라벨 → 필드명 매핑."""
        mapping: dict[str, str] = {
            # B/S
            "유동자산": "current_assets",
            "비유동자산": "non_current_assets",
            "자산총계": "total_assets",
            "유동부채": "current_liabilities",
            "비유동부채": "non_current_liabilities",
            "부채총계": "total_liabilities",
            "자본총계": "equity",
            # P/L
            "매출액": "revenue",
            "매출원가": "cost_of_revenue",
            "매출총이익": "gross_profit",
            "판관비": "sga",
            "판매비와관리비": "sga",
            "판매관리비": "sga",
            "영업이익": "operating_income",
            "영업손실": "operating_income",
            "당기순이익": "net_income",
            "당기순손실": "net_income",
        }
        return mapping.get(label)

    @staticmethod
    def _parse_number(text: str) -> int | None:
        """숫자 파싱 — 쉼표, 부호 처리."""
        if not text:
            return None
        text = text.replace(",", "").replace(" ", "").strip()
        try:
            return int(text)
        except ValueError:
            try:
                return int(float(text))
            except ValueError:
                return None

    def _compute_confidence(self, result: dict) -> float:
        score = 0.0
        total = 6.0

        if result["corp_name"]:
            score += 1.0
        if result["representative"]:
            score += 1.0
        if result["sections"]:
            score += 1.0
        if result["cap_table"]:
            score += 1.0
        if result["historical_financials"]:
            score += 1.0
        if result["projected_financials"]:
            score += 1.0

        return min(score / total, 1.0)
