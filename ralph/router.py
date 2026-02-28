"""
HITL 라우터 — 파일명 기반 문서 타입 자동 감지 + classifier 폴백.

파일명에서 한국어 키워드 매칭으로 문서 타입을 추론하고,
실패 시 classifier.py의 텍스트 기반 분류로 폴백.
"""
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass

from ralph.classifier import classify_document
from ralph.extraction.registry import list_supported_types


@dataclass
class DetectionResult:
    """문서 타입 감지 결과."""
    file_id: str
    filename: str
    detected_type: str | None
    method: str  # "filename" | "classifier" | "dino" | "none"
    confidence: float
    supported_types: list[str]


# 파일명 → 문서 타입 매핑 (한국어 키워드)
_FILENAME_HINTS: list[tuple[str, list[str]]] = [
    ("business_reg", ["사업자등록증", "사업자등록", "사업자_등록"]),
    ("financial_stmt", ["재무제표", "표준재무", "재무상태표", "손익계산서"]),
    ("shareholder", ["주주명부", "주주_명부", "주주현황"]),
    ("investment_review", ["투자검토", "투자_검토", "IR자료", "IR_자료"]),
    ("employee_list", ["임직원명부", "임직원_명부", "4대보험", "사업장가입자"]),
    ("startup_cert", ["창업기업확인서", "창업기업_확인서", "창업확인"]),
    ("certificate", ["중소기업확인서", "벤처기업확인서", "기업부설연구소", "확인서"]),
    ("articles", ["정관", "articles_of_incorporation"]),
    ("corp_registry", ["등기부등본", "등기사항", "법인등기"]),
]


def detect_type_from_filename(filename: str) -> tuple[str | None, float]:
    """
    파일명에서 문서 타입 추론.

    Args:
        filename: 파일명 (확장자 포함)

    Returns:
        (doc_type, confidence) — 매칭 실패 시 (None, 0.0)
    """
    # 확장자 제거 + NFC 정규화 (macOS NFD 대응) + 소문자 + 언더스코어/하이픈 → 공백
    name = unicodedata.normalize("NFC", os.path.splitext(filename)[0])
    name_clean = name.replace("_", " ").replace("-", " ").lower()
    # 공백 제거 버전도 (붙여쓰기 대응)
    name_nospace = name_clean.replace(" ", "")

    for doc_type, keywords in _FILENAME_HINTS:
        for kw in keywords:
            kw_lower = kw.lower()
            kw_nospace = kw_lower.replace("_", "").replace(" ", "")
            if kw_lower in name_clean or kw_nospace in name_nospace:
                return doc_type, 0.9
    return None, 0.0


def detect_type(
    file_id: str,
    filename: str,
    pdf_path: str | None = None,
    use_dino: bool = True,
) -> DetectionResult:
    """
    단일 파일 문서 타입 감지 (파일명 → 텍스트 classifier → DINOv2 → none).

    Args:
        file_id: 파일 고유 ID
        filename: 원본 파일명
        pdf_path: 로컬 PDF 경로 (classifier/dino 폴백용)
        use_dino: DINOv2 폴백 사용 여부 (기본 True)

    Returns:
        DetectionResult
    """
    supported = list_supported_types()

    # 1차: 파일명 매칭
    doc_type, conf = detect_type_from_filename(filename)
    if doc_type:
        return DetectionResult(
            file_id=file_id,
            filename=filename,
            detected_type=doc_type,
            method="filename",
            confidence=conf,
            supported_types=supported,
        )

    # 2차: 텍스트 classifier (PDF 필요)
    if pdf_path and os.path.exists(pdf_path):
        try:
            doc_type, conf = classify_document(pdf_path)
            if doc_type != "unknown" and conf > 0.0:
                return DetectionResult(
                    file_id=file_id,
                    filename=filename,
                    detected_type=doc_type,
                    method="classifier",
                    confidence=conf,
                    supported_types=supported,
                )
        except Exception:
            pass

        # 3차: DINOv2 시각 분류 (텍스트 classifier 실패 시)
        if use_dino:
            try:
                from ralph.dino_classifier import get_dino_classifier
                clf = get_dino_classifier()
                doc_type, conf = clf.classify(pdf_path)
                if doc_type != "unknown" and conf > 0.0:
                    return DetectionResult(
                        file_id=file_id,
                        filename=filename,
                        detected_type=doc_type,
                        method="dino",
                        confidence=conf,
                        supported_types=supported,
                    )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"DINOv2 분류 실패: {e}")

    # 감지 실패
    return DetectionResult(
        file_id=file_id,
        filename=filename,
        detected_type=None,
        method="none",
        confidence=0.0,
        supported_types=supported,
    )


@dataclass
class FileInfo:
    """배치 감지용 파일 정보."""
    file_id: str
    filename: str
    pdf_path: str | None = None


def detect_types_batch(file_infos: list[FileInfo]) -> list[DetectionResult]:
    """
    다건 파일 문서 타입 일괄 감지.

    Args:
        file_infos: 파일 정보 리스트

    Returns:
        DetectionResult 리스트 (입력 순서 유지)
    """
    return [
        detect_type(
            file_id=fi.file_id,
            filename=fi.filename,
            pdf_path=fi.pdf_path,
        )
        for fi in file_infos
    ]
