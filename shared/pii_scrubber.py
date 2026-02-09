"""
PII (Personally Identifiable Information) scrubbing utilities.

Removes or masks sensitive personal information from training data
to ensure privacy and compliance.
"""

import re
from typing import Any, Dict, List, Set

from .logging_config import get_logger

logger = get_logger("pii_scrubber")

# PII patterns to detect and mask
PII_PATTERNS = {
    # Korean phone numbers: 010-1234-5678, 02-123-4567, etc.
    "phone": re.compile(
        r"\b0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}\b"
    ),
    # Email addresses
    "email": re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    ),
    # Korean resident registration numbers: 123456-1234567
    "resident_id": re.compile(
        r"\b\d{6}[-\s]?[1-4]\d{6}\b"
    ),
    # Business registration numbers: 123-45-67890
    "business_id": re.compile(
        r"\b\d{3}[-\s]?\d{2}[-\s]?\d{5}\b"
    ),
    # Corporate registration numbers: 110111-1234567
    "corp_id": re.compile(
        r"\b\d{6}[-\s]?\d{7}\b"
    ),
    # Credit card numbers: 1234-5678-9012-3456
    "credit_card": re.compile(
        r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"
    ),
    # Korean addresses (heuristic: 시/구/동 + 번지)
    "address": re.compile(
        r"[가-힣]+[시도]\s+[가-힣]+[구군]\s+[가-힣]+[동읍면리로길]\s+\d+"
    ),
    # Bank account numbers: 123-456-789012
    "bank_account": re.compile(
        r"\b\d{2,4}[-\s]?\d{2,6}[-\s]?\d{2,8}\b"
    ),
}

# Fields that commonly contain PII (case-insensitive)
PII_FIELD_NAMES: Set[str] = {
    "email",
    "phone",
    "tel",
    "mobile",
    "resident_id",
    "주민번호",
    "주민등록번호",
    "business_registration_number",
    "사업자등록번호",
    "corporate_registration_number",
    "법인등록번호",
    "representative_name",
    "대표자",
    "대표이사",
    "name",
    "이름",
    "성명",
    "address",
    "주소",
    "소재지",
    "hq_address",
    "branch_address",
    "bank_account",
    "계좌번호",
    "credit_card",
    "카드번호",
}


def mask_text(text: str, mask_char: str = "*") -> str:
    """Mask PII in text using pattern matching.

    Args:
        text: Input text
        mask_char: Character to use for masking

    Returns:
        Masked text
    """
    if not text or not isinstance(text, str):
        return text

    masked = text
    for pii_type, pattern in PII_PATTERNS.items():
        matches = pattern.findall(masked)
        for match in matches:
            # Keep first 3 chars for context, mask the rest
            if len(match) > 3:
                replacement = match[:3] + mask_char * (len(match) - 3)
            else:
                replacement = mask_char * len(match)
            masked = masked.replace(match, replacement)

    return masked


def is_pii_field(field_name: str) -> bool:
    """Check if a field name likely contains PII.

    Args:
        field_name: Field/key name

    Returns:
        True if field is likely PII
    """
    if not field_name:
        return False
    field_lower = field_name.lower().strip()
    return any(pii_name in field_lower for pii_name in PII_FIELD_NAMES)


def scrub_dict(data: Dict[str, Any], redact_values: bool = True) -> Dict[str, Any]:
    """Scrub PII from dictionary data.

    Args:
        data: Input dictionary
        redact_values: If True, mask values. If False, remove keys entirely.

    Returns:
        Scrubbed dictionary
    """
    if not isinstance(data, dict):
        return data

    scrubbed = {}
    for key, value in data.items():
        # Check if key name indicates PII
        if is_pii_field(key):
            if redact_values:
                if isinstance(value, str):
                    scrubbed[key] = "[REDACTED_PII]"
                elif isinstance(value, (int, float)):
                    scrubbed[key] = 0
                else:
                    scrubbed[key] = None
            # else: skip this key (remove entirely)
            continue

        # Recursively scrub nested structures
        if isinstance(value, dict):
            scrubbed[key] = scrub_dict(value, redact_values)
        elif isinstance(value, list):
            scrubbed[key] = [
                scrub_dict(item, redact_values) if isinstance(item, dict) else mask_text(str(item)) if isinstance(item, str) else item
                for item in value
            ]
        elif isinstance(value, str):
            # Mask text patterns in string values
            scrubbed[key] = mask_text(value)
        else:
            scrubbed[key] = value

    return scrubbed


def scrub_training_sample(sample: Dict[str, Any]) -> Dict[str, Any]:
    """Scrub PII from a training sample.

    Training samples typically have 'input' and 'output' fields.
    We mask PII but keep structure intact for training.

    Args:
        sample: Training sample

    Returns:
        Scrubbed sample
    """
    scrubbed = {}

    for key, value in sample.items():
        if key in ("input", "output", "parsed_output", "raw_output"):
            # Scrub but keep structure
            if isinstance(value, dict):
                scrubbed[key] = scrub_dict(value, redact_values=True)
            elif isinstance(value, str):
                scrubbed[key] = mask_text(value)
            else:
                scrubbed[key] = value
        elif key == "metadata":
            # Keep metadata but scrub any PII fields
            if isinstance(value, dict):
                scrubbed[key] = scrub_dict(value, redact_values=True)
            else:
                scrubbed[key] = value
        else:
            # Other fields: pass through
            scrubbed[key] = value

    return scrubbed


def validate_no_pii(data: Any, path: str = "root") -> List[str]:
    """Validate that data contains no obvious PII.

    Args:
        data: Data to validate
        path: Current path in data structure (for error reporting)

    Returns:
        List of warnings (empty if no PII detected)
    """
    warnings = []

    if isinstance(data, dict):
        for key, value in data.items():
            # Check field name
            if is_pii_field(key):
                warnings.append(f"{path}.{key}: Field name indicates PII")

            # Check value
            if isinstance(value, str):
                for pii_type, pattern in PII_PATTERNS.items():
                    if pattern.search(value):
                        warnings.append(
                            f"{path}.{key}: Detected {pii_type} pattern in value"
                        )

            # Recurse
            warnings.extend(validate_no_pii(value, f"{path}.{key}"))

    elif isinstance(data, list):
        for idx, item in enumerate(data):
            warnings.extend(validate_no_pii(item, f"{path}[{idx}]"))

    elif isinstance(data, str):
        for pii_type, pattern in PII_PATTERNS.items():
            if pattern.search(data):
                warnings.append(f"{path}: Detected {pii_type} pattern")

    return warnings


# Example usage and tests
if __name__ == "__main__":
    # Test masking
    test_text = "연락처: 010-1234-5678, 이메일: user@example.com, 주민번호: 123456-1234567"
    print("Original:", test_text)
    print("Masked:", mask_text(test_text))
    print()

    # Test dict scrubbing
    test_dict = {
        "company_name": "테스트 회사",
        "representative_name": "홍길동",
        "phone": "010-1234-5678",
        "email": "test@example.com",
        "revenue": 1000000000,
        "address": "서울시 강남구 테헤란로 123",
    }
    print("Original dict:")
    print(test_dict)
    print("\nScrubbed dict:")
    print(scrub_dict(test_dict))
    print()

    # Test validation
    warnings = validate_no_pii(test_dict)
    print("Validation warnings:")
    for w in warnings:
        print(f"  - {w}")
