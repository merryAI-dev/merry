"""
Nova Lite hybrid extractor.

역할 분리 전략:
- 텍스트: PyMuPDF (정확, 무료)
- 시각 요소: Nova Lite (차트/사진/다이어그램 묘사만, 텍스트 읽기 금지)

환각 제어 원칙:
1. Nova Lite에게 텍스트 재현 명시적 금지
2. 시각 요소 묘사로만 역할 제한
3. 불확실한 경우 "불명확" 출력 강제
4. temperature=0 고정
"""
from __future__ import annotations

import json
import logging
import os
import re

import fitz  # PyMuPDF

from .base import BaseVLMCaller, VLMResult

logger = logging.getLogger(__name__)

_VISUAL_ONLY_PROMPT = """이 슬라이드에서 시각적 요소만 설명하세요. 텍스트는 별도로 추출하므로 읽지 마세요.

분석 대상:
- 차트/그래프: 종류(막대/선/원형/산점도), 무엇을 비교하는지, 보이는 수치나 레이블
- 사진/일러스트: 무엇이 묘사되어 있는지
- 다이어그램/플로우차트: 구조와 흐름
- 로고/아이콘: 어느 기관/브랜드인지, 슬라이드 내 위치
- 색상 강조: 특별히 강조된 수치나 항목

금지 사항: 슬라이드 텍스트를 그대로 읽거나 재현하지 마세요.
불확실한 요소는 "불명확"이라고만 표기하세요.

다음 JSON으로만 응답하세요:
{
  "visuals": [
    {
      "type": "chart|graph|diagram|photo|logo|icon|other",
      "description": "구체적 설명",
      "key_values": ["차트에서 읽히는 수치나 항목들"]
    }
  ],
  "layout_summary": "슬라이드 레이아웃 구조 한 줄 요약"
}"""


class NovaLiteHybridCaller(BaseVLMCaller):
    """
    PyMuPDF(텍스트) + Nova Lite(시각) 하이브리드 caller.

    Nova Lite는 시각 요소 묘사만 담당 → 환각 범위를 텍스트 재현에서 제거.
    """

    def __init__(
        self,
        model_id: str | None = None,
        region: str | None = None,
        dpi: int = 150,
    ):
        self._model_id = (
            model_id
            or os.getenv("RALPH_VLM_NOVA_MODEL_ID")
            or "us.amazon.nova-lite-v1:0"
        )
        self._region = region or os.getenv("RALPH_VLM_NOVA_REGION", "us-east-1")
        self._dpi = dpi

    @property
    def backend_name(self) -> str:
        return "nova_lite_hybrid"

    def extract(
        self,
        pdf_path: str,
        doc_type: str,
        max_pages: int = 5,
    ) -> VLMResult:
        try:
            import boto3

            client = boto3.client("bedrock-runtime", region_name=self._region)
            doc = fitz.open(pdf_path)
            pages_to_process = min(doc.page_count, max_pages)

            page_results = []
            total_input_tokens = 0
            total_output_tokens = 0

            for i in range(pages_to_process):
                page = doc[i]
                page_result = self._process_page(client, page, i + 1)
                page_results.append(page_result)
                total_input_tokens += page_result.pop("_input_tokens", 0)
                total_output_tokens += page_result.pop("_output_tokens", 0)

            doc.close()

            data = {
                "doc_type": doc_type,
                "pages": page_results,
                "total_pages_processed": pages_to_process,
            }

            # confidence: 시각 요소가 있는 페이지 비율
            pages_with_visuals = sum(
                1 for p in page_results if p.get("visuals")
            )
            confidence = pages_with_visuals / max(pages_to_process, 1)

            return VLMResult(
                success=True,
                data=data,
                confidence=confidence,
                model_id=self._model_id,
                usage={
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                },
            )

        except Exception as e:
            logger.error(f"Nova hybrid 추출 실패: {e}", exc_info=True)
            return VLMResult(
                success=False,
                data={},
                confidence=0.0,
                model_id=self._model_id,
                error=str(e),
            )

    def _process_page(self, client, page, page_num: int) -> dict:
        """단일 페이지: PyMuPDF 텍스트 + Nova Lite 시각 묘사."""
        # 1. 텍스트: PyMuPDF
        text = page.get_text().strip()

        # 2. 이미지: Nova Lite (시각 전용)
        mat = fitz.Matrix(self._dpi / 72, self._dpi / 72)
        img_bytes = page.get_pixmap(matrix=mat).tobytes("png")

        visuals = []
        layout_summary = ""
        input_tokens = 0
        output_tokens = 0

        try:
            resp = client.converse(
                modelId=self._model_id,
                messages=[{
                    "role": "user",
                    "content": [
                        {"image": {"format": "png", "source": {"bytes": img_bytes}}},
                        {"text": _VISUAL_ONLY_PROMPT},
                    ],
                }],
                inferenceConfig={"maxTokens": 600, "temperature": 0},
            )
            raw = resp["output"]["message"]["content"][0]["text"]
            usage = resp.get("usage", {})
            input_tokens = usage.get("inputTokens", 0)
            output_tokens = usage.get("outputTokens", 0)

            parsed = self._parse_json(raw)
            if parsed:
                visuals = parsed.get("visuals", [])
                layout_summary = parsed.get("layout_summary", "")

        except Exception as e:
            logger.warning(f"p{page_num} Nova 시각 추출 실패: {e}")

        return {
            "page": page_num,
            "text": text,
            "visuals": visuals,
            "layout_summary": layout_summary,
            "_input_tokens": input_tokens,
            "_output_tokens": output_tokens,
        }

    def _parse_json(self, text: str) -> dict | None:
        m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        return None
