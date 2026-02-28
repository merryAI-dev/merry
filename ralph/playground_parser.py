"""
PDF 파싱 플레이그라운드 CLI.

사용:
    python ralph/playground_parser.py <pdf_path>

출력: JSON (stdout)
  {
    ok, text, pages, method, text_quality,
    doc_type, confidence, detection_method, description,
    visual_description   # Nova가 사용된 경우에만
  }

품질 게이트:
  PyMuPDF 텍스트 품질 평가 → 충분하면 텍스트 반환, 부족하면 Nova 시각 추출 추가.
  Nova는 품질이 낮은 (스캔 이미지) 문서에만 호출됨.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import unicodedata

import fitz

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# 품질 평가
# ─────────────────────────────────────────────────────────────

# 텍스트가 이 기준 미달이면 스캔 문서로 판단 → Nova 호출
_MIN_CHARS = 80          # 전체 문자 수
_MIN_KOREAN_RATIO = 0.10 # 전체 대비 한글 비율


def assess_text_quality(text: str) -> tuple[float, bool]:
    """
    Returns:
        (quality_score 0–1, is_poor)
    is_poor=True → 스캔/이미지 PDF일 가능성 높음
    """
    stripped = text.strip()
    if not stripped or len(stripped) < _MIN_CHARS:
        return 0.0, True

    korean = sum(
        1 for c in stripped
        if "\uAC00" <= c <= "\uD7A3" or "\u3131" <= c <= "\u318E"
    )
    ratio = korean / len(stripped)
    quality = min(1.0, ratio * 2)  # 50% Korean → score 1.0
    return quality, ratio < _MIN_KOREAN_RATIO


# ─────────────────────────────────────────────────────────────
# PyMuPDF 추출
# ─────────────────────────────────────────────────────────────

def extract_text(pdf_path: str) -> tuple[str, int]:
    """전체 페이지 텍스트 추출. Returns (text, page_count)."""
    doc = fitz.open(pdf_path)
    page_count = doc.page_count
    parts: list[str] = []
    for i in range(page_count):
        t = doc[i].get_text()
        if t.strip():
            parts.append(t)
    doc.close()
    return "\n\n---\n\n".join(parts), page_count


def render_first_page(pdf_path: str, dpi: int = 150) -> bytes:
    doc = fitz.open(pdf_path)
    try:
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        return doc[0].get_pixmap(matrix=mat).tobytes("png")
    finally:
        doc.close()


# ─────────────────────────────────────────────────────────────
# Nova 시각 추출
# ─────────────────────────────────────────────────────────────

_VISUAL_EXTRACT_PROMPT = """\
이 문서 이미지의 내용을 상세히 추출해주세요.

규칙:
- 읽을 수 있는 텍스트를 최대한 정확히 옮겨주세요
- 표나 목록은 구조를 유지해주세요
- 불명확한 부분은 [불명확]으로 표시하세요

JSON으로 응답:
{
  "document_type": "문서 종류 (예: 사업자등록증, 영수증 등)",
  "readable_text": "읽힌 텍스트 전체",
  "structure_notes": "표/레이아웃 설명 (선택)"
}"""


def call_nova_visual(img_bytes: bytes, model_id: str, region: str) -> dict:
    import boto3

    client = boto3.client("bedrock-runtime", region_name=region)
    resp = client.converse(
        modelId=model_id,
        messages=[{
            "role": "user",
            "content": [
                {"image": {"format": "png", "source": {"bytes": img_bytes}}},
                {"text": _VISUAL_EXTRACT_PROMPT},
            ],
        }],
        inferenceConfig={"maxTokens": 800, "temperature": 0},
    )
    raw = resp["output"]["message"]["content"][0]["text"]

    # JSON 파싱 시도
    for pattern in [r"```json\s*(.*?)\s*```", r"(\{.*?\})"]:
        m = re.search(pattern, raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        return {"readable_text": raw.strip()}


# ─────────────────────────────────────────────────────────────
# 문서 분류 (파일명 + 텍스트만, VLM 없음)
# ─────────────────────────────────────────────────────────────

def classify_no_vlm(pdf_path: str, filename: str) -> dict:
    """라우터 1~2단계만 실행 (Nova 없음)."""
    try:
        from ralph.router import detect_type
        r = detect_type(
            file_id="playground",
            filename=filename,
            pdf_path=pdf_path,
            use_vlm=False,
            use_dino=False,
        )
        return {
            "doc_type": r.detected_type,
            "confidence": r.confidence,
            "detection_method": r.method,
            "description": r.description,
        }
    except Exception as e:
        return {"doc_type": None, "confidence": 0.0, "detection_method": "error", "description": str(e)}


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "PDF 경로가 필요합니다"}))
        sys.exit(1)

    pdf_path = sys.argv[1]
    model_id = os.getenv("RALPH_VLM_NOVA_MODEL_ID", "us.amazon.nova-lite-v1:0")
    region = os.getenv("RALPH_VLM_NOVA_REGION", "us-east-1")
    use_vlm = os.getenv("RALPH_USE_VLM", "true").lower() != "false"

    try:
        # ── 1. PyMuPDF 텍스트 추출
        text, pages = extract_text(pdf_path)
        quality, is_poor = assess_text_quality(text)

        # ── 2. 분류 (Nova 없이)
        filename = os.path.basename(pdf_path)
        clf = classify_no_vlm(pdf_path, filename)

        # ── 3. 품질 게이트: 스캔이면 Nova 호출
        method = "pymupdf"
        visual_description: dict | None = None

        if is_poor and use_vlm:
            try:
                img_bytes = render_first_page(pdf_path)
                visual_description = call_nova_visual(img_bytes, model_id, region)
                method = "nova_hybrid"
            except Exception as e:
                visual_description = {"error": str(e)}
                method = "nova_error"

        result = {
            "ok": True,
            "text": text,
            "pages": pages,
            "method": method,
            "text_quality": round(quality, 3),
            "is_poor": is_poor,
            **clf,
            "visual_description": visual_description,
        }

        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    # PYTHONPATH에 프로젝트 루트 추가
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    main()
