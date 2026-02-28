"""
Bedrock Claude 3 Haiku VLM caller.

이미지 PDF를 base64 PNG로 변환 → Claude 3 Haiku (Vision 지원)로 구조화 추출.
향후 Qwen2.5-VL 또는 Bedrock Custom Model로 교체 가능.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re

from .base import BaseVLMCaller, VLMResult

logger = logging.getLogger(__name__)

# 문서 타입별 추출 프롬프트
_EXTRACTION_PROMPTS: dict[str, str] = {
    "business_reg": """이 사업자등록증에서 다음 정보를 JSON으로 추출하세요:
- corp_name: 상호(법인명)
- business_number: 사업자등록번호
- representative: 대표자
- corp_reg_number: 법인등록번호
- address: 사업장 소재지
- business_type: 업태
- business_item: 종목
- opening_date: 개업연월일
- issue_date: 발급일자""",

    "financial_stmt": """이 재무제표에서 다음 정보를 JSON으로 추출하세요:
- corp_name: 회사명
- statement_type: 재무제표 종류
- statements: 연도별 데이터 배열 (각각 year, revenue, operating_income, net_income, total_assets, total_liabilities, equity)
- issue_date: 발급일""",

    "shareholder": """이 주주명부에서 다음 정보를 JSON으로 추출하세요:
- corp_name: 회사명
- base_date: 기준일
- total_shares: 발행주식 총수
- capital: 자본금
- shareholders: 주주 배열 (각각 name, shares, ratio, stock_type, note)""",

    "articles": """이 정관에서 다음 정보를 JSON으로 추출하세요:
- corp_name: 회사 상호
- total_shares_authorized: 발행할 주식 총수
- par_value: 1주 액면금
- headquarters_location: 본점 소재지
- business_purposes: 사업 목적 목록
- stock_types: 주식 종류 목록
- has_stock_options: 주식매수선택권 조항 여부 (true/false)
- has_convertible_bonds: 전환사채 조항 여부 (true/false)
- director_term_years: 이사 임기(년)
- auditor_term_years: 감사 임기(년)""",

    "corp_registry": """이 법인등기부등본에서 다음 정보를 JSON으로 추출하세요:
- corp_name: 상호
- corp_reg_number: 법인등록번호
- address: 본점 소재지
- representative: 대표이사
- directors: 이사/감사 목록 (각각 name, position, appointed_date)
- capital: 자본금
- total_shares: 발행주식 총수
- established_date: 설립일""",

    "investment_review": """이 IR/투자검토 자료의 각 페이지를 분석하세요. 다음 JSON 구조로 반환하세요:
- corp_name: 회사명
- pages: 페이지별 분석 배열. 각 항목:
  - page: 페이지 번호
  - slide_title: 슬라이드 제목 (텍스트)
  - text_content: 페이지의 주요 텍스트 내용 (불릿 포함)
  - visuals: 시각 요소 배열. 각 항목:
    - type: "chart" | "graph" | "diagram" | "photo" | "table" | "logo" | "icon" | "other"
    - description: 이미지/차트/다이어그램이 무엇을 나타내는지 구체적으로 설명 (예: "2021-2024년 매출 성장 막대그래프, 최고값 50억", "서비스 플로우 다이어그램 3단계")
    - key_values: 차트/표에서 읽을 수 있는 핵심 수치나 항목 (없으면 빈 배열)
  - page_summary: 이 페이지가 전달하는 핵심 메시지 1-2문장""",
}

_DEFAULT_PROMPT = """이 문서의 모든 내용을 다음 JSON 구조로 반환하세요:
- pages: 페이지별 분석 배열. 각 항목:
  - page: 페이지 번호
  - text_content: 텍스트 내용
  - visuals: 시각 요소 배열 (각각 type, description, key_values)
  - page_summary: 이 페이지 핵심 내용 요약
