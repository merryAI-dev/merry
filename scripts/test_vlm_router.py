"""
VLM OCR 라우터 통합 테스트.

테스트 목록:
  A. 알려진 문서 13개 — UUID 마스킹, VLM OCR fallback
  B. 미지 문서 — 간이 영수증 PDF (expected: unknown + description)

실행:
    python scripts/test_vlm_router.py
"""
from __future__ import annotations

import logging
import os
import shutil
import sys
import time
import uuid
from pathlib import Path

import fitz

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / "web" / ".env.local", override=False)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("vlm_router_test")

COMPANY_DATA_DIR = Path(os.getenv("BENCHMARK_DATA_DIR", str(PROJECT_ROOT / "companyData")))
TEMP_DIR = PROJECT_ROOT / "temp" / "vlm_router_test"

# 실제 파일명으로 채우세요 (companyData/ 디렉토리에 파일이 있어야 합니다).
# 예시 구조 (파일명과 문서 타입 매핑):
GROUND_TRUTH: dict[str, str] = {
    "1. 투자검토자료.pdf": "investment_review",
    "2. IR자료.pdf": "investment_review",
    "3. 주주명부.pdf": "shareholder",
    "4. 임직원명부.pdf": "employee_list",
    "5. 사업자등록증.pdf": "business_reg",
    "6. 법인등기부등본.pdf": "corp_registry",
    "7. 2022년_재무제표증명.pdf": "financial_stmt",
    "8. 2023년_재무제표증명.pdf": "financial_stmt",
    "9. 2024년_재무제표증명.pdf": "financial_stmt",
    "10. 2025년_재무제표증명.pdf": "financial_stmt",
    "11. 정관사본.pdf": "articles",
    "12. 인증서.pdf": "certificate",
    "13. 창업기업확인서.pdf": "startup_cert",
}


# ------------------------------------------------------------------ #
# 영수증 PDF 생성
# ------------------------------------------------------------------ #

def create_receipt_pdf(path: Path) -> Path:
    """간이 영수증 PDF 생성 (미지 문서 테스트용)."""
    doc = fitz.open()
    page = doc.new_page(width=400, height=600)

    def text(y: int, content: str, size: int = 11):
        page.insert_text((30, y), content, fontsize=size, fontname="helv")

    text(50,  "━━━━━━━━━━━━━━━━━━━━━━", 10)
    text(70,  "영  수  증", 20)
    text(100, "━━━━━━━━━━━━━━━━━━━━━━", 10)
    text(125, "발행일: 2026-02-28")
    text(145, "공급자: (주)카페모카")
    text(165, "사업자번호: 123-45-67890")
    text(185, "주소: 서울시 강남구 테헤란로 123")
    text(215, "─────────────────────", 10)
    text(235, "품목                수량   금액")
    text(255, "─────────────────────", 10)
    text(275, "아메리카노           2    9,000")
    text(295, "카페라떼             1    5,500")
    text(315, "치즈케이크           1    7,000")
    text(335, "─────────────────────", 10)
    text(355, "소계                       21,500")
    text(375, "부가세 (10%)                2,150")
    text(395, "합계                       23,650")
    text(425, "─────────────────────", 10)
    text(445, "결제수단: 신용카드")
    text(465, "카드번호: ****-****-****-1234")
    text(485, "승인번호: 12345678")
    text(515, "이용해 주셔서 감사합니다.")
    text(535, "━━━━━━━━━━━━━━━━━━━━━━", 10)

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    doc.close()
    logger.info(f"영수증 PDF 생성: {path}")
    return path


# ------------------------------------------------------------------ #
# 테스트 A: 알려진 문서 13개 (UUID 마스킹, VLM fallback)
# ------------------------------------------------------------------ #

def test_known_docs() -> list[dict]:
    """UUID 파일명으로 마스킹된 알려진 문서들을 VLM OCR로 분류."""
    from ralph.router import detect_type

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for fname, true_type in GROUND_TRUTH.items():
        src = COMPANY_DATA_DIR / fname
        if not src.exists():
            logger.warning(f"파일 없음: {src}")
            continue

        # UUID 마스킹 복사
        uid = str(uuid.uuid4()) + ".pdf"
        dst = TEMP_DIR / uid
        shutil.copy2(src, dst)

        t0 = time.time()
        result = detect_type(
            file_id=uid,
            filename=uid,           # UUID 파일명 → 1단계 파일명 매칭 실패
            pdf_path=str(dst),
            use_vlm=True,
            use_dino=False,
        )
        elapsed = time.time() - t0

        results.append({
            "filename": fname,
            "true_type": true_type,
            "detected": result.detected_type or "none",
            "method": result.method,
            "confidence": round(result.confidence, 3),
            "description": result.description,
            "correct": result.detected_type == true_type,
            "elapsed": round(elapsed, 2),
        })
        dst.unlink(missing_ok=True)

        status = "✓" if result.detected_type == true_type else "✗"
        logger.info(
            f"{status} {fname[:50]:<50} → {result.detected_type or 'none':>15}"
            f" [{result.method}] ({elapsed:.1f}s)"
        )

    return results


