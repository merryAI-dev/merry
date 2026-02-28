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
_CHART_IMAGE_AREA_RATIO = 0.30  # 이미지 면적 비율 > 30% → 차트/도표 슬라이드


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
# 경로2: 페이지별 위치 기반 텍스트 추출 + 차트 슬라이드 감지
# ─────────────────────────────────────────────────────────────

def _page_text_sorted(page) -> str:
    """
    get_text("dict")로 텍스트 블록을 y→x 좌표 순으로 정렬.
    슬라이드 읽기 순서(상→하, 좌→우)로 복원.
    """
    blocks = page.get_text("dict")["blocks"]
    items: list[tuple[float, float, str]] = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        y0, x0 = block["bbox"][1], block["bbox"][0]
        lines = [
            "".join(s["text"] for s in line.get("spans", []))
            for line in block.get("lines", [])
        ]
        text = "\n".join(l for l in lines if l.strip())
        if text:
            items.append((y0, x0, text))
    items.sort(key=lambda t: (t[0], t[1]))
    return "\n".join(t[2] for t in items)


def _is_chart_heavy(page, threshold: float = _CHART_IMAGE_AREA_RATIO) -> bool:
    """이미지 면적 비율 > threshold → 차트/도표 중심 슬라이드."""
    rect = page.rect
    page_area = rect.width * rect.height
    if page_area <= 0:
        return False
    image_area = sum(
        (b["bbox"][2] - b["bbox"][0]) * (b["bbox"][3] - b["bbox"][1])
        for b in page.get_text("dict")["blocks"]
        if b.get("type") == 1
    )
    return (image_area / page_area) > threshold


def analyze_pages(pdf_path: str, max_pages: int = 10) -> list[dict]:
    """
    페이지별 분석:
      - text: y→x 위치 기반 정렬된 텍스트
      - is_chart: 차트/도표 중심 여부
    """
    doc = fitz.open(pdf_path)
    try:
        result = []
        for i in range(min(doc.page_count, max_pages)):
            page = doc[i]
            result.append({
                "page": i + 1,
                "text": _page_text_sorted(page),
                "is_chart": _is_chart_heavy(page),
            })
        return result
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

def build_presentation_prompt(pages_info: list[dict]) -> str:
    """
    경로1+2 통합 프롬프트.
    - 텍스트 슬라이드: y→x 위치 기반 정렬 텍스트를 앵커로 제공 (할루시네이션 방지)
    - 차트/도표 슬라이드: 시각 관계 서술 요청 (화살표·박스·계층·흐름)
    """
    sections: list[str] = []
    for p in pages_info:
        pg = p["page"]
        text = p["text"].strip()[:400]  # 슬라이드당 최대 400자
        if p["is_chart"]:
            block = f"[슬라이드 {pg}: 차트/도표 중심]"
            if text:
                block += f"\n추출 키워드: {text}"
            block += "\n→ 이미지에서 화살표·박스·계층·흐름 관계를 서술하세요"
        else:
            block = f"[슬라이드 {pg}]"
            if text:
                block += f"\n{text}"
            else:
                block += "\n(텍스트 없음)"
        sections.append(block)

    pages_block = "\n\n".join(sections)

    return f"""\
슬라이드 이미지들을 보면서 각 슬라이드의 내용을 서술해주세요.

<<< 페이지별 추출 정보 >>>
{pages_block}
<<< 끝 >>>

규칙 (반드시 준수):
1. 각 [슬라이드 N]에 대응하는 이미지를 확인하세요
2. 텍스트 슬라이드: 추출 텍스트를 기반으로 내용을 정리하고 추출 텍스트에 없는 내용은 추가하지 마세요
3. 차트/도표 슬라이드: 이미지에서 보이는 화살표, 박스, 계층, 흐름 관계를 구체적으로 서술하세요
4. 각 슬라이드를 "### 슬라이드 N" 헤더로 구분하세요

아래 JSON 형식으로만 응답하세요:
{{
  "document_type": "발표자료 종류 (예: 정부업무보고, IR자료, 연구발표 등)",
  "readable_text": "슬라이드별 내용 (### 슬라이드 N 헤더로 구분)",
  "structure_notes": "전체 흐름 요약 (예: 제목 → 현황 → 계획 → 결론)"
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

    def _sanitize(s: str) -> str:
        """
        Nova JSON 응답의 두 가지 문제를 수정:
        1. 문자열 값 내 리터럴 제어 문자(개행 등) → \\n 이스케이프로 변환
        2. \\uXXXX 에서 XXXX가 16진수 4자리가 아닌 경우 → \\u 제거
        """
        _CTRL = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}
        out: list[str] = []
        in_str = False
        i = 0
        while i < len(s):
            c = s[i]
            if not in_str:
                out.append(c)
                if c == '"':
                    in_str = True
                i += 1
            else:
                if c == "\\" and i + 1 < len(s):
                    nxt = s[i + 1]
                    if nxt == "u":
                        hex4 = s[i + 2 : i + 6]
                        if len(hex4) == 4 and all(
                            h in "0123456789abcdefABCDEF" for h in hex4
                        ):
                            out.append(s[i : i + 6])
                            i += 6
                        else:
                            i += 2  # 무효한 \u → 제거
                    else:
                        out.append(c)
                        out.append(nxt)
                        i += 2
                elif c == '"':
                    out.append(c)
                    in_str = False
                    i += 1
                elif ord(c) < 32:
                    out.append(_CTRL.get(c, f"\\u{ord(c):04x}"))
                    i += 1
                else:
                    out.append(c)
                    i += 1
        return "".join(out)

    s = _sanitize(raw)

    # 1) 순수 JSON 응답
    try:
        return json.loads(s.strip())
    except json.JSONDecodeError:
        pass
    # 2) 마크다운 코드펜스 안 JSON
    m = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    if m:
        try:
            return json.loads(_sanitize(m.group(1)))
        except json.JSONDecodeError:
            pass
    # 3) 텍스트 내 JSON 블록 추출 (greedy — 가장 큰 {} 블록)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(_sanitize(m.group(0)))
        except json.JSONDecodeError:
            pass
    # 4) 끊긴 응답 처리 (maxTokens 초과로 JSON이 잘린 경우)
    #    마지막 불완전한 \u 이스케이프 제거 후 닫는 문자열 추가
    trimmed = re.sub(r"\\u[0-9a-fA-F]{0,3}$", "", s.rstrip())
    for suffix in ['"}', '"\n}']:
        try:
            return json.loads(trimmed + suffix)
        except json.JSONDecodeError:
            pass
    return {"readable_text": trimmed}


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
            # 슬라이드/발표자료 → Nova 구조화 (경로1+2: 위치 기반 + 차트 감지)
            try:
                page_images = render_pages(pdf_path, max_pages=10, dpi=100)
                pages_info = analyze_pages(pdf_path, max_pages=10)
                prompt = build_presentation_prompt(pages_info)
                visual_description = call_nova_visual(
                    page_images, model_id, region, prompt,
                    max_tokens=5000,
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
