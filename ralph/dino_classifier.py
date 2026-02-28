"""
DINOv2 시각 문서 분류기.

PyMuPDF로 첫 페이지 렌더링 → DINOv2(facebook/dinov2-base) 임베딩 →
레퍼런스 임베딩과 cosine similarity 비교 → 문서 타입 반환.

레퍼런스 임베딩은 JSON 파일로 저장/로드.
없으면 컴파일 시 companyData 폴더에서 자동 빌드.
"""
from __future__ import annotations

import json
import logging
import os
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

_MODEL_NAME = "facebook/dinov2-base"
_DEFAULT_REFS_PATH = Path(__file__).parent / "dino_refs.pkl"

# companyData 파일명 → doc_type 매핑 (레퍼런스 빌드용).
# 실제 운영 시 해당 프로젝트의 레퍼런스 문서 파일명과 doc_type을 매핑하세요.
# 예시:
# _COMPANY_DATA_LABELS: dict[str, str] = {
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
_COMPANY_DATA_LABELS: dict[str, str] = {}


@dataclass
class DinoRef:
    """레퍼런스 임베딩 항목."""
    doc_type: str
    source_path: str
    embedding: np.ndarray


class DinoClassifier:
    """
    DINOv2 기반 시각 문서 분류기.

    사용법:
        clf = DinoClassifier()
        clf.build_refs(companydata_dir, refs_path)  # 최초 1회
        doc_type, conf = clf.classify(pdf_path)
    """

    def __init__(self, refs_path: str | Path | None = None):
        self._refs_path = Path(refs_path) if refs_path else _DEFAULT_REFS_PATH
        self._refs: list[DinoRef] = []
        self._model = None
        self._processor = None
        self._device = None

    # ------------------------------------------------------------------ #
    # 모델 로드 (지연 초기화)
    # ------------------------------------------------------------------ #

    def _load_model(self):
        if self._model is not None:
            return
        import torch
        from transformers import AutoImageProcessor, AutoModel

        self._device = "mps" if torch.backends.mps.is_available() else "cpu"
        logger.info(f"DINOv2 로드 중 ({self._device})…")
        self._processor = AutoImageProcessor.from_pretrained(_MODEL_NAME)
        self._model = AutoModel.from_pretrained(_MODEL_NAME).to(self._device)
        self._model.eval()
        logger.info("DINOv2 로드 완료")

    # ------------------------------------------------------------------ #
    # 임베딩 추출
    # ------------------------------------------------------------------ #

    def _embed_pdf(self, pdf_path: str, page_idx: int = 0, dpi: int = 150) -> np.ndarray:
        """PDF 한 페이지 → DINOv2 CLS 토큰 임베딩 (L2 정규화)."""
        import torch
        import fitz
        from PIL import Image
        import io

        self._load_model()

        doc = fitz.open(pdf_path)
        try:
            page = doc[min(page_idx, doc.page_count - 1)]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            img_bytes = page.get_pixmap(matrix=mat).tobytes("png")
        finally:
            doc.close()

        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        inputs = self._processor(images=img, return_tensors="pt")
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)
            emb = outputs.last_hidden_state[:, 0, :].squeeze(0).cpu().numpy()

        # L2 정규화
        norm = np.linalg.norm(emb)
        return emb / (norm + 1e-8)

    # ------------------------------------------------------------------ #
    # 레퍼런스 빌드 & 저장/로드
    # ------------------------------------------------------------------ #

    def build_refs(
        self,
        companydata_dir: str | Path,
        save_path: str | Path | None = None,
        exclude_files: list[str] | None = None,
    ) -> int:
        """
        companyData 폴더에서 레퍼런스 임베딩 빌드.

        Args:
            companydata_dir: companyData 폴더 경로
            save_path: 저장 경로 (None이면 self._refs_path)
            exclude_files: 제외할 파일명 목록 (leave-one-out 벤치마크용)

        Returns:
            빌드된 레퍼런스 수
        """
        companydata_dir = Path(companydata_dir)
        exclude_set = set(exclude_files or [])
        refs = []

        for fname, doc_type in _COMPANY_DATA_LABELS.items():
            if fname in exclude_set:
                continue
            fpath = companydata_dir / fname
            if not fpath.exists():
                logger.warning(f"레퍼런스 파일 없음: {fpath}")
                continue
            try:
                emb = self._embed_pdf(str(fpath))
                refs.append(DinoRef(doc_type=doc_type, source_path=str(fpath), embedding=emb))
                logger.info(f"  ✓ {fname} → {doc_type}")
            except Exception as e:
                logger.error(f"  ✗ {fname}: {e}")

        self._refs = refs
        save_to = Path(save_path) if save_path else self._refs_path
        save_to.parent.mkdir(parents=True, exist_ok=True)
        with open(save_to, "wb") as f:
            pickle.dump(refs, f)
        logger.info(f"레퍼런스 {len(refs)}개 저장 → {save_to}")
        return len(refs)

    def load_refs(self, refs_path: str | Path | None = None) -> int:
        """저장된 레퍼런스 임베딩 로드."""
        path = Path(refs_path) if refs_path else self._refs_path
        if not path.exists():
            return 0
        with open(path, "rb") as f:
            self._refs = pickle.load(f)
        logger.debug(f"레퍼런스 {len(self._refs)}개 로드 ← {path}")
        return len(self._refs)

    # ------------------------------------------------------------------ #
    # 분류
    # ------------------------------------------------------------------ #

    def classify(
        self,
        pdf_path: str,
        threshold: float = 0.55,
        top_k: int = 3,
    ) -> tuple[str, float]:
        """
        DINOv2 임베딩으로 문서 타입 분류.

        Args:
            pdf_path: 분류할 PDF 경로
            threshold: 최소 cosine similarity (미달 시 "unknown" 반환)
            top_k: 투표에 사용할 최근접 이웃 수

        Returns:
            (doc_type, confidence): "unknown" 반환 가능
        """
        if not self._refs:
            loaded = self.load_refs()
            if not loaded:
                logger.warning("DINOv2 레퍼런스 없음 — 분류 불가")
                return "unknown", 0.0

        try:
            emb = self._embed_pdf(pdf_path)
        except Exception as e:
            logger.error(f"DINOv2 임베딩 실패: {e}")
            return "unknown", 0.0

        # cosine similarity (임베딩이 L2 정규화되어 있으므로 내적 = cos_sim)
        sims = [(ref.doc_type, float(np.dot(emb, ref.embedding))) for ref in self._refs]
        sims.sort(key=lambda x: x[1], reverse=True)

        top = sims[:top_k]
        best_sim = top[0][1]

        if best_sim < threshold:
            return "unknown", best_sim

        # 상위 k개 투표 (similarity 가중)
        votes: dict[str, float] = {}
        for dtype, sim in top:
            votes[dtype] = votes.get(dtype, 0.0) + sim
        winner = max(votes, key=lambda k: votes[k])
        confidence = best_sim

        return winner, confidence

    def classify_with_refs(
        self,
        pdf_path: str,
        refs: list[DinoRef],
        threshold: float = 0.55,
        top_k: int = 3,
    ) -> tuple[str, float]:
        """
        외부 레퍼런스 목록으로 분류 (leave-one-out 벤치마크용).
        """
        if not refs:
            return "unknown", 0.0
        try:
            emb = self._embed_pdf(pdf_path)
        except Exception as e:
            logger.error(f"DINOv2 임베딩 실패: {e}")
            return "unknown", 0.0

        sims = [(ref.doc_type, float(np.dot(emb, ref.embedding))) for ref in refs]
        sims.sort(key=lambda x: x[1], reverse=True)
        top = sims[:top_k]
        best_sim = top[0][1]

        if best_sim < threshold:
            return "unknown", best_sim

        votes: dict[str, float] = {}
        for dtype, sim in top:
            votes[dtype] = votes.get(dtype, 0.0) + sim
        winner = max(votes, key=lambda k: votes[k])
        return winner, best_sim


# 싱글톤 (router에서 재사용)
_instance: DinoClassifier | None = None


def get_dino_classifier() -> DinoClassifier:
    global _instance
    if _instance is None:
        _instance = DinoClassifier()
    return _instance
