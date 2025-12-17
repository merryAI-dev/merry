"""
파일 업로드 보안 유틸리티
- 사용자별 격리된 업로드 경로
- 파일명 검증 및 정화
- 파일 크기/확장자 검증
- TTL 기반 임시 파일 정리
"""

import re
import uuid
import time
from pathlib import Path
from typing import Optional, Tuple

from shared.logging_config import get_logger

logger = get_logger("file_utils")

# 파일 업로드 제한
MAX_FILE_SIZE_MB = 50  # 최대 파일 크기 (MB)
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS_EXCEL = ['.xlsx', '.xls']
ALLOWED_EXTENSIONS_PDF = ['.pdf']
DEFAULT_TTL_DAYS = 7  # 기본 TTL (일)


def sanitize_filename(filename: str) -> str:
    """
    파일명에서 위험한 문자 제거

    Args:
        filename: 원본 파일명

    Returns:
        정화된 파일명
    """
    if not filename:
        return "unnamed"

    # 경로 구분자 제거 (path traversal 방지)
    filename = filename.replace("/", "_").replace("\\", "_")

    # 허용: 알파벳, 숫자, 한글, 언더스코어, 하이픈, 점, 공백
    sanitized = re.sub(r'[^\w\s가-힣.\-]', '_', filename, flags=re.UNICODE)

    # 연속된 언더스코어/공백 정리
    sanitized = re.sub(r'[_\s]+', '_', sanitized)

    # 앞뒤 특수문자 제거
    sanitized = sanitized.strip('_. ')

    # 빈 문자열 방지
    return sanitized or "unnamed"


def get_secure_upload_path(
    user_id: str,
    original_filename: str,
    base_dir: str = "temp"
) -> Path:
    """
    사용자별 격리된 안전한 업로드 경로 생성

    Args:
        user_id: 사용자 고유 ID (API 키 해시)
        original_filename: 원본 파일명
        base_dir: 기본 업로드 디렉토리

    Returns:
        안전한 업로드 경로 (Path 객체)

    구조: temp/<user_id>/<uuid>_<safe_filename>
    """
    # 파일명 정화
    safe_filename = sanitize_filename(original_filename)

    # 고유 ID 생성 (동명이인 파일 덮어쓰기 방지)
    unique_id = uuid.uuid4().hex[:8]

    # 사용자별 디렉토리 생성
    upload_dir = Path(base_dir) / user_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 최종 경로
    final_path = upload_dir / f"{unique_id}_{safe_filename}"

    logger.info(f"Secure upload path created: {final_path}")
    return final_path


def validate_file_extension(
    filename: str,
    allowed_extensions: list
) -> tuple:
    """
    파일 확장자 검증

    Args:
        filename: 파일명
        allowed_extensions: 허용된 확장자 리스트 (예: ['.xlsx', '.pdf'])

    Returns:
        (is_valid: bool, error_message: Optional[str])
    """
    if not filename:
        return False, "파일명이 비어있습니다"

    ext = Path(filename).suffix.lower()

    # 확장자 정규화 (. 포함)
    normalized_extensions = [
        e.lower() if e.startswith('.') else f'.{e.lower()}'
        for e in allowed_extensions
    ]

    if ext not in normalized_extensions:
        return False, f"허용되지 않은 파일 형식입니다. 허용: {', '.join(allowed_extensions)}"

    return True, None


def validate_upload(
    filename: str,
    file_size: int,
    allowed_extensions: list = None
) -> Tuple[bool, Optional[str]]:
    """
    업로드 전 파일 검증 (확장자 + 크기)

    Args:
        filename: 파일명
        file_size: 파일 크기 (bytes)
        allowed_extensions: 허용된 확장자 리스트 (기본: 엑셀+PDF)

    Returns:
        (is_valid: bool, error_message: Optional[str])
    """
    if allowed_extensions is None:
        allowed_extensions = ALLOWED_EXTENSIONS_EXCEL + ALLOWED_EXTENSIONS_PDF

    # 확장자 검증
    is_valid, error = validate_file_extension(filename, allowed_extensions)
    if not is_valid:
        return False, error

    # 크기 검증
    if file_size > MAX_FILE_SIZE_BYTES:
        return False, f"파일 크기가 너무 큽니다. 최대: {MAX_FILE_SIZE_MB}MB"

    if file_size == 0:
        return False, "빈 파일입니다"

    return True, None


