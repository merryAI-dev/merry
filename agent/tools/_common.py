"""
Shared infrastructure for agent tools.

Common constants, helpers, and utilities used across all domain modules.
"""

import json
import logging
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.cache_utils import (
    compute_file_hash,
    compute_payload_hash,
    get_cache_dir,
    load_json,
    save_json,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_VERSION = "v3"
CACHE_TTL_SECONDS = 86400 * 7  # 7 days


def retry_with_backoff(
    max_retries=3, initial_delay=1.0, backoff_factor=2.0, exceptions=(Exception,)
):
    """지수 백오프 재시도 데코레이터"""

    def decorator(func):
        import functools

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay *= backoff_factor

        return wrapper

    return decorator


def _sanitize_filename(filename: str) -> str:
    """파일명 sanitize — 위험 문자 제거"""
    if not filename:
        return "output"
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(filename))
    sanitized = sanitized.strip(". ")
    if not sanitized:
        return "output"
    return sanitized[:200]


def _validate_file_path(
    file_path: str,
    allowed_extensions: List[str] = None,
    require_temp_dir: bool = False,
) -> tuple:
    """파일 경로 보안 검증

    Returns:
        (is_valid: bool, error_message: str or None)
    """
    if not file_path:
        return False, "파일 경로가 비어 있습니다"

    path = Path(file_path).resolve()

    # 경로 순회 공격 방지
    try:
        path_str = str(path)
        if ".." in file_path:
            return False, "경로에 '..'를 사용할 수 없습니다"
    except Exception:
        return False, "잘못된 경로 형식입니다"

    # 확장자 검증
    if allowed_extensions:
        if not any(path_str.lower().endswith(ext.lower()) for ext in allowed_extensions):
            return False, f"허용되지 않는 파일 형식입니다. 허용: {', '.join(allowed_extensions)}"

    # temp 디렉토리 제한 (선택적)
    if require_temp_dir:
        temp_root = (PROJECT_ROOT / "temp").resolve()
        shared_root = (PROJECT_ROOT / "shared").resolve()
        companyData_root = (PROJECT_ROOT / "companyData").resolve()
        try:
            path.relative_to(temp_root)
        except ValueError:
            try:
                path.relative_to(shared_root)
            except ValueError:
                try:
                    path.relative_to(companyData_root)
                except ValueError:
                    return (
                        False,
                        "파일은 temp/, shared/, 또는 companyData/ 디렉토리 내에 있어야 합니다",
                    )

    return True, None


def _validate_numeric_param(
    value: Any, name: str, min_val: float = None, max_val: float = None
) -> tuple:
    """숫자 파라미터 검증

    Returns:
        (is_valid: bool, validated_value: float or None, error_message: str or None)
    """
    try:
        val = float(value)
    except (TypeError, ValueError):
        return False, None, f"{name}은(는) 숫자여야 합니다"

    if math.isnan(val) or math.isinf(val):
        return False, None, f"{name}은(는) 유효한 숫자여야 합니다"

    if min_val is not None and val < min_val:
        return False, None, f"{name}은(는) {min_val} 이상이어야 합니다"

    if max_val is not None and val > max_val:
        return False, None, f"{name}은(는) {max_val} 이하여야 합니다"

    return True, val, None


def _normalize_text(text: str) -> str:
    """텍스트 정규화 — 공백, 줄바꿈 정리"""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()
