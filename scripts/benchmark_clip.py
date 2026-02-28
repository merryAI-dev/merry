"""
CLIP 문서 분류 벤치마크.

세 가지 전략 비교:
  A. English CLIP (openai/clip-vit-large-patch14) + 영어 프롬프트
  B. Multilingual CLIP (laion/CLIP-ViT-B-32-xlm-roberta-base-laion5B-s13B-b90k) + 한국어 프롬프트
  C. English CLIP + 헤더 크롭 (상단 25%)

실행:
    BENCHMARK_DATA_DIR=/path/to/docs python scripts/benchmark_clip.py
"""
from __future__ import annotations

import io
import logging
import os
import sys
import time
from pathlib import Path

import fitz
import numpy as np
import torch
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / "web" / ".env.local", override=False)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("clip_bench")

# ------------------------------------------------------------------ #
# Ground truth (익명화 — 실제 파일명으로 채우세요)
# ------------------------------------------------------------------ #
COMPANY_DATA_DIR = Path(os.getenv("BENCHMARK_DATA_DIR", str(PROJECT_ROOT / "companyData")))

GROUND_TRUTH: dict[str, str] = {
    "1. MYSC_투자검토자료_스트레스솔루션_251211.pdf": "investment_review",
    "10. MYSC_IR 자료.pdf": "investment_review",
    "2. MYSC_주주명부('25.10.16)_주식회사 스트레스솔루션.pdf": "shareholder",
    "3. MYSC_임직원 명부 (4대보험가입자 명부).pdf": "employee_list",
    "4. MYSC_사업자등록증.pdf": "business_reg",
    "5. MYSC_법인등기부등본 (말소사항포함).pdf": "corp_registry",
    "6-1. MYSC_2022년 표준재무제표증명.pdf": "financial_stmt",
    "6-2. MYSC_2023년 표준재무제표증명.pdf": "financial_stmt",
    "6-3. MYSC_2024년 표준재무제표증명.pdf": "financial_stmt",
    "6-4. MYSC_2025년 표준재무제표증명.pdf": "financial_stmt",
    "7. MYSC_정관사본.pdf": "articles",
    "8. MYSC_인증서(중소기업, 벤처기업, 기업부설연구소, 스피커 전파인증KC).pdf": "certificate",
    "9. MYSC_창업기업확인서.pdf": "startup_cert",
}

# ------------------------------------------------------------------ #
# 프롬프트 정의
# ------------------------------------------------------------------ #
ENGLISH_PROMPTS: dict[str, str] = {
    "business_reg":     "a Korean business registration certificate document",
    "financial_stmt":   "a Korean financial statement or tax certificate document with tables",
    "shareholder":      "a Korean shareholder registry or stock ownership document",
    "employee_list":    "a Korean employee list or national insurance enrollment document",
    "corp_registry":    "a Korean corporate registry certificate from court",
    "articles":         "a Korean articles of incorporation company bylaws document",
    "investment_review":"a startup investment review presentation or IR pitch deck slides",
    "certificate":      "a Korean government-issued SME or venture company certificate",
    "startup_cert":     "a Korean startup company certificate confirmation document",
}

KOREAN_PROMPTS: dict[str, str] = {
    "business_reg":     "사업자등록증 문서",
    "financial_stmt":   "재무제표 또는 표준재무제표증명 서류",
    "shareholder":      "주주명부 서류",
    "employee_list":    "임직원 명부 또는 4대보험 가입자 명부",
    "corp_registry":    "법인등기부등본 서류",
    "articles":         "정관 사본 서류",
    "investment_review":"투자검토자료 또는 IR 발표 자료 슬라이드",
    "certificate":      "중소기업확인서 또는 벤처기업확인서",
    "startup_cert":     "창업기업확인서 서류",
}

DOC_TYPES = list(ENGLISH_PROMPTS.keys())


# ------------------------------------------------------------------ #
# 이미지 추출 유틸
# ------------------------------------------------------------------ #

def pdf_to_image(pdf_path: str, dpi: int = 150, crop_top_ratio: float = 1.0) -> Image.Image:
    """PDF 첫 페이지 → PIL Image. crop_top_ratio=0.25면 상단 25%만."""
    doc = fitz.open(pdf_path)
    try:
        page = doc[0]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    finally:
        doc.close()

    if crop_top_ratio < 1.0:
        w, h = img.size
        img = img.crop((0, 0, w, int(h * crop_top_ratio)))
    return img


