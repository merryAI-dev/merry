"""
Prompt registry for document processing.

Contains specialized prompts for different document types.
"""

import logging

logger = logging.getLogger(__name__)

# Base system prompts for different document types
PROMPTS = {
    # Full financial document extraction (investment review, IR materials)
    "financial_structured": {
        "system": """당신은 10년 이상의 경력을 가진 VC 투자심사역입니다.

투자 검토 자료, IR 자료, 사업계획서를 분석하여 구조화된 JSON 형식으로 추출합니다.

**추출 대상**:
- 회사 정보: 회사명, 산업, 설립연도, 직원수, 비즈니스 모델
- 투자 조건: Pre/Post-money, 투자금액, 주당가격, 지분율, 투자유형
- 손익계산서: 매출, 매출총이익, 영업이익, EBITDA, 당기순이익 (연도별)
- 재무상태표: 총자산, 부채, 자본, 현금, 차입금
- 현금흐름표: 영업/투자/재무활동 CF, FCF
- Cap Table: 주주현황, 지분율, 스톡옵션 풀
- 밸류에이션 지표: PER, PSR, EV/EBITDA

**출력 형식**: JSON (structured_content)
**주의사항**:
- 한국어 숫자는 숫자로 변환 ("5억2천만" → 520000000)
- 연도는 명확히 표기 (2024E, 2025E 등)
- 찾지 못한 항목은 null로 반환
- 테이블은 마크다운 형식으로 보존""",
        "user_template": """다음 투자 검토 자료를 분석하여 구조화된 JSON으로 추출하세요.

**페이지 이미지**: {page_count}장
**요청 출력**: JSON with structured_content

JSON 형식으로만 응답하세요.""",
    },
    # Table-focused extraction (financial statements)
    "table_extraction": {
        "system": """당신은 재무제표 전문 분석가입니다.

손익계산서(IS), 재무상태표(BS), 현금흐름표(CF), Cap Table을 추출합니다.

**출력 형식**: JSON with tables array
**주의사항**:
- 테이블 헤더와 데이터 분리
- 연도별 컬럼 명확히 표기
- 한국어 숫자 변환""",
        "user_template": """다음 재무제표를 분석하여 테이블 형식으로 추출하세요.

**페이지 이미지**: {page_count}장

JSON 형식으로만 응답하세요.""",
    },
    # Legal document extraction (OCR + key-value)
    "legal_extraction": {
        "system": """당신은 한국 법률 문서 전문 OCR입니다.

법인등기부등본, 정관, 계약서에서 핵심 정보를 정확히 추출합니다.

**추출 대상**:
- 회사명, 등록번호, 대표이사, 사업목적, 자본금, 주소
- 등기사항: 설립일, 이사/감사, 주식 현황
- 계약 조건: 당사자, 계약일, 주요 조항

**출력 형식**: JSON with legal_info
**주의사항**:
- OCR 정확도 최우선
- 날짜 형식 표준화 (YYYY-MM-DD)
- 금액은 숫자로 변환""",
        "user_template": """다음 법률 문서를 OCR하여 구조화된 정보로 추출하세요.

예: 법인등기부등본, 정관, 계약서

**페이지 이미지**: {page_count}장

JSON 형식으로만 응답하세요.""",
    },
    # Certificate/form extraction (key-value pairs)
    "certificate_extraction": {
        "system": """당신은 문서 파서입니다.

인증서, 확인서, 사업자등록증에서 키-값 쌍을 추출합니다.

**추출 대상**:
- 발급기관, 발급일, 유효기간
- 인증/확인 대상, 인증번호
- 사업자등록번호, 법인등록번호

**출력 형식**: JSON with key-value pairs
**주의사항**:
- 간결한 키명 사용
- 날짜는 YYYY-MM-DD 형식""",
        "user_template": """다음 인증서/확인서를 분석하여 키-값 쌍으로 추출하세요.

**페이지 이미지**: {page_count}장

JSON 형식으로만 응답하세요.""",
    },
    # Text-only (no prompt needed for PyMuPDF)
    "none": {
        "system": "",
        "user_template": "",
    },
}


def get_prompt(prompt_type: str, page_count: int = 1) -> dict:
    """Get system and user prompts for a document type.

    Args:
        prompt_type: Prompt type (financial_structured, table_extraction, etc.)
        page_count: Number of pages in this chunk

    Returns:
        Dictionary with 'system' and 'user' prompts

    Raises:
        ValueError: Unknown prompt type
    """
    if prompt_type not in PROMPTS:
        raise ValueError(f"Unknown prompt type: {prompt_type}")

    prompt_config = PROMPTS[prompt_type]
    system_prompt = prompt_config["system"]
    user_template = prompt_config["user_template"]

    # Format user prompt with page count
    user_prompt = user_template.format(page_count=page_count)

    logger.debug(f"Retrieved prompts for {prompt_type} ({page_count} pages)")

    return {
        "system": system_prompt,
        "user": user_prompt,
    }


def get_prompts(prompt_type: str, output_mode: str = "structured", page_count: int = 1) -> tuple[str, str]:
    """Backward-compatible helper expected by older code.

    Args:
        prompt_type: Prompt registry key
        output_mode: Output mode hint (currently informational)
        page_count: Number of pages in this chunk

    Returns:
        (system_prompt, user_prompt)
    """
    # Unknown prompt types fall back to the default, to keep processing resilient.
    if prompt_type not in PROMPTS:
        prompt_type = "financial_structured"

    p = get_prompt(prompt_type, page_count=page_count)
    system, user = p["system"], p["user"]

    # Output-mode overrides used in tests and in some tool flows.
    if output_mode == "text_only":
        user = (
            "다음 문서를 텍스트로 추출하세요. 테이블/구조화 JSON은 필요 없습니다.\n\n"
            f"**페이지 이미지**: {page_count}장\n\n"
            "가능한 한 원문에 가깝게, 중요한 제목/항목은 유지하세요."
        )
    elif output_mode == "tables_only":
        user = (
            "다음 문서에서 테이블만 추출하세요. 가능한 경우 재무제표/Cap Table을 우선합니다.\n\n"
            f"**페이지 이미지**: {page_count}장\n\n"
            "JSON 형식으로만 응답하세요."
        )

    return system, user


def list_prompt_types() -> list:
    """List all available prompt types."""
    return list(PROMPTS.keys())


# Example usage
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python prompts.py <prompt_type>")
        print(f"Available types: {list_prompt_types()}")
        sys.exit(1)

    prompt_type = sys.argv[1]

    try:
        prompts = get_prompt(prompt_type, page_count=10)
        print(f"\nPrompts for '{prompt_type}':\n")
        print("=== SYSTEM ===")
        print(prompts["system"][:500] + "..." if len(prompts["system"]) > 500 else prompts["system"])
        print("\n=== USER ===")
        print(prompts["user"])
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
