"""한국어 텍스트 정규화 유틸리티."""
from __future__ import annotations

import re
import unicodedata


def normalize_text(text: str) -> str:
    """한국어 텍스트 NFC 정규화 + 전각→반각."""
    text = unicodedata.normalize("NFC", text)
    # 전각 문자 → 반각
    text = text.replace("：", ":").replace("，", ",")
    text = text.replace("（", "(").replace("）", ")")
    return text


def normalize_date(text: str) -> str | None:
    """다양한 한국 날짜 형식 → YYYY-MM-DD."""
    text = text.strip()

    # "2024년 01월 28일" 또는 "2024 년01 월28 일"
    m = re.search(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일?", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # "2024.01.28" or "2024-01-28"
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    return None


def normalize_business_number(text: str) -> str | None:
    """사업자등록번호 정규화 → XXX-XX-XXXXX."""
    digits = re.sub(r"\D", "", text)
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
    return None


def normalize_corp_reg_number(text: str) -> str | None:
    """법인등록번호 정규화 → XXXXXX-XXXXXXX."""
    digits = re.sub(r"\D", "", text)
    if len(digits) == 13:
        return f"{digits[:6]}-{digits[6:]}"
    return None


def parse_korean_number(text: str) -> int | None:
    """한국어 숫자 표현 → int. 예: '1,631,784,767' → 1631784767, '(1,234)' → -1234."""
    text = text.strip()
    if not text:
        return None

    # 음수 표현
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    elif text.startswith("-") or text.startswith("△") or text.startswith("▲"):
        negative = True
        text = text[1:]

    # 쉼표, 공백 제거
    text = text.replace(",", "").replace(" ", "").replace("\u3000", "")

    # 단위 처리
    multiplier = 1
    if text.endswith("천원"):
        multiplier = 1000
        text = text[:-2]
    elif text.endswith("백만원"):
        multiplier = 1_000_000
        text = text[:-3]
    elif text.endswith("억원"):
        multiplier = 100_000_000
        text = text[:-2]
    elif text.endswith("원"):
        text = text[:-1]

    try:
        value = int(float(text) * multiplier)
        return -value if negative else value
    except (ValueError, OverflowError):
        return None
