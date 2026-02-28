"""
라우터 벤치마크: 파일명 있을 때 vs UUID 마스킹 시 정확도 비교.

실행:
    python scripts/benchmark_router.py

동작:
  1. companyData 13개 PDF에 대해 ground truth 매핑
  2. UUID 마스킹 복사본 생성 (temp/benchmark_masked/)
  3. 세 가지 방법으로 라우팅 결과 비교:
     - 파일명 기반 (filename)
     - 텍스트 classifier (text)
     - DINOv2 시각 분류 (dino, leave-one-out)
  4. 정확도 표 출력
"""
from __future__ import annotations

import logging
import os
import shutil
import sys
import uuid
from pathlib import Path

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / "web" / ".env.local", override=False)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("benchmark")

# ------------------------------------------------------------------ #
# Ground truth
# ------------------------------------------------------------------ #

COMPANY_DATA_DIR = Path(os.getenv("BENCHMARK_DATA_DIR", str(PROJECT_ROOT / "companyData")))
MASKED_DIR = PROJECT_ROOT / "temp" / "benchmark_masked"

# 파일명 → 실제 문서 타입 매핑 (ground truth).
# 실행 전 테스트할 문서 목록과 정답 타입을 채워 넣으세요.
# 예시:
# GROUND_TRUTH: dict[str, str] = {
#     "투자검토자료.pdf": "investment_review",
#     "IR자료.pdf": "investment_review",
#     "주주명부.pdf": "shareholder",
#     "임직원명부.pdf": "employee_list",
#     "사업자등록증.pdf": "business_reg",
#     "법인등기부등본.pdf": "corp_registry",
#     "재무제표증명.pdf": "financial_stmt",
#     "정관.pdf": "articles",
#     "인증서.pdf": "certificate",
#     "창업기업확인서.pdf": "startup_cert",
# }
GROUND_TRUTH: dict[str, str] = {}


def prepare_masked_copies() -> dict[str, tuple[str, str]]:
    """
    UUID 마스킹 복사본 생성.

    Returns:
        {원본파일명: (UUID파일명, UUID파일경로)}
    """
    MASKED_DIR.mkdir(parents=True, exist_ok=True)
    # 기존 파일 정리
    for f in MASKED_DIR.glob("*.pdf"):
        f.unlink()

    mapping: dict[str, tuple[str, str]] = {}
    for fname in GROUND_TRUTH:
        src = COMPANY_DATA_DIR / fname
        if not src.exists():
            logger.warning(f"파일 없음: {src}")
            continue
        uid = str(uuid.uuid4()) + ".pdf"
        dst = MASKED_DIR / uid
        shutil.copy2(src, dst)
        mapping[fname] = (uid, str(dst))
    logger.info(f"UUID 마스킹 복사본 {len(mapping)}개 생성 → {MASKED_DIR}")
    return mapping


# ------------------------------------------------------------------ #
# 방법 1: 파일명 기반 라우팅
# ------------------------------------------------------------------ #

def test_filename_routing() -> list[dict]:
    from ralph.router import detect_type_from_filename

    results = []
    for fname, true_type in GROUND_TRUTH.items():
        src = COMPANY_DATA_DIR / fname
        if not src.exists():
            continue
        detected, conf = detect_type_from_filename(fname)
        results.append({
            "filename": fname,
            "true_type": true_type,
            "detected": detected or "none",
            "confidence": conf,
            "correct": detected == true_type,
            "method": "filename",
        })
    return results


# ------------------------------------------------------------------ #
# 방법 2: UUID 파일명 → 텍스트 classifier
# ------------------------------------------------------------------ #

def test_text_classifier(mapping: dict[str, tuple[str, str]]) -> list[dict]:
    from ralph.classifier import classify_document

    results = []
    for fname, true_type in GROUND_TRUTH.items():
        if fname not in mapping:
            continue
        uuid_name, uuid_path = mapping[fname]
        detected, conf = classify_document(uuid_path)
        results.append({
            "filename": fname,
            "true_type": true_type,
            "detected": detected,
            "confidence": round(conf, 3),
            "correct": detected == true_type,
            "method": "text_classifier",
        })
    return results


# ------------------------------------------------------------------ #
# 방법 3: DINOv2 (leave-one-out)
# ------------------------------------------------------------------ #

