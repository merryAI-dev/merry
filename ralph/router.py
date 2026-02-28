"""
HITL 라우터 — 4단계 문서 타입 자동 감지.

감지 파이프라인 (순서대로 폴백):
  1. 파일명 키워드 매칭  (conf 0.9, 0 API 비용)
  2. 텍스트 Classifier   (PyMuPDF + 키워드, 0 API 비용)
  3. VLM OCR 분류        (Nova Lite, 이미지에서 텍스트 읽어 분류)
  4. DINOv2 시각 분류    (선택적, 비용 없음 but 공문서 간 구별력 낮음)
  5. none                (HITL 수동 지정)

미지 문서(영수증, 계약서 등) 처리:
  - VLM이 "unknown" + description 반환
  - DetectionResult.detected_type=None, description에 문서 설명 포함
  - HITL 화면에서 사람이 확인
"""
from __future__ import annotations

import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field

from ralph.classifier import classify_document
from ralph.extraction.registry import list_supported_types

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """문서 타입 감지 결과."""
    file_id: str
    filename: str
    detected_type: str | None          # None = 미분류
    method: str                         # "filename"|"classifier"|"vlm"|"dino"|"none"
    confidence: float
    supported_types: list[str]
    description: str | None = None      # 미지 문서일 때 VLM이 생성한 설명


# ------------------------------------------------------------------ #
# 파일명 → 문서 타입 키워드 매핑
# ------------------------------------------------------------------ #

_FILENAME_HINTS: list[tuple[str, list[str]]] = [
    ("business_reg",     ["사업자등록증", "사업자등록", "사업자_등록"]),
    ("financial_stmt",   ["재무제표", "표준재무", "재무상태표", "손익계산서"]),
    ("shareholder",      ["주주명부", "주주_명부", "주주현황"]),
    ("investment_review",["투자검토", "투자_검토", "IR자료", "IR_자료"]),
    ("employee_list",    ["임직원명부", "임직원_명부", "4대보험", "사업장가입자"]),
    ("startup_cert",     ["창업기업확인서", "창업기업_확인서", "창업확인"]),
    ("certificate",      ["중소기업확인서", "벤처기업확인서", "기업부설연구소", "확인서"]),
    ("articles",         ["정관", "articles_of_incorporation"]),
    ("corp_registry",    ["등기부등본", "등기사항", "법인등기"]),
]


def detect_type_from_filename(filename: str) -> tuple[str | None, float]:
    """
    파일명에서 문서 타입 추론.

    Returns:
        (doc_type, confidence) — 매칭 실패 시 (None, 0.0)
    """
    name = unicodedata.normalize("NFC", os.path.splitext(filename)[0])
    name_clean = name.replace("_", " ").replace("-", " ").lower()
    name_nospace = name_clean.replace(" ", "")

    for doc_type, keywords in _FILENAME_HINTS:
        for kw in keywords:
            kw_lower = kw.lower()
            kw_nospace = kw_lower.replace("_", "").replace(" ", "")
            if kw_lower in name_clean or kw_nospace in name_nospace:
                return doc_type, 0.9
    return None, 0.0


# ------------------------------------------------------------------ #
# 메인 감지 함수
# ------------------------------------------------------------------ #

def detect_type(
    file_id: str,
    filename: str,
    pdf_path: str | None = None,
    use_vlm: bool = True,
    use_dino: bool = False,          # 벤치마크 결과 공문서 간 구별력 낮아 기본 off
) -> DetectionResult:
    """
    단일 파일 문서 타입 감지.

    Args:
        file_id:  파일 고유 ID
        filename: 원본 파일명
        pdf_path: 로컬 PDF 경로 (2~4단계에 필요)
        use_vlm:  VLM OCR 폴백 사용 여부 (기본 True)
        use_dino: DINOv2 시각 분류 폴백 (기본 False, 공문서 간 성능 낮음)

    Returns:
        DetectionResult — detected_type=None이면 미분류(HITL 필요)
    """
    supported = list_supported_types()

    # ── 1단계: 파일명 키워드 ───────────────────────────────────────
    doc_type, conf = detect_type_from_filename(filename)
    if doc_type:
        return DetectionResult(
            file_id=file_id, filename=filename,
            detected_type=doc_type, method="filename",
            confidence=conf, supported_types=supported,
        )

    if not (pdf_path and os.path.exists(pdf_path)):
        return DetectionResult(
            file_id=file_id, filename=filename,
            detected_type=None, method="none",
            confidence=0.0, supported_types=supported,
        )

    # ── 2단계: 텍스트 Classifier ───────────────────────────────────
    try:
        doc_type, conf = classify_document(pdf_path)
        if doc_type != "unknown" and conf > 0.0:
            return DetectionResult(
                file_id=file_id, filename=filename,
                detected_type=doc_type, method="classifier",
                confidence=conf, supported_types=supported,
            )
    except Exception as e:
        logger.debug(f"텍스트 classifier 예외: {e}")

    # ── 3단계: VLM OCR 분류 ────────────────────────────────────────
    if use_vlm:
        try:
            from ralph.vlm.doc_classifier import get_vlm_doc_classifier
            vlm_clf = get_vlm_doc_classifier()
            doc_type, conf, description = vlm_clf.classify(pdf_path)
            if doc_type != "unknown" and conf > 0.0:
                return DetectionResult(
                    file_id=file_id, filename=filename,
                    detected_type=doc_type, method="vlm",
                    confidence=conf, supported_types=supported,
                )
            # VLM이 unknown 반환 → 미지 문서로 처리 (더 이상 폴백 불필요)
            if description:
                logger.info(f"VLM 미지 문서: {description}")
                return DetectionResult(
                    file_id=file_id, filename=filename,
                    detected_type=None, method="vlm",
                    confidence=0.0, supported_types=supported,
                    description=description,
                )
        except Exception as e:
            logger.warning(f"VLM 분류 실패: {e}")

    # ── 4단계: DINOv2 (선택적) ─────────────────────────────────────
    if use_dino:
        try:
            from ralph.dino_classifier import get_dino_classifier
            clf = get_dino_classifier()
            doc_type, conf = clf.classify(pdf_path)
            if doc_type != "unknown" and conf > 0.0:
                return DetectionResult(
                    file_id=file_id, filename=filename,
                    detected_type=doc_type, method="dino",
                    confidence=conf, supported_types=supported,
                )
        except Exception as e:
            logger.warning(f"DINOv2 분류 실패: {e}")

    # ── 감지 실패 ──────────────────────────────────────────────────
    return DetectionResult(
        file_id=file_id, filename=filename,
        detected_type=None, method="none",
        confidence=0.0, supported_types=supported,
    )


# ------------------------------------------------------------------ #
# 배치 처리
# ------------------------------------------------------------------ #

@dataclass
class FileInfo:
    """배치 감지용 파일 정보."""
    file_id: str
    filename: str
    pdf_path: str | None = None


def detect_types_batch(
    file_infos: list[FileInfo],
    use_vlm: bool = True,
    use_dino: bool = False,
) -> list[DetectionResult]:
    """다건 파일 문서 타입 일괄 감지."""
    return [
        detect_type(
            file_id=fi.file_id,
            filename=fi.filename,
            pdf_path=fi.pdf_path,
            use_vlm=use_vlm,
            use_dino=use_dino,
        )
        for fi in file_infos
    ]
