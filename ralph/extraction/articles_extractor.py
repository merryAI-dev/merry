"""
정관(Articles of Incorporation) 추출기.

정규식 기반 핵심 조항 추출. API 호출 없이 모든 필드 추출.
VC 실사에 필요한 주요 조항: 발행주식총수, 액면금, 주식종류,
주식매수선택권, 전환사채, 이사/감사 임기 등.
"""
from __future__ import annotations

import re

from ralph.layout.models import LayoutResult
from ralph.utils.korean_text import normalize_date
from .base import BaseExtractor


class ArticlesExtractor(BaseExtractor):
    """정관 추출기 — 0 API 호출."""

    @property
    def doc_type(self) -> str:
        return "articles"

    def extract(self, layout: LayoutResult) -> tuple[dict, float]:
        result: dict = {
            "corp_name": None,
            "corp_name_en": None,
            "established_date": None,
            "latest_revision_date": None,
            "revision_history": None,
            "total_shares_authorized": None,
            "par_value": None,
            "initial_shares": None,
            "headquarters_location": None,
            "business_purposes": None,
            "stock_types": None,
            "has_stock_options": None,
            "has_convertible_bonds": None,
            "director_term_years": None,
            "auditor_term_years": None,
            "chapter_count": None,
            "article_count": None,
            "fiscal_year_end": None,
        }

        text = layout.full_text
        text_oneline = text.replace("\n", " ")

        # --- 회사 상호 ---
        m = re.search(r"상호[】\]]?\s*\n?(이\s*회사의\s*상호는\s*(.+?)(?:이|라)\s*(?:라\s*)?한다)", text)
        if m:
            result["corp_name"] = m.group(2).strip()

        # 영문 상호
        m = re.search(r"영문\s*상호는\s*(.+?)(?:라고|이라)\s*한다", text)
        if m:
            result["corp_name_en"] = m.group(1).strip().rstrip(".")

        # --- 개정 이력 ---
        revisions = re.findall(r"(\d{4}[./]\d{2}[./]\d{2})\.?\s*(제정|개정)", text)
        if revisions:
            history = []
            for date_str, action in revisions:
                normalized = normalize_date(date_str) or date_str
                history.append({"date": normalized, "action": action})
            result["revision_history"] = history

            # 제정일 = 첫 번째 "제정"
            for h in history:
                if h["action"] == "제정":
                    result["established_date"] = h["date"]
                    break

            # 최신 개정일 = 마지막 항목
            result["latest_revision_date"] = history[-1]["date"]

        # --- 발행할 주식 총수 ---
        m = re.search(r"발행할\s*주식의\s*총수는\s*([\d,]+)\s*주", text_oneline)
        if m:
            result["total_shares_authorized"] = int(m.group(1).replace(",", ""))

        # --- 1주 액면금 ---
        m = re.search(r"(?:1주의\s*)?액면금?은?\s*([\d,]+)\s*원", text_oneline)
        if m:
            result["par_value"] = int(m.group(1).replace(",", ""))

        # --- 설립시 발행 주식 ---
        m = re.search(r"설립과\s*동시에\s*발행하는\s*주식의\s*총수는\s*([\d,]+)\s*주", text_oneline)
        if m:
            result["initial_shares"] = int(m.group(1).replace(",", ""))

        # --- 본점 소재지 ---
        m = re.search(r"이\s*회사의\s*본점\s*(?:사업장)?은?\s*(.+?)에\s*(?:설치|둔다)", text_oneline)
        if m:
            result["headquarters_location"] = m.group(1).strip()

        # --- 사업 목적 ---
        m = re.search(r"사업목적[】\]]?\s*\n?(.+?)(?:제\d+조|$)", text, re.DOTALL)
        if m:
            purpose_text = m.group(1)
            # 번호가 매겨진 목록 추출 (1. 또는 숫자.)
            purposes = re.findall(r"\d+\.\s*(.+?)(?:\n|$)", purpose_text)
            if purposes:
                result["business_purposes"] = [p.strip() for p in purposes if p.strip()]

        # --- 주식 종류 ---
        stock_types = []
        if re.search(r"보통주식", text):
            stock_types.append("보통주")
        if re.search(r"우선주식", text):
            stock_types.append("우선주")
        if re.search(r"전환우선주식", text):
            stock_types.append("전환우선주")
        if re.search(r"상환우선주식", text):
            stock_types.append("상환우선주")
        if re.search(r"상환전환우선주식", text):
            stock_types.append("상환전환우선주")
        if stock_types:
            result["stock_types"] = stock_types

        # --- 주식매수선택권 여부 ---
        result["has_stock_options"] = bool(re.search(r"주식매수선택권", text))

        # --- 전환사채 여부 ---
        result["has_convertible_bonds"] = bool(re.search(r"전환사채", text))

        # --- 이사 임기 ---
        m = re.search(r"이사의\s*임기는\s*(?:취임\s*후\s*)?(\d+)\s*년", text_oneline)
        if m:
            result["director_term_years"] = int(m.group(1))

        # --- 감사 임기 ---
        m = re.search(r"감사의\s*임기는\s*(?:취임\s*후\s*)?(\d+)\s*년", text_oneline)
        if m:
            result["auditor_term_years"] = int(m.group(1))

        # --- 장/조 카운트 ---
        chapters = re.findall(r"제(\d+)장", text)
        if chapters:
            result["chapter_count"] = max(int(c) for c in chapters)

        # 정관 자체 조문만 카운트 (【제목】 패턴이 있는 것만)
        own_articles = re.findall(r"제(\d+)조\s*【", text)
        if own_articles:
            result["article_count"] = len(own_articles)
        else:
            # fallback: 제N조 패턴 중 100 이하만 (상법 참조 제외)
            articles = [int(a) for a in re.findall(r"제(\d+)조", text) if int(a) <= 100]
            if articles:
                result["article_count"] = len(set(articles))

        # --- 사업연도 ---
        m = re.search(r"사업연도[】\]]?\s*\n?.+?(\d{1,2})\s*월\s*(\d{1,2})\s*일.+?(\d{1,2})\s*월\s*(\d{1,2})\s*일", text_oneline)
        if m:
            result["fiscal_year_end"] = f"{m.group(3)}월 {m.group(4)}일"
        else:
            # 매년 1월 1일부터 12월 31일까지 패턴
            m = re.search(r"(\d{1,2})월\s*(\d{1,2})일까지", text_oneline)
            if m:
                result["fiscal_year_end"] = f"{m.group(1)}월 {m.group(2)}일"

        confidence = self._compute_confidence(result)
        return result, confidence

    def _compute_confidence(self, result: dict) -> float:
        score = 0.0
        total = 6.0

        if result["corp_name"]:
            score += 1.0
        if result["total_shares_authorized"]:
            score += 1.0
        if result["par_value"]:
            score += 1.0
        if result["revision_history"]:
            score += 1.0
        if result["business_purposes"]:
            score += 1.0
        if result["stock_types"]:
            score += 1.0

        return min(score / total, 1.0)
