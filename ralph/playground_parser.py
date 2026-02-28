"""
PDF 파싱 플레이그라운드 CLI.

사용:
    python ralph/playground_parser.py <pdf_path>

출력: JSON (stdout)
  {
    ok, text, pages, method, text_quality, text_structure,
    doc_type, confidence, detection_method, description,
    visual_description   # Nova가 사용된 경우에만
  }

품질 게이트 (3-way):
  1. is_poor      → 스캔/이미지 PDF   → Nova OCR 추출
  2. is_fragmented → 슬라이드/발표자료 → Nova 구조화 추출
  3. else          → 일반 텍스트 PDF  → PyMuPDF 텍스트 반환
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys

import fitz

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# 품질 평가 임계값
# ─────────────────────────────────────────────────────────────

_MIN_CHARS = 80           # 전체 문자 수 미달 → 이미지 PDF
_MIN_KOREAN_RATIO = 0.10  # 한글 비율 미달 → 이미지 PDF
_MAX_AVG_BLOCK_CHARS = 50 # 블록 평균 글자 수 이하 → 슬라이드형
_MIN_BLOCKS_FOR_FRAG = 8  # 슬라이드 판단 최소 블록 수


def assess_text_quality(text: str, blocks: list[str] | None = None) -> tuple[float, bool, bool]:
    """
    Returns:
        (quality_score 0–1, is_poor, is_fragmented)
    - is_poor=True       → 스캔/이미지 PDF (Nova OCR)
    - is_fragmented=True → 슬라이드/발표자료 (Nova 구조화)
    """
    stripped = text.strip()
    if not stripped or len(stripped) < _MIN_CHARS:
        return 0.0, True, False

    korean = sum(
        1 for c in stripped
        if "\uAC00" <= c <= "\uD7A3" or "\u3131" <= c <= "\u318E"
    )
    ratio = korean / len(stripped)
    quality = min(1.0, ratio * 2)
    is_poor = ratio < _MIN_KOREAN_RATIO

    is_fragmented = False
    if not is_poor and blocks and len(blocks) >= _MIN_BLOCKS_FOR_FRAG:
        avg_chars = sum(len(b) for b in blocks) / len(blocks)
        is_fragmented = avg_chars < _MAX_AVG_BLOCK_CHARS

    return quality, is_poor, is_fragmented


# ─────────────────────────────────────────────────────────────
# PyMuPDF 추출
# ─────────────────────────────────────────────────────────────

def extract_text(pdf_path: str) -> tuple[str, int, list[str]]:
    """전체 페이지 텍스트 추출. Returns (text, page_count, text_blocks)."""
    doc = fitz.open(pdf_path)
    page_count = doc.page_count
    parts: list[str] = []
    all_blocks: list[str] = []

    for i in range(page_count):
        page = doc[i]
        t = page.get_text()
        if t.strip():
            parts.append(t)
        # 블록별 텍스트 수집 (파편화 감지용)
        for block in page.get_text("blocks"):
            btext = block[4].strip()
            if btext and block[6] == 0:  # 0 = 텍스트 블록 (이미지 블록 제외)
                all_blocks.append(btext)

    doc.close()
    return "\n\n---\n\n".join(parts), page_count, all_blocks


def render_first_page(pdf_path: str, dpi: int = 150) -> bytes:
    doc = fitz.open(pdf_path)
    try:
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        return doc[0].get_pixmap(matrix=mat).tobytes("png")
    finally:
        doc.close()


def render_pages(pdf_path: str, max_pages: int = 10, dpi: int = 100) -> list[bytes]:
    """여러 페이지를 이미지로 렌더링. 발표자료 전체 처리용."""
    doc = fitz.open(pdf_path)
    try:
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        return [
            doc[i].get_pixmap(matrix=mat).tobytes("png")
            for i in range(min(doc.page_count, max_pages))
        ]
    finally:
        doc.close()


# ─────────────────────────────────────────────────────────────
# Nova 시각 추출 — 프롬프트 분리
# ─────────────────────────────────────────────────────────────

# 스캔/이미지 PDF용: 텍스트 OCR 중심
_PROMPT_OCR = """\
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

