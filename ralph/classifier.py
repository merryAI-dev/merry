"""
문서 타입 자동 분류기.

PDF 첫 1~2페이지 텍스트에서 키워드 매칭으로 문서 타입 판별.
API 호출 없이 0.1초 이내 분류.
"""
from __future__ import annotations

import re

import fitz


# 분류 규칙: (doc_type, keywords, weight)
# 먼저 매칭되는 규칙이 우선. weight가 높은 것부터 정렬.
_CLASSIFICATION_RULES: list[tuple[str, list[str], float]] = [
    # 사업자등록증 — 고유 키워드
    ("business_reg", ["사업자등록증", "사업자 등록증"], 1.0),
    # 주주명부 — 고유 키워드
    ("shareholder", ["주주명부", "주 주 명 부", "주주 명부"], 1.0),
    # 재무제표 (두 포맷 모두)
    ("financial_stmt", ["표준재무제표증명", "재무제표확인", "재무제표 확인"], 1.0),
    # 정관
    ("articles", ["정관", "정 관"], 0.8),
    # 법인등기부등본
    ("corp_registry", ["법인등기부등본", "등기부등본", "등기사항전부증명서"], 0.8),
    # 창업기업확인서
    ("startup_cert", ["창업기업확인서"], 0.8),
    # 임직원명부 / 4대보험 가입자 명부
    ("employee_list", ["임직원명부", "임직원 명부", "4대보험가입자", "사업장가입자명부"], 0.7),
    # 인증서 (중소기업, 벤처기업 등)
    ("certificate", ["중소기업확인서", "벤처기업확인서", "기업부설연구소"], 0.7),
    # 투자검토자료
    ("investment_review", ["투자검토", "투자 검토"], 0.6),
    # IR 자료 (텍스트 적을 수 있음 — 폴백용)
    ("ir_material", ["IR자료", "IR 자료", "사업계획서"], 0.5),
]


def classify_document(pdf_path: str, max_pages: int = 2) -> tuple[str, float]:
    """
    PDF 문서 타입 자동 분류.

    Args:
        pdf_path: PDF 파일 경로
        max_pages: 분류에 사용할 최대 페이지 수

    Returns:
        (doc_type, confidence): 문서 타입과 분류 신뢰도
        분류 불가 시 ("unknown", 0.0)
    """
    doc = fitz.open(pdf_path)
    try:
        pages_to_check = min(doc.page_count, max_pages)
        text = ""
        for i in range(pages_to_check):
            text += doc[i].get_text()

        # 공백 제거 버전도 준비 (자간 확장된 문서 대응)
        text_nospace = text.replace(" ", "").replace("\n", "")
    finally:
        doc.close()

    for doc_type, keywords, weight in _CLASSIFICATION_RULES:
        for kw in keywords:
            kw_nospace = kw.replace(" ", "")
            if kw in text or kw_nospace in text_nospace:
                return doc_type, weight

    return "unknown", 0.0