def cleanup_user_temp_files(
    user_id: str,
    base_dir: str = "temp",
    max_files: int = 10,
    ttl_days: int = DEFAULT_TTL_DAYS
):
    """
    사용자의 오래된 임시 파일 정리 (개수 + TTL 기반)

    Args:
        user_id: 사용자 고유 ID
        base_dir: 기본 업로드 디렉토리
        max_files: 유지할 최대 파일 수
        ttl_days: 파일 보관 기간 (일)
    """
    user_dir = Path(base_dir) / user_id
    if not user_dir.exists():
        return

    current_time = time.time()
    ttl_seconds = ttl_days * 24 * 60 * 60

    # 파일 목록 (수정 시간 기준 정렬)
    files = sorted(
        [f for f in user_dir.glob("*") if f.is_file()],
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    # TTL 초과 파일 삭제
    for file in files:
        try:
            file_age = current_time - file.stat().st_mtime
            if file_age > ttl_seconds:
                file.unlink()
                logger.info(f"TTL cleanup - deleted: {file} (age: {file_age/86400:.1f} days)")
        except OSError as e:
            logger.warning(f"Failed to delete TTL-expired file {file}: {e}")

    # 남은 파일 중 개수 초과분 삭제
    remaining_files = sorted(
        [f for f in user_dir.glob("*") if f.is_file()],
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    for old_file in remaining_files[max_files:]:
        try:
            old_file.unlink()
            logger.info(f"Count cleanup - deleted: {old_file}")
        except OSError as e:
            logger.warning(f"Failed to clean up {old_file}: {e}")


def cleanup_all_temp_files(base_dir: str = "temp", ttl_days: int = DEFAULT_TTL_DAYS):
    """
    전체 임시 디렉토리의 TTL 초과 파일 정리 (배치 작업용)

    Args:
        base_dir: 기본 업로드 디렉토리
        ttl_days: 파일 보관 기간 (일)
    """
    temp_dir = Path(base_dir)
    if not temp_dir.exists():
        return

    current_time = time.time()
    ttl_seconds = ttl_days * 24 * 60 * 60
    deleted_count = 0

    for user_dir in temp_dir.iterdir():
        if not user_dir.is_dir():
            continue

        for file in user_dir.glob("*"):
            if not file.is_file():
                continue
            try:
                file_age = current_time - file.stat().st_mtime
                if file_age > ttl_seconds:
                    file.unlink()
                    deleted_count += 1
            except OSError:
                pass

        # 빈 사용자 디렉토리 삭제
        try:
            if user_dir.exists() and not any(user_dir.iterdir()):
                user_dir.rmdir()
                logger.info(f"Removed empty user directory: {user_dir}")
        except OSError:
            pass

    if deleted_count > 0:
        logger.info(f"Batch cleanup completed: {deleted_count} files deleted")


def copy_to_temp(
    source_path: str,
    user_id: str = "cli_user",
    base_dir: str = "temp"
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    외부 파일을 temp 디렉토리로 복사 (CLI용)

    Args:
        source_path: 원본 파일 경로
        user_id: 사용자 ID (CLI는 기본값 사용)
        base_dir: 기본 업로드 디렉토리

    Returns:
        (success: bool, temp_path: Optional[str], error: Optional[str])
    """
    import shutil

    source = Path(source_path)

    # 원본 파일 존재 확인
    if not source.exists():
        return False, None, f"파일을 찾을 수 없습니다: {source_path}"

    if not source.is_file():
        return False, None, f"유효한 파일이 아닙니다: {source_path}"

    # 확장자 검증
    ext = source.suffix.lower()
    all_allowed = ALLOWED_EXTENSIONS_EXCEL + ALLOWED_EXTENSIONS_PDF
    if ext not in all_allowed:
        return False, None, f"허용되지 않은 파일 형식입니다. 허용: {', '.join(all_allowed)}"

    # 크기 검증
    file_size = source.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        return False, None, f"파일 크기가 너무 큽니다. 최대: {MAX_FILE_SIZE_MB}MB"

    # temp 경로 생성
    temp_path = get_secure_upload_path(user_id, source.name, base_dir)

    try:
        shutil.copy2(source, temp_path)
        logger.info(f"File copied to temp: {source} -> {temp_path}")
        return True, str(temp_path), None
    except (OSError, IOError) as e:
        logger.error(f"Failed to copy file to temp: {e}")
        return False, None, f"파일 복사 실패: {e}"