# ------------------------------------------------------------------ #
# CLIP 분류기
# ------------------------------------------------------------------ #

class CLIPClassifier:
    def __init__(self, model_name: str, label: str):
        self.model_name = model_name
        self.label = label
        self._model = None
        self._processor = None
        self._device = None

    def _load(self):
        if self._model:
            return
        from transformers import CLIPModel, CLIPProcessor
        self._device = "mps" if torch.backends.mps.is_available() else "cpu"
        logger.info(f"CLIP 로드: {self.model_name} ({self._device})")
        self._processor = CLIPProcessor.from_pretrained(self.model_name)
        self._model = CLIPModel.from_pretrained(self.model_name).to(self._device)
        self._model.eval()

    def classify(
        self,
        image: Image.Image,
        prompts: dict[str, str],
    ) -> tuple[str, float]:
        """
        이미지를 prompts의 각 텍스트와 비교 → 가장 높은 similarity의 doc_type 반환.
        """
        self._load()

        texts = [prompts[t] for t in DOC_TYPES]
        inputs = self._processor(
            text=texts,
            images=image,
            return_tensors="pt",
            padding=True,
            truncation=True,
        )
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)
            # logits_per_image: [1, num_texts]
            probs = outputs.logits_per_image.softmax(dim=-1).squeeze(0).cpu().numpy()

        best_idx = int(np.argmax(probs))
        return DOC_TYPES[best_idx], float(probs[best_idx])


# ------------------------------------------------------------------ #
# 벤치마크 실행
# ------------------------------------------------------------------ #

def run_strategy(
    clf: CLIPClassifier,
    prompts: dict[str, str],
    crop_top: float = 1.0,
    strategy_label: str = "",
) -> list[dict]:
    results = []
    for fname, true_type in GROUND_TRUTH.items():
        fpath = COMPANY_DATA_DIR / fname
        if not fpath.exists():
            continue
        img = pdf_to_image(str(fpath), dpi=150, crop_top_ratio=crop_top)
        detected, conf = clf.classify(img, prompts)
        results.append({
            "filename": fname,
            "true_type": true_type,
            "detected": detected,
            "confidence": round(conf, 3),
            "correct": detected == true_type,
            "strategy": strategy_label,
        })
    return results


def print_table(title: str, results: list[dict]):
    n = len(results)
    correct = sum(1 for r in results if r["correct"])
    print(f"\n{'='*72}")
    print(f"  {title}  ({correct}/{n}, {correct/max(n,1)*100:.1f}%)")
    print(f"{'='*72}")
    print(f"{'파일명':<45} {'실제':>15} {'감지':>15} {'확률':>6}")
    print(f"{'-'*72}")
    for r in results:
        ok = "✓" if r["correct"] else "✗"
        short = r["filename"][:43]
        print(f"{ok} {short:<43} {r['true_type']:>15} {r['detected']:>15} {r['confidence']:>6.3f}")
    print(f"{'='*72}")


def print_final_comparison(all_results: dict[str, list[dict]]):
    print(f"\n{'='*72}")
    print("  종합 비교")
    print(f"{'='*72}")
    headers = list(all_results.keys())
    print(f"{'파일명':<38}", end="")
    for h in headers:
        print(f" {h[:8]:>9}", end="")
    print()
    print(f"{'-'*72}")

    all_fnames = list(GROUND_TRUTH.keys())
    totals = {h: 0 for h in headers}
    for fname in all_fnames:
        short = fname[:36]
        print(f"{short:<38}", end="")
        for h in headers:
            res = next((r for r in all_results[h] if r["filename"] == fname), None)
            mark = "✓" if res and res["correct"] else "✗"
            if res and res["correct"]:
                totals[h] += 1
            print(f" {mark:>9}", end="")
        print()

    n = len(all_fnames)
    print(f"{'-'*72}")
    print(f"{'정확도':>38}", end="")
    for h in headers:
        print(f" {totals[h]}/{n}".rjust(9) + " ", end="")
    print()
    print(f"{'%':>38}", end="")
    for h in headers:
        print(f" {totals[h]/n*100:.0f}%".rjust(9) + " ", end="")
    print()
    print(f"{'='*72}")


