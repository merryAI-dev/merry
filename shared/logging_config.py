"""
프로덕션 레벨 로깅 설정
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    중앙 로깅 시스템 설정

    Args:
        log_level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR)

    Returns:
        설정된 로거
    """
    # 로그 디렉토리 생성
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # 루트 로거 설정
    logger = logging.getLogger("vc_agent")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 이미 핸들러가 있으면 스킵 (중복 방지)
    if logger.handlers:
        return logger

    # 포맷터
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 파일 핸들러 (일별 로그)
    log_filename = log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # 콘솔 핸들러 (WARNING 이상만)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    모듈별 로거 가져오기

    Args:
        name: 모듈 이름 (예: "supabase", "memory", "tools")

    Returns:
        모듈별 로거
    """
    return logging.getLogger(f"vc_agent.{name}")