- doc_summary: 문서 전체 요약 (회사명, 날짜, 금액 등 핵심 정보 포함)"""


class BedrockClaudeVLMCaller(BaseVLMCaller):
    """Bedrock Claude 3 Haiku (Vision) VLM caller."""

    def __init__(
        self,
        model_id: str | None = None,
        region: str | None = None,
    ):
        self._model_id = (
            model_id
            or os.getenv("RALPH_VLM_MODEL_ID")
            or "global.anthropic.claude-haiku-4-5-20251001-v1:0"
        ).strip()
        self._region = region or os.getenv(
            "AWS_REGION",
            os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2"),
        )

    @property
    def backend_name(self) -> str:
        return "bedrock_claude"

    def extract(
        self,
        pdf_path: str,
        doc_type: str,
        max_pages: int = 5,
    ) -> VLMResult:
        try:
            images_b64 = self._pdf_to_base64(pdf_path, max_pages)
            if not images_b64:
                return VLMResult(
                    success=False,
                    data={},
                    confidence=0.0,
                    model_id=self._model_id,
                    error="PDF에서 이미지를 추출할 수 없습니다",
                )

            prompt = _EXTRACTION_PROMPTS.get(doc_type, _DEFAULT_PROMPT)
            text, usage = self._invoke(images_b64, prompt)
            data = self._parse_json(text)

            if not data:
                return VLMResult(
                    success=False,
                    data={},
                    confidence=0.0,
                    model_id=self._model_id,
                    usage=usage,
                    error="VLM 응답에서 JSON 파싱 실패",
                )

            # confidence 추정: 추출된 필드 수 기반
            non_null = sum(1 for v in data.values() if v is not None)
            confidence = min(non_null / max(len(data), 1), 1.0)

            return VLMResult(
                success=True,
                data=data,
                confidence=confidence,
                model_id=self._model_id,
                usage=usage,
            )

        except Exception as e:
            logger.error(f"VLM 추출 실패: {e}", exc_info=True)
            return VLMResult(
                success=False,
                data={},
                confidence=0.0,
                model_id=self._model_id,
                error=str(e),
            )

    def _pdf_to_base64(self, pdf_path: str, max_pages: int) -> list[str]:
        """PDF → base64 PNG 리스트."""
        import fitz

        images = []
        doc = fitz.open(pdf_path)
        try:
            pages = min(doc.page_count, max_pages)
            zoom = 150 / 72  # 150 DPI
            mat = fitz.Matrix(zoom, zoom)
            for i in range(pages):
                pix = doc[i].get_pixmap(matrix=mat)
                img_bytes = pix.tobytes("png")
                images.append(base64.standard_b64encode(img_bytes).decode("utf-8"))
        finally:
            doc.close()
        return images

    def _invoke(
        self,
        images_b64: list[str],
        prompt: str,
    ) -> tuple[str, dict[str, int]]:
        """Bedrock Anthropic Messages API 호출."""
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "bedrock-runtime",
            region_name=self._region,
            config=Config(
                connect_timeout=30,
                read_timeout=120,
                retries={"max_attempts": 3},
            ),
        )

        # content blocks 구성
        content: list[dict] = []
        for i, img_b64 in enumerate(images_b64):
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_b64,
                },
            })
            content.append({"type": "text", "text": f"[페이지 {i + 1}]"})

        content.append({
            "type": "text",
            "text": f"{prompt}\n\n반드시 JSON만 출력하세요. ```json 블록으로 감싸주세요.",
        })

        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "temperature": 0,
            "system": "당신은 한국 VC 투자 실사에 사용되는 문서에서 구조화된 데이터를 추출하는 전문가입니다. 정확한 JSON만 출력하세요.",
            "messages": [{"role": "user", "content": content}],
        }

        resp = client.invoke_model(
            modelId=self._model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(payload).encode("utf-8"),
        )
        parsed = json.loads(resp["body"].read())

        # 텍스트 추출
        text = ""
        for block in parsed.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                text += block.get("text", "")

        # usage 추출
        usage_raw = parsed.get("usage", {})
        usage = {}
        if isinstance(usage_raw.get("input_tokens"), int):
            usage["input_tokens"] = usage_raw["input_tokens"]
        if isinstance(usage_raw.get("output_tokens"), int):
            usage["output_tokens"] = usage_raw["output_tokens"]

        return text, usage

    def _parse_json(self, text: str) -> dict | None:
        """VLM 응답에서 JSON 추출."""
        # ```json ... ``` 블록 탐색
        m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

        # 전체가 JSON인 경우
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        return None
