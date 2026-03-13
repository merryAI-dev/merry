"""
Stage 2: VLM semantic extraction using Claude Vision.

Takes Stage 1 markdown + page images → structured JSON extraction.
Reuses dolphin_service/processor.py for image conversion and API calls.
"""

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import fitz  # PyMuPDF

from dolphin_service.classifier import DocType
from dolphin_service.strategy import get_strategy

from .stage1 import Stage1Result

logger = logging.getLogger(__name__)


# Document-type specific extraction prompts for RALPH
RALPH_PROMPTS: Dict[str, Dict[str, str]] = {
    "business_reg": {
        "system": """당신은 한국 사업자등록증 전문 파서입니다.

사업자등록증에서 다음 필드를 정확히 추출하여 JSON으로 반환하세요:

**필수 필드**:
- business_number: 사업자등록번호 (XXX-XX-XXXXX 형식, 하이픈 포함)
- corp_name: 상호 (법인명)
- representative: 대표자 성명

**선택 필드**:
- corp_reg_number: 법인등록번호 (XXXXXX-XXXXXXX 형식)
- business_type: 업태
- business_item: 종목
- address: 사업장 소재지
- head_office_address: 본점 소재지
- registration_date: 사업자등록일 (YYYY-MM-DD)
- opening_date: 개업연월일 (YYYY-MM-DD)
- tax_office: 관할 세무서

**주의사항**:
- 찾을 수 없는 필드는 null로 반환
- 날짜는 YYYY-MM-DD 형식으로 표준화
- 사업자등록번호는 반드시 하이픈 포함 (XXX-XX-XXXXX)
- JSON만 반환하세요. 설명 없이.""",
        "user": "다음 사업자등록증을 분석하여 JSON으로 추출하세요.",
    },
    "financial_stmt": {
        "system": """당신은 한국 표준재무제표증명 전문 파서입니다.

재무제표증명에서 연도별 재무 데이터를 추출하여 JSON으로 반환하세요.

**출력 형식**:
```json
{
  "corp_name": "법인명",
  "statement_type": "표준재무제표증명",
  "issuer": "국세청",
  "issue_date": "YYYY-MM-DD",
  "statements": [
    {
      "year": 2024,
      "revenue": 매출액(원),
      "cost_of_revenue": 매출원가(원),
      "gross_profit": 매출총이익(원),
      "operating_income": 영업이익(원),
      "net_income": 당기순이익(원),
      "total_assets": 자산총계(원),
      "total_liabilities": 부채총계(원),
      "equity": 자본총계(원)
    }
  ]
}
```

**주의사항**:
- 금액은 원 단위 정수로 변환 (천원, 백만원 단위 → 원)
- 한국어 숫자 변환 (5억2천만 → 520000000)
- 음수(적자)는 마이너스 부호 유지
- 찾을 수 없는 항목은 null
- JSON만 반환하세요.""",
        "user": "다음 재무제표증명을 분석하여 연도별 재무 데이터를 JSON으로 추출하세요.",
    },
    "shareholder": {
        "system": """당신은 한국 주주명부 전문 파서입니다.

주주명부에서 주주 정보를 추출하여 JSON으로 반환하세요.

**출력 형식**:
```json
{
  "corp_name": "법인명",
  "total_shares": 발행주식총수,
  "base_date": "YYYY-MM-DD",
  "capital": 자본금(원),
  "shareholders": [
    {
      "name": "주주명",
      "shares": 주식수,
      "ratio": 지분율(%),
      "share_type": "보통주|우선주",
      "note": "비고"
    }
  ]
}
```

**주의사항**:
- 지분율은 소수점 2자리까지 (예: 51.23)
- 주식수는 정수
- 주주명부 전체 주주 빠짐없이 추출
- 합계 행은 제외
- JSON만 반환하세요.""",
        "user": "다음 주주명부를 분석하여 주주 정보를 JSON으로 추출하세요.",
    },
}


def _get_anthropic_client():
    """Get Anthropic API client."""
    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic 패키지가 필요합니다: pip install anthropic")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다")

    return anthropic.Anthropic(api_key=api_key)