def build_presentation_prompt(raw_text: str) -> str:
    """
    Grounded 프롬프트: PyMuPDF 텍스트를 앵커로 제공하여 할루시네이션 방지.
    Nova는 구조·순서만 잡고, 새 내용을 생성하지 않음.
    """
    # PyMuPDF 페이지 구분자(---)를 중립적 태그로 교체해 프롬프트 구조 오염 방지
    snippet = raw_text.replace("\n\n---\n\n", "\n[PAGE]\n").strip()[:2000]
    return f"""\
아래 슬라이드 이미지들을 보면서, 이미 추출된 텍스트 조각들을 올바른 흐름으로 재구성해주세요.

<<< 추출된 텍스트 조각 (순서·구조 무작위) >>>
{snippet}
<<< 끝 >>>

규칙 (반드시 준수):
1. 슬라이드 이미지를 보며 각 슬라이드의 제목과 내용 위치를 파악하세요
2. 위 텍스트 조각들을 슬라이드 순서에 맞게 재조합하세요
3. 위 텍스트에 없는 내용은 절대 추가하지 마세요
4. 차트/도표는 이미지에서 직접 읽히는 키워드만 간단히 기술하세요

아래 JSON 형식으로만 응답하세요:
{{
  "document_type": "발표자료 종류 (예: 정부업무보고, IR자료, 연구발표 등)",
  "readable_text": "텍스트 조각을 슬라이드 순서로 재구성한 전체 내용",
  "structure_notes": "슬라이드 구조 요약 (예: 제목 → 현황 → 계획 → 결론)"
}}"""


def call_nova_visual(
    images: bytes | list[bytes],
    model_id: str,
    region: str,
    prompt: str,
    max_tokens: int = 1200,
) -> dict:
    import boto3

    if isinstance(images, bytes):
        images = [images]

    content: list[dict] = [
        {"image": {"format": "png", "source": {"bytes": img}}}
        for img in images
    ]
    content.append({"text": prompt})

    client = boto3.client("bedrock-runtime", region_name=region)
    resp = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": content}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": 0},
    )
    raw = resp["output"]["message"]["content"][0]["text"]

    # 1) 순수 JSON 응답
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass
    # 2) 마크다운 코드펜스 안 JSON
    m = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # 3) 텍스트 내 JSON 블록 추출 (greedy — 가장 큰 {} 블록)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
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
        # ── 1. PyMuPDF 텍스트 + 블록 추출
        text, pages, blocks = extract_text(pdf_path)
        quality, is_poor, is_fragmented = assess_text_quality(text, blocks)

        # ── 2. 분류 (Nova 없이)
        filename = os.path.basename(pdf_path)
        clf = classify_no_vlm(pdf_path, filename)

        # ── 3. 3-way 품질 게이트
        method = "pymupdf"
        text_structure = "document"
        visual_description: dict | None = None

        if is_poor and use_vlm:
            # 스캔/이미지 PDF → Nova OCR
            try:
                img_bytes = render_first_page(pdf_path)
                visual_description = call_nova_visual(img_bytes, model_id, region, _PROMPT_OCR)
                method = "nova_hybrid"
                text_structure = "image"
            except Exception as e:
                visual_description = {"error": str(e)}
                method = "nova_error"
                text_structure = "image"

        elif is_fragmented and use_vlm:
            # 슬라이드/발표자료 → Nova 구조화 (전체 페이지 + grounded 프롬프트)
            try:
                page_images = render_pages(pdf_path, max_pages=10, dpi=100)
                prompt = build_presentation_prompt(text)
                visual_description = call_nova_visual(
                    page_images, model_id, region, prompt,
                    max_tokens=2000,
                )
                method = "nova_presentation"
                text_structure = "presentation"
            except Exception as e:
                visual_description = {"error": str(e)}
                method = "nova_error"
                text_structure = "presentation"

        elif is_fragmented:
            text_structure = "presentation"

        result = {
            "ok": True,
            "text": text,
            "pages": pages,
            "method": method,
            "text_quality": round(quality, 3),
            "is_poor": is_poor,
            "is_fragmented": is_fragmented,
            "text_structure": text_structure,
            **clf,
            "visual_description": visual_description,
        }

        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    main()