def main():
    # 모델 선택
    EN_MODEL = "openai/clip-vit-large-patch14"
    ML_MODEL = "laion/CLIP-ViT-B-32-xlm-roberta-base-laion5B-s13B-b90k"

    all_results: dict[str, list[dict]] = {}

    # 기준선: DINOv2 & 텍스트 classifier 결과 하드코딩 (이전 벤치마크)
    # (비교 편의를 위해 포함)
    all_results["텍스트CLS"] = [
        {"filename": f, "true_type": t, "detected": t if f not in [
            "10. MYSC_IR 자료.pdf",
            "5. MYSC_법인등기부등본 (말소사항포함).pdf",
        ] else "unknown", "correct": f not in [
            "10. MYSC_IR 자료.pdf",
            "5. MYSC_법인등기부등본 (말소사항포함).pdf",
        ], "confidence": 0.9, "strategy": "텍스트CLS"}
        for f, t in GROUND_TRUTH.items()
    ]
    all_results["DINOv2"] = [
        {"filename": f, "true_type": t, "detected": t if f in [
            "6-1. MYSC_2022년 표준재무제표증명.pdf",
            "6-2. MYSC_2023년 표준재무제표증명.pdf",
            "6-3. MYSC_2024년 표준재무제표증명.pdf",
        ] else "wrong", "correct": f in [
            "6-1. MYSC_2022년 표준재무제표증명.pdf",
            "6-2. MYSC_2023년 표준재무제표증명.pdf",
            "6-3. MYSC_2024년 표준재무제표증명.pdf",
        ], "confidence": 0.9, "strategy": "DINOv2"}
        for f, t in GROUND_TRUTH.items()
    ]

    # A. English CLIP, 전체 페이지
    logger.info("=== 전략 A: English CLIP (전체 페이지) ===")
    clf_en = CLIPClassifier(EN_MODEL, "EN-CLIP")
    t0 = time.time()
    results_a = run_strategy(clf_en, ENGLISH_PROMPTS, crop_top=1.0, strategy_label="EN-CLIP")
    logger.info(f"완료 ({time.time()-t0:.1f}s)")
    print_table("A. English CLIP — 전체 페이지", results_a)
    all_results["EN-CLIP"] = results_a

    # B. English CLIP, 헤더 크롭 (상단 25%)
    logger.info("=== 전략 B: English CLIP (헤더 크롭 25%) ===")
    t0 = time.time()
    results_b = run_strategy(clf_en, ENGLISH_PROMPTS, crop_top=0.25, strategy_label="EN-CLIP-crop")
    logger.info(f"완료 ({time.time()-t0:.1f}s)")
    print_table("B. English CLIP — 헤더 크롭 상단 25%", results_b)
    all_results["EN-crop"] = results_b

    # C. Multilingual CLIP, 한국어 프롬프트
    logger.info("=== 전략 C: Multilingual CLIP + 한국어 프롬프트 ===")
    clf_ml = CLIPClassifier(ML_MODEL, "ML-CLIP")
    t0 = time.time()
    results_c = run_strategy(clf_ml, KOREAN_PROMPTS, crop_top=1.0, strategy_label="ML-CLIP-KO")
    logger.info(f"완료 ({time.time()-t0:.1f}s)")
    print_table("C. Multilingual CLIP — 한국어 프롬프트", results_c)
    all_results["ML-CLIP"] = results_c

    # D. Multilingual CLIP, 한국어, 헤더 크롭
    logger.info("=== 전략 D: Multilingual CLIP + 한국어 + 헤더 크롭 ===")
    t0 = time.time()
    results_d = run_strategy(clf_ml, KOREAN_PROMPTS, crop_top=0.25, strategy_label="ML-CLIP-KO-crop")
    logger.info(f"완료 ({time.time()-t0:.1f}s)")
    print_table("D. Multilingual CLIP — 한국어 + 헤더 크롭 25%", results_d)
    all_results["ML-crop"] = results_d

    # 종합 비교
    print_final_comparison(all_results)


if __name__ == "__main__":
    main()
