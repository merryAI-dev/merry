"""
창업기업확인서 추출기.

KV 패턴 기반 필드 추출. API 호출 없이 모든 필드 추출.
"""
from __future__ import annotations

import re

from ralph.layout.models import LayoutResult
from ralph.utils.korean_text import normalize_date
from .base import BaseExtractor


class StartupCertExtractor(BaseExtractor):
    """창업기업확인서 추출기 — 0 API 호출."""

    @property
    def doc_type(self) -> str:
        return "startup_cert"

    def extract(self, layout: LayoutResult) -> tuple[dict, float]:
        result: dict = {
            "corp_name": None,
            "business_number": None,
            "corp_reg_number": None,
            "representative": None,
            "address": None,
            "startup_date": None,
            "valid_from": None,
            "valid_to": None,
            "issue_number": None,
        }

        text = layout.full_text

        # 발급번호
        m = re.search(r"발급번호\s*[:：]?\s*(제?\s*\S+)", text)
        if m:
            result["issue_number"] = m.group(1).strip()

        # 기업명 — "기업명:" 또는 "기 업 명:"
        m = re.search(r"기\s*업\s*명\s*[:：]?\s*(.+?)(?:\n|$)", text)
        if m:
            result["corp_name"] = m.group(1).strip()

        # 사업자등록번호 (법인등록번호 괄호 포함)
        m = re.search(
            r"사업자\s*\(?법인\)?\s*등록번호\s*[:：]?\s*(\d{3}-\d{2}-\d{5})",
            text,
        )
        if m:
            result["business_number"] = m.group(1)
        else:
            m = re.search(r"(\d{3}-\d{2}-\d{5})", text)
            if m:
                result["business_number"] = m.group(1)

        # 법인등록번호
        m = re.search(r"\((\d{6}-\d{7})\)", text)
        if m:
            result["corp_reg_number"] = m.group(1)

        # 대표자
        m = re.search(r"대\s*표\s*자\s*[:：]?\s*(.+?)(?:\n|$)", text)
        if m:
            result["representative"] = m.group(1).strip()

        # 주소
        m = re.search(r"주\s*소\s*(?:\(본점\))?\s*[:：]?\s*(.+?)(?:\n|$)", text)
        if m:
            result["address"] = m.group(1).strip()

        # 창업일
        m = re.search(r"창\s*업\s*일\s*[:：]?\s*(.+?)(?:\n|$)", text)
        if m:
            date_str = m.group(1).strip()
            result["startup_date"] = normalize_date(date_str) or date_str

        # 유효기간 — 줄바꿈/점 포함 대응
        m = re.search(
            r"유효기간\s*[:：]?\s*(\d{4}[-./]\d{2}[-./]\d{2})\.?\s*~\s*(\d{4}[-./]\d{2}[-./]\d{2})",
            text.replace("\n", " "),
        )
        if m:
            result["valid_from"] = m.group(1).rstrip(".")
            result["valid_to"] = m.group(2).rstrip(".")

        confidence = self._compute_confidence(result)
        return result, confidence

    def _compute_confidence(self, result: dict) -> float:
        score = 0.0
        total = 5.0

        if result["corp_name"]:
            score += 1.0
        if result["business_number"]:
            score += 1.0
        if result["representative"]:
            score += 1.0
        if result["issue_number"]:
            score += 1.0
        if result["valid_from"] or result["startup_date"]:
            score += 1.0

        return min(score / total, 1.0)
