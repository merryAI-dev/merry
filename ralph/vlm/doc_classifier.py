"""
VLM 기반 문서 타입 분류기 — 2단계 전략.

규칙 기반 텍스트 classifier 실패(스캔 이미지 PDF 등) 시 호출.

전략:
  Step 1: VLM이 문서 제목만 읽기 (단순 OCR, 환각 최소화)
  Step 2: Python 키워드 매칭으로 분류 (결정적, VLM 판단 배제)
  Step 3: 키워드 미매칭 → VLM에 "어떤 문서인지 설명만 해줘" (unknown 처리)

VLM에 분류 판단을 맡기지 않아 환각을 억제.
판단 로직은 Python이 담당 → 일관성 보장.
"""
from __future__ import annotations

import json
import logging
import os
import re
import unicodedata

import fitz

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# 알려진 문서 타입 키워드 (classifier.py와 동기화)
# ------------------------------------------------------------------ #

_TYPE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("business_reg",     ["사업자등록증"]),
    ("shareholder",      ["주주명부"]),
    ("financial_stmt",   ["표준재무제표증명", "재무제표증명", "재무제표확인"]),
    ("corp_registry",    ["법인등기부등본", "등기부등본", "등기사항전부증명서", "법인등기"]),
    ("articles",         ["정관"]),
    ("startup_cert",     ["창업기업확인서"]),
    ("employee_list",    ["임직원명부", "임직원 명부", "4대보험가입자", "사업장가입자명부"]),
    ("certificate",      ["중소기업확인서", "벤처기업확인서", "기업부설연구소"]),
    ("investment_review",["투자검토", "투자검토자료", "IR자료", "사업계획서", "투자제안서"]),
]

# Step 1 프롬프트 — 제목만 읽기, 판단 없음
_TITLE_EXTRACT_PROMPT = """이 문서 이미지의 상단에서 문서 종류를 나타내는 제목을 찾아 읽어주세요.

규칙:
- 큰 글씨로 표시된 문서 이름 1개만 읽으세요 (예: "사업자등록증", "주주명부", "영수증")
- 기관명, 회사명, 날짜, 페이지 번호는 포함하지 마세요
- 제목이 없거나 읽을 수 없으면 "알 수 없음"이라고 하세요
- 텍스트가 흐릿하거나 확실하지 않으면 "불명확"이라고 하세요

JSON으로만 응답하세요:
{"title": "사업자등록증"}"""

# Step 3 프롬프트 — 미지 문서 설명 (분류 판단 없음)
_DESCRIBE_PROMPT = """이 문서가 어떤 종류의 문서인지 한 문장으로 설명하세요.
예: "편의점 구매 영수증", "부동산 매매 계약서", "신용카드 명세서"

JSON으로만 응답:
{"description": "설명"}"""


class VLMDocClassifier:
    """
    2단계 VLM 분류기.

    VLM은 '읽기'만, 분류는 Python 키워드 매칭이 담당.
    미지 문서: detected_type=None, description에 문서 설명.
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

    def classify(
        self,
        pdf_path: str,
        confidence_threshold: float = 0.30,
    ) -> tuple[str, float, str | None]:
        """
        문서 타입 분류.

        Returns:
            (doc_type, confidence, description)
            - 알려진 타입: (doc_type, 0.85, None)
            - 미지 문서:   ("unknown", 0.0, "설명 텍스트")
        """
        try:
            img_bytes = self._render_first_page(pdf_path)

            # Step 1: VLM으로 제목만 읽기
            title = self._extract_title(img_bytes)
            logger.info(f"VLM 제목 추출: '{title}'")

            # Step 2: Python 키워드 매칭
            if title and title not in ("알 수 없음", "불명확"):
                matched = self._keyword_match(title)
                if matched:
                    logger.info(f"VLM OCR → {matched} (title='{title}')")
                    return matched, 0.85, None

            # Step 3: 미지 문서 설명
            description = self._describe_doc(img_bytes)
            if not description:
                description = f"문서 제목: {title}" if title else "문서 타입 미확인"
            logger.info(f"VLM → unknown | {description}")
            return "unknown", 0.0, description

        except Exception as e:
            logger.error(f"VLM 분류 실패 ({pdf_path}): {e}", exc_info=True)
            return "unknown", 0.0, f"VLM 오류: {e}"

    # ---------------------------------------------------------------- #
    # 내부 메서드
    # ---------------------------------------------------------------- #

    def _render_first_page(self, pdf_path: str) -> bytes:
        doc = fitz.open(pdf_path)
        try:
            mat = fitz.Matrix(self._dpi / 72, self._dpi / 72)
            return doc[0].get_pixmap(matrix=mat).tobytes("png")
        finally:
            doc.close()

    def _call_nova(self, img_bytes: bytes, prompt: str, max_tokens: int = 100) -> str:
        import boto3
        client = boto3.client("bedrock-runtime", region_name=self._region)
        resp = client.converse(
            modelId=self._model_id,
            messages=[{
                "role": "user",
                "content": [
                    {"image": {"format": "png", "source": {"bytes": img_bytes}}},
                    {"text": prompt},
                ],
            }],
            inferenceConfig={"maxTokens": max_tokens, "temperature": 0},
        )
        return resp["output"]["message"]["content"][0]["text"]

    def _extract_title(self, img_bytes: bytes) -> str:
        """Step 1: VLM으로 문서 제목 텍스트만 추출."""
        raw = self._call_nova(img_bytes, _TITLE_EXTRACT_PROMPT, max_tokens=80)
        parsed = self._parse_json(raw)
        if parsed and "title" in parsed:
            return str(parsed["title"]).strip()
        # JSON 파싱 실패 시 raw 텍스트에서 추출 시도
        return raw.strip()[:50]

    def _keyword_match(self, title: str) -> str | None:
        """Step 2: 제목 텍스트에서 Python 키워드 매칭."""
        title_norm = unicodedata.normalize("NFC", title)
        title_nospace = title_norm.replace(" ", "").replace("\n", "")
        for doc_type, keywords in _TYPE_KEYWORDS:
            for kw in keywords:
                kw_nospace = kw.replace(" ", "")
                if kw in title_norm or kw_nospace in title_nospace:
                    return doc_type
        return None

    def _describe_doc(self, img_bytes: bytes) -> str | None:
        """Step 3: 미지 문서 설명 생성."""
        try:
            raw = self._call_nova(img_bytes, _DESCRIBE_PROMPT, max_tokens=80)
            parsed = self._parse_json(raw)
            if parsed and "description" in parsed:
                return str(parsed["description"]).strip()
            return raw.strip()[:100]
        except Exception as e:
            logger.warning(f"문서 설명 생성 실패: {e}")
            return None

    def _parse_json(self, text: str) -> dict | None:
        for pattern in [
            r"```json\s*(.*?)\s*```",
            r"(\{.*?\})",
        ]:
            m = re.search(pattern, text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError:
                    pass
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            return None


# 싱글톤
_instance: VLMDocClassifier | None = None


def get_vlm_doc_classifier() -> VLMDocClassifier:
    global _instance
    if _instance is None:
        _instance = VLMDocClassifier()
    return _instance