def test_dino_loo(mapping: dict[str, tuple[str, str]]) -> list[dict]:
    """Leave-one-out: 각 문서를 제외한 나머지 12개를 레퍼런스로 사용."""
    from ralph.dino_classifier import DinoClassifier, _COMPANY_DATA_LABELS

    clf = DinoClassifier()
    # 모든 레퍼런스 임베딩 미리 계산 (모델 1회 로드)
    logger.info("DINOv2: 레퍼런스 임베딩 계산 중 (13개)…")
    all_refs = []
    from ralph.dino_classifier import DinoRef

    fnames_available = [f for f in GROUND_TRUTH if (COMPANY_DATA_DIR / f).exists()]
    for fname in fnames_available:
        fpath = COMPANY_DATA_DIR / fname
        doc_type = GROUND_TRUTH[fname]
        try:
            emb = clf._embed_pdf(str(fpath))
            all_refs.append(DinoRef(doc_type=doc_type, source_path=str(fpath), embedding=emb))
        except Exception as e:
            logger.error(f"임베딩 실패 {fname}: {e}")

    logger.info(f"DINOv2 레퍼런스 {len(all_refs)}개 완료")

    results = []
    for i, fname in enumerate(fnames_available):
        if fname not in mapping:
            continue
        uuid_name, uuid_path = mapping[fname]

        # 자신 제외한 레퍼런스 (source_path로 매핑)
        src_path = str(COMPANY_DATA_DIR / fname)
        loo_refs = [r for r in all_refs if r.source_path != src_path]

        true_type = GROUND_TRUTH[fname]
        detected, conf = clf.classify_with_refs(uuid_path, loo_refs)
        results.append({
            "filename": fname,
            "true_type": true_type,
            "detected": detected,
            "confidence": round(conf, 3),
            "correct": detected == true_type,
            "method": "dino_loo",
        })

    return results


# ------------------------------------------------------------------ #
# 결과 출력
# ------------------------------------------------------------------ #

def print_table(title: str, results: list[dict]):
    n = len(results)
    correct = sum(1 for r in results if r["correct"])
    print(f"\n{'='*70}")
    print(f"  {title}  ({correct}/{n} 정확, {correct/max(n,1)*100:.1f}%)")
    print(f"{'='*70}")
    print(f"{'파일명':<45} {'실제':>15} {'감지':>15} {'신뢰도':>7} {'결과':>5}")
    print(f"{'-'*70}")
    for r in results:
        short = r["filename"][:43]
        ok = "✓" if r["correct"] else "✗"
        print(f"{short:<45} {r['true_type']:>15} {r['detected']:>15} {r['confidence']:>7.3f} {ok:>5}")
    print(f"{'='*70}")


def print_comparison(fname_results, text_results, dino_results):
    """세 방법 비교 요약 출력."""
    print(f"\n{'='*70}")
    print("  방법별 정확도 비교")
    print(f"{'='*70}")

    fname_map = {r["filename"]: r for r in fname_results}
    text_map = {r["filename"]: r for r in text_results}
    dino_map = {r["filename"]: r for r in dino_results}

    all_files = sorted(set(fname_map) | set(text_map) | set(dino_map))

    print(f"{'파일명':<40} {'실제':>15} {'파일명':>7} {'텍스트':>7} {'DINO':>7}")
    print(f"{'-'*70}")

    fname_ok = text_ok = dino_ok = 0
    for fname in all_files:
        true_t = GROUND_TRUTH.get(fname, "?")
        f = "✓" if fname_map.get(fname, {}).get("correct") else "✗"
        t = "✓" if text_map.get(fname, {}).get("correct") else "✗"
        d = "✓" if dino_map.get(fname, {}).get("correct") else "✗"
        fname_ok += f == "✓"
        text_ok += t == "✓"
        dino_ok += d == "✓"
        short = fname[:38]
        print(f"{short:<40} {true_t:>15} {f:>7} {t:>7} {d:>7}")

    n = len(all_files)
    print(f"{'-'*70}")
    print(f"{'정확도':>55} {fname_ok}/{n} {text_ok}/{n} {dino_ok}/{n}")
    print(f"{'(%)':>55} {fname_ok/n*100:>5.0f}% {text_ok/n*100:>5.0f}% {dino_ok/n*100:>5.0f}%")
    print(f"{'='*70}")


# ------------------------------------------------------------------ #
# main
# ------------------------------------------------------------------ #

def main():
    import time

    logger.info("벤치마크 시작")

    # UUID 마스킹 복사본 생성
    mapping = prepare_masked_copies()
    if not mapping:
        logger.error("컴파일 파일 없음 — 종료")
        return

    # 방법 1: 파일명
    logger.info("방법 1: 파일명 기반 라우팅")
    t0 = time.time()
    fname_results = test_filename_routing()
    logger.info(f"  → {time.time()-t0:.2f}s")
    print_table("방법 1: 파일명 기반", fname_results)

    # 방법 2: 텍스트 classifier
    logger.info("방법 2: 텍스트 classifier (UUID 파일명)")
    t0 = time.time()
    text_results = test_text_classifier(mapping)
    logger.info(f"  → {time.time()-t0:.2f}s")
    print_table("방법 2: 텍스트 Classifier (UUID)", text_results)

    # 방법 3: DINOv2
    logger.info("방법 3: DINOv2 시각 분류 (Leave-One-Out)")
    t0 = time.time()
    dino_results = test_dino_loo(mapping)
    logger.info(f"  → {time.time()-t0:.2f}s")
    print_table("방법 3: DINOv2 (Leave-One-Out, UUID)", dino_results)

    # 종합 비교
    print_comparison(fname_results, text_results, dino_results)

    # 마스킹 파일 정리
    shutil.rmtree(MASKED_DIR, ignore_errors=True)
    logger.info(f"마스킹 파일 정리 완료")


if __name__ == "__main__":
    main()