def _pdf_to_base64_images(pdf_path: str, dpi: int = 150, max_pages: int = 30) -> list[str]:
    """Convert PDF pages to base64 PNG images."""
    doc = fitz.open(pdf_path)
    images = []
    try:
        zoom = dpi / 72
        pages_to_read = min(len(doc), max_pages)
        for i in range(pages_to_read):
            page = doc[i]
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            images.append(base64.standard_b64encode(img_bytes).decode("utf-8"))
    finally:
        doc.close()
    return images


def get_ralph_prompt(doc_type: str) -> Dict[str, str]:
    """Get RALPH prompt for a document type."""
    if doc_type not in RALPH_PROMPTS:
        raise ValueError(f"Unknown doc_type: {doc_type}. Available: {list(RALPH_PROMPTS.keys())}")
    return RALPH_PROMPTS[doc_type]


def _select_model_and_dpi(doc_type: str, classification=None) -> tuple[str, int]:
    """Select model and DPI based on document type."""
    # Map ralph doc_type to dolphin DocType for strategy lookup
    doc_type_map = {
        "business_reg": DocType.SIMPLE_FORM,
        "financial_stmt": DocType.TEXT_WITH_TABLES,
        "shareholder": DocType.SMALL_TABLE,
    }

    dolphin_type = doc_type_map.get(doc_type)
    if dolphin_type and dolphin_type in (DocType.TEXT_WITH_TABLES, DocType.SMALL_TABLE):
        # These types normally use PyMuPDF only, but RALPH Stage 2 needs Vision
        # Use Haiku for cost efficiency on simpler docs
        return "claude-haiku-4-5-20251001", 100

    if dolphin_type:
        strategy = get_strategy(dolphin_type)
        return strategy.model or "claude-haiku-4-5-20251001", strategy.dpi or 100

    # Default: Sonnet for complex docs
    return "claude-sonnet-4-5-20250929", 150


def extract_stage2(
    pdf_path: str,
    stage1: Stage1Result,
    doc_type: str,
    prompt_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Claude Vision으로 시맨틱 추출.

    Args:
        pdf_path: PDF 파일 경로
        stage1: Stage 1 결과 (마크다운)
        doc_type: 문서 타입 (business_reg, financial_stmt, shareholder)
        prompt_override: 리플렉션에서 조정된 프롬프트 (None이면 기본 프롬프트)

    Returns:
        추출된 JSON dict
    """
    client = _get_anthropic_client()

    # Model and DPI selection
    model, dpi = _select_model_and_dpi(doc_type, stage1.classification)

    # Prompt selection
    if prompt_override:
        system_prompt = prompt_override
        user_prompt = RALPH_PROMPTS.get(doc_type, {}).get("user", "JSON으로 추출하세요.")
    else:
        prompts = get_ralph_prompt(doc_type)
        system_prompt = prompts["system"]
        user_prompt = prompts["user"]

    # Convert PDF to images
    images_b64 = _pdf_to_base64_images(pdf_path, dpi=dpi)
    if not images_b64:
        raise ValueError(f"PDF에서 이미지를 추출할 수 없습니다: {pdf_path}")

    # Build message content: per-page context + images + user prompt
    content_blocks: list[dict] = []

    # Per-page context propagation: pair each page's Stage 1 text with its image
    # This gives the VLM both the raw extraction AND the visual for each page
    for i, img_b64 in enumerate(images_b64):
        # Page-level Stage 1 context
        if i < len(stage1.pages):
            page_md = stage1.pages[i].to_markdown()
            if len(page_md) > 2000:
                page_md = page_md[:2000] + "\n... (truncated)"
            content_blocks.append({
                "type": "text",
                "text": f"## Page {i + 1} — Stage 1 텍스트\n{page_md}",
            })

        # Page image
        content_blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": img_b64,
            },
        })

    # User prompt
    content_blocks.append({
        "type": "text",
        "text": user_prompt,
    })

    logger.info(f"Stage2 호출: model={model}, pages={len(images_b64)}, doc_type={doc_type}")

    # API call
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": content_blocks}],
    )

    # Parse JSON from response
    raw_text = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        # Remove first and last line (```json and ```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw_text = "\n".join(lines).strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.warning(f"Stage2 JSON 파싱 실패: {e}")
        logger.debug(f"Raw response: {raw_text[:500]}")
        # Return raw text as error for reflection
        result = {"_parse_error": str(e), "_raw_text": raw_text[:2000]}

    # Add metadata
    result["_model"] = model
    result["_usage"] = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }

    return result
