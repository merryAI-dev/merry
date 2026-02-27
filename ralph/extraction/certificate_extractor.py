"""
인증서 추출기 (중소기업확인서, 벤처기업확인서, 기업부설연구소 등).

각 페이지 텍스트에서 인증서 종류별 KV 패턴 매칭.
API 호출 없이 모든 필드 추출.
"""
from __future__ import annotations

import re

from ralph.layout.models import LayoutResult
from .base import BaseExtractor


# 인증서 타입 감지 패턴
_CERT_PATTERNS: list[tuple[str, str]] = [
    ("중소기업확인서", r"중소기업\s*확인서"),
    ("벤처기업확인서", r"벤처기업\s*확인서"),
    ("기업부설연구소", r"기업부설연구소"),
    ("이노비즈확인서", r"이노비즈\s*확인"),
    ("메인비즈확인서", r"메인비즈\s*확인"),
    ("KC인증", r"KC\s*인증|전파인증|적합등록\s*필증"),
]


class CertificateExtractor(BaseExtractor):
    """인증서 추출기 — 0 API 호출."""

    @property
    def doc_type(self) -> str:
        return "certificate"

    def extract(self, layout: LayoutResult) -> tuple[dict, float]:
        result: dict = {
            "corp_name": None,
            "certificates": [],
        }

        # 페이지별로 인증서 감지
        for page in layout.pages:
            text = page.full_text
            if not text.strip():
                continue

            for cert_type, pattern in _CERT_PATTERNS:
                if re.search(pattern, text):
                    cert = self._extract_cert(cert_type, text)
                    if cert:
                        result["certificates"].append(cert)
                        # 첫 번째 인증서에서 corp_name
                        if not result["corp_name"] and cert.get("corp_name"):
                            result["corp_name"] = cert["corp_name"]

        confidence = self._compute_confidence(result)
        return result, confidence

    def _extract_cert(self, cert_type: str, text: str) -> dict:
        cert: dict = {
            "cert_type": cert_type,
            "corp_name": None,
            "issue_number": None,
            "valid_from": None,
            "valid_to": None,
        }

        # 기업명
        m = re.search(r"기\s*업\s*명\s*[:：]?\s*(.+?)(?:\n|$)", text)
        if m:
            cert["corp_name"] = m.group(1).strip()
        else:
            # "소속기업명:" 패턴
            m = re.search(r"소속기업명\s*[:：]?\s*(.+?)(?:\n|\]|$)", text)
            if m:
                cert["corp_name"] = m.group(1).strip()

        # 발급번호
        m = re.search(r"발급번호\s*[:：]?\s*(\S+)", text)
        if m:
            cert["issue_number"] = m.group(1).strip()
        else:
            m = re.search(r"제\s*(\S+)\s*호", text)
            if m:
                cert["issue_number"] = m.group(1).strip()

        # 줄바꿈 제거 버전으로 유효기간 탐색
        text_flat = text.replace("\n", " ")

        # 유효기간: "2024-04-01 ~ 2025-03-31" 패턴
        m = re.search(
            r"유효기간\s*[:：]?\s*(\d{4}[-./]\d{2}[-./]\d{2})\s*~\s*(\d{4}[-./]\d{2}[-./]\d{2})",
            text_flat,
        )
        if m:
            cert["valid_from"] = m.group(1)
            cert["valid_to"] = m.group(2)
        else:
            # "YYYY년MM월DD일~ YYYY년MM월DD일" 한국어 패턴
            m = re.search(
                r"유효기간\s*[:：]?\s*(\d{4})년\s*(\d{2})월\s*(\d{2})일\s*~\s*(\d{4})년\s*(\d{2})월\s*(\d{2})일",
                text_flat,
            )
            if m:
                cert["valid_from"] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                cert["valid_to"] = f"{m.group(4)}-{m.group(5)}-{m.group(6)}"
            else:
                # 단일 날짜 유효기간: "유효기간: YYYY년 M월 DD일"
                m = re.search(
                    r"유효기간\s*[:：]?\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일",
                    text_flat,
                )
                if m:
                    cert["valid_to"] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

        return cert

    def _compute_confidence(self, result: dict) -> float:
        score = 0.0
        total = 3.0

        if result["corp_name"]:
            score += 1.0
        if result["certificates"]:
            score += 1.0
        if len(result["certificates"]) >= 2:
            score += 1.0

        return min(score / total, 1.0)