# ------------------------------------------------------------------ #
# 테스트 B: 미지 문서 (영수증)
# ------------------------------------------------------------------ #

def test_unknown_doc() -> dict:
    """미지 문서(영수증)가 들어왔을 때 적절히 unknown + description을 반환하는지 확인."""
    from ralph.router import detect_type

    receipt_path = TEMP_DIR / "test_receipt.pdf"
    create_receipt_pdf(receipt_path)

    t0 = time.time()
    result = detect_type(
        file_id="receipt-001",
        filename=str(uuid.uuid4()) + ".pdf",   # UUID 파일명
        pdf_path=str(receipt_path),
        use_vlm=True,
        use_dino=False,
    )
    elapsed = time.time() - t0

    receipt_path.unlink(missing_ok=True)

    return {
        "filename": "영수증 (간이 테스트)",
        "true_type": "unknown (미지 문서)",
        "detected": result.detected_type or "none",
        "method": result.method,
        "confidence": round(result.confidence, 3),
        "description": result.description,
        "correct": result.detected_type is None,   # None이면 미지 문서로 올바르게 처리
        "elapsed": round(elapsed, 2),
    }


# ------------------------------------------------------------------ #
# 결과 출력
# ------------------------------------------------------------------ #

def print_known_results(results: list[dict]):
    n = len(results)
    correct = sum(1 for r in results if r["correct"])
    vlm_count = sum(1 for r in results if r["method"] == "vlm")
    cls_count = sum(1 for r in results if r["method"] == "classifier")

    print(f"\n{'='*78}")
    print(f"  알려진 문서 VLM OCR 라우팅  ({correct}/{n}, {correct/max(n,1)*100:.1f}%)")
    print(f"  method: classifier={cls_count}건, vlm={vlm_count}건")
    print(f"{'='*78}")
    print(f"{'파일명':<46} {'실제':>15} {'감지':>15} {'방법':>10} {'확률':>6}")
    print(f"{'-'*78}")
    for r in results:
        ok = "✓" if r["correct"] else "✗"
        short = r["filename"][:44]
        print(
            f"{ok} {short:<44} {r['true_type']:>15} {r['detected']:>15}"
            f" {r['method']:>10} {r['confidence']:>6.3f}"
        )
    print(f"{'='*78}")
    avg_t = sum(r["elapsed"] for r in results) / max(n, 1)
    print(f"  평균 처리시간: {avg_t:.1f}s/문서")


def print_unknown_result(r: dict):
    print(f"\n{'='*78}")
    print(f"  미지 문서 테스트 (영수증)")
    print(f"{'='*78}")
    ok = "✓ 올바르게 unknown 처리" if r["correct"] else "✗ 잘못된 분류"
    print(f"  결과:       {ok}")
    print(f"  감지 타입:  {r['detected']}")
    print(f"  method:     {r['method']}")
    print(f"  설명:       {r['description'] or '(없음)'}")
    print(f"  처리시간:   {r['elapsed']}s")
    print(f"{'='*78}")


def print_comparison(known_results: list[dict]):
    """이전 벤치마크와 비교 요약."""
    n = len(known_results)
    correct = sum(1 for r in known_results if r["correct"])
    print(f"\n{'='*50}")
    print(f"  방법별 정확도 최종 비교 (UUID 마스킹 기준)")
    print(f"{'='*50}")
    rows = [
        ("파일명 기반",        "13/13", "100%", "0 API"),
        ("텍스트 Classifier",  "11/13",  "85%", "0 API"),
        ("DINOv2 (LOO)",        "3/13",  "23%", "로컬"),
        ("English CLIP",        "1/13",   "8%", "로컬"),
        ("CLIP 헤더크롭",       "3/13",  "23%", "로컬"),
        (f"VLM OCR (Nova Lite)", f"{correct}/{n}", f"{correct/max(n,1)*100:.0f}%", "Nova Lite"),
    ]
    print(f"  {'방법':<22} {'정확도':>8} {'%':>6} {'비용':>12}")
    print(f"  {'-'*50}")
    for name, acc, pct, cost in rows:
        marker = " ◀" if "VLM" in name else ""
        print(f"  {name:<22} {acc:>8} {pct:>6} {cost:>12}{marker}")
    print(f"{'='*50}")


def main():
    logger.info("=== VLM OCR 라우터 테스트 시작 ===")

    # A. 알려진 문서 13개
    logger.info("\n--- 테스트 A: 알려진 문서 (UUID 마스킹) ---")
    known_results = test_known_docs()
    print_known_results(known_results)

    # B. 미지 문서 (영수증)
    logger.info("\n--- 테스트 B: 미지 문서 (영수증) ---")
    unknown_result = test_unknown_doc()
    print_unknown_result(unknown_result)

    # 종합 비교
    print_comparison(known_results)

    # 정리
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    logger.info("완료")


if __name__ == "__main__":
    main()
