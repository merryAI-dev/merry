"""
Dolphin Service Configuration

CPU 환경에서 최적화된 설정값을 정의합니다.
"""

import os
from pathlib import Path
from typing import Dict, List

# 모델 설정
DOLPHIN_CONFIG = {
    # 모델 경로
    "model_path": os.getenv("DOLPHIN_MODEL_PATH", "./models/dolphin-v2"),
    "model_id": "ByteDance/Dolphin-v2",

    # 디바이스 설정 (CPU 전용)
    "device": "cpu",
    "dtype": "float32",  # CPU는 bfloat16 비효율적

    # CPU 성능 튜닝
    "num_threads": os.cpu_count() or 4,
    "max_batch_size": 1,  # CPU에서는 순차 처리

    # 메모리 제한
    "min_memory_gb": 8,  # 최소 필요 메모리
    "max_memory_gb": 16,
    "low_memory_mode": True,

    # 처리 제한
    "default_max_pages": 30,
    "absolute_max_pages": 100,
    "timeout_seconds": 900,  # 15분 (정확도 우선)

    # 이미지 변환 설정 (PDF → 이미지)
    "image_dpi": 150,  # 속도와 품질 균형
    "image_format": "RGB",

    # 캐시 설정
    "cache_enabled": True,
    "cache_ttl_days": 7,
    "cache_namespace": "dolphin_pdf",
}

# 재무제표 테이블 감지 키워드 (한국어/영어)
FINANCIAL_TABLE_KEYWORDS: Dict[str, List[str]] = {
    "income_statement": [
        "손익계산서", "IS요약", "IS 요약", "Income Statement",
        "수익", "매출", "매출액", "영업이익", "당기순이익",
        "Revenue", "Operating Income", "Net Income", "P&L",
    ],
    "balance_sheet": [
        "재무상태표", "BS요약", "BS 요약", "Balance Sheet",
        "자산", "부채", "자본", "총자산", "총부채",
        "Assets", "Liabilities", "Equity",
    ],
    "cash_flow": [
        "현금흐름표", "CF요약", "CF 요약", "Cash Flow",
        "영업활동", "투자활동", "재무활동",
        "Operating Activities", "Investing Activities",
    ],
    "cap_table": [
        "Cap Table", "CapTable", "주주현황", "지분구조",
        "발행주식", "주식수", "지분율", "Shareholders",
    ],
}

# Dolphin 요소 타입 매핑
ELEMENT_TYPE_MAP = {
    "sec_0": "title",       # 제목
    "sec_1": "heading1",    # 소제목 1
    "sec_2": "heading2",    # 소제목 2
    "sec_3": "heading3",    # 소제목 3
    "para": "paragraph",    # 문단
    "tab": "table",         # 테이블
    "fig": "figure",        # 이미지/차트
    "equ": "equation",      # 수식
    "code": "code",         # 코드
    "list": "list",         # 목록
    "foot": "footnote",     # 각주
    "caption": "caption",   # 캡션
}

# 출력 모드
OUTPUT_MODES = ["text_only", "structured", "tables_only"]

# 로깅 설정
LOG_CONFIG = {
    "level": os.getenv("DOLPHIN_LOG_LEVEL", "INFO"),
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
}


def get_model_path() -> Path:
    """모델 경로 반환 (환경변수 우선)"""
    path = Path(DOLPHIN_CONFIG["model_path"])
    if path.exists():
        return path

    # 프로젝트 루트 기준 상대 경로 시도
    project_root = Path(__file__).parent.parent
    alt_path = project_root / "models" / "dolphin-v2"
    if alt_path.exists():
        return alt_path

    return path  # 존재하지 않아도 반환 (에러는 로딩 시 처리)


def validate_config() -> tuple:
    """설정 유효성 검사

    Returns:
        (is_valid: bool, error_message: str or None)
    """
    errors = []

    # 페이지 제한 검사
    if DOLPHIN_CONFIG["default_max_pages"] > DOLPHIN_CONFIG["absolute_max_pages"]:
        errors.append("default_max_pages가 absolute_max_pages보다 큼")

    # 메모리 제한 검사
    if DOLPHIN_CONFIG["min_memory_gb"] > DOLPHIN_CONFIG["max_memory_gb"]:
        errors.append("min_memory_gb가 max_memory_gb보다 큼")

    # 타임아웃 검사
    if DOLPHIN_CONFIG["timeout_seconds"] < 60:
        errors.append("timeout_seconds가 너무 짧음 (최소 60초)")

    if errors:
        return False, "; ".join(errors)
    return True, None
