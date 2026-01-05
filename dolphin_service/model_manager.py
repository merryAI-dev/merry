"""
Dolphin Model Manager

싱글톤 패턴으로 모델을 관리하고, CPU 환경에서의 메모리 최적화를 처리합니다.
"""

import logging
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from .config import DOLPHIN_CONFIG, get_model_path

logger = logging.getLogger(__name__)


class DolphinModelManager:
    """Dolphin 모델 싱글톤 관리자

    - Lazy loading: 첫 사용 시에만 모델 로드
    - 메모리 체크: 로드 전 가용 메모리 확인
    - 스레드 안전: Lock으로 동시 로딩 방지
    """

    _instance: Optional["DolphinModelManager"] = None
    _lock = threading.Lock()
    _model: Optional[Dict[str, Any]] = None
    _is_loaded: bool = False

    def __new__(cls) -> "DolphinModelManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "DolphinModelManager":
        """싱글톤 인스턴스 반환"""
        return cls()

    @classmethod
    def is_model_loaded(cls) -> bool:
        """모델 로드 여부 확인"""
        return cls._is_loaded

    @classmethod
    def get_model(cls) -> Dict[str, Any]:
        """모델 반환 (필요시 로드)

        Returns:
            {"model": model, "processor": processor}

        Raises:
            MemoryError: 메모리 부족
            FileNotFoundError: 모델 파일 없음
            ImportError: 필수 라이브러리 없음
        """
        instance = cls.get_instance()

        if cls._model is not None:
            return cls._model

        with cls._lock:
            # Double-check locking
            if cls._model is not None:
                return cls._model

            cls._model = instance._load_model()
            cls._is_loaded = True
            return cls._model

    def _load_model(self) -> Dict[str, Any]:
        """모델 로드 (내부 사용)"""
        # 1. 메모리 체크
        self._check_memory()

        # 2. 모델 경로 확인
        model_path = get_model_path()
        if not model_path.exists():
            # HuggingFace에서 직접 로드 시도
            logger.info(f"로컬 모델 없음, HuggingFace에서 로드: {DOLPHIN_CONFIG['model_id']}")
            model_path = DOLPHIN_CONFIG["model_id"]
        else:
            logger.info(f"로컬 모델 로드: {model_path}")

        # 3. 필수 라이브러리 임포트
        try:
            import torch
            from transformers import AutoModelForVision2Seq, AutoProcessor
        except ImportError as e:
            raise ImportError(
                f"Dolphin 모델 로드에 필요한 라이브러리가 없습니다: {e}\n"
                "pip install torch transformers accelerate"
            ) from e

        # 4. CPU 스레드 설정
        torch.set_num_threads(DOLPHIN_CONFIG["num_threads"])
        logger.info(f"CPU 스레드 수: {DOLPHIN_CONFIG['num_threads']}")

        # 5. 모델 로드
        try:
            logger.info("Dolphin 모델 로딩 시작...")

            processor = AutoProcessor.from_pretrained(
                str(model_path),
                trust_remote_code=True,
            )

            model = AutoModelForVision2Seq.from_pretrained(
                str(model_path),
                torch_dtype=torch.float32,
                device_map="cpu",
                low_cpu_mem_usage=DOLPHIN_CONFIG["low_memory_mode"],
                trust_remote_code=True,
            )

            # 평가 모드 설정
            model.eval()

            logger.info("Dolphin 모델 로딩 완료")

            return {
                "model": model,
                "processor": processor,
                "model_path": str(model_path),
            }

        except Exception as e:
            logger.error(f"모델 로드 실패: {e}")
            raise

    def _check_memory(self) -> None:
        """가용 메모리 확인

        Raises:
            MemoryError: 메모리 부족
        """
        try:
            import psutil

            available_gb = psutil.virtual_memory().available / (1024**3)
            min_required = DOLPHIN_CONFIG["min_memory_gb"]

            logger.info(f"가용 메모리: {available_gb:.1f}GB (최소 필요: {min_required}GB)")

            if available_gb < min_required:
                raise MemoryError(
                    f"Dolphin 모델 로딩에 최소 {min_required}GB RAM이 필요합니다. "
                    f"현재 가용 메모리: {available_gb:.1f}GB. "
                    "다른 프로그램을 종료하거나 max_pages를 줄여주세요."
                )

        except ImportError:
            logger.warning("psutil이 없어 메모리 체크를 건너뜁니다")

    @classmethod
    def unload_model(cls) -> None:
        """모델 언로드 (메모리 해제)"""
        with cls._lock:
            if cls._model is not None:
                logger.info("Dolphin 모델 언로드 중...")

                try:
                    import gc

                    import torch

                    del cls._model
                    cls._model = None
                    cls._is_loaded = False

                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()

                    logger.info("모델 언로드 완료")

                except Exception as e:
                    logger.error(f"모델 언로드 실패: {e}")

    @classmethod
    def get_model_info(cls) -> Dict[str, Any]:
        """모델 정보 반환"""
        return {
            "is_loaded": cls._is_loaded,
            "model_id": DOLPHIN_CONFIG["model_id"],
            "model_path": str(get_model_path()),
            "device": DOLPHIN_CONFIG["device"],
            "num_threads": DOLPHIN_CONFIG["num_threads"],
        }


def check_dolphin_availability() -> tuple:
    """Dolphin 사용 가능 여부 확인

    Returns:
        (is_available: bool, reason: str or None)
    """
    errors = []

    # 1. 필수 라이브러리 확인
    try:
        import torch
    except ImportError:
        errors.append("torch 라이브러리 필요")

    try:
        import transformers
    except ImportError:
        errors.append("transformers 라이브러리 필요")

    # 2. 메모리 확인
    try:
        import psutil

        available_gb = psutil.virtual_memory().available / (1024**3)
        if available_gb < DOLPHIN_CONFIG["min_memory_gb"]:
            errors.append(f"메모리 부족 ({available_gb:.1f}GB < {DOLPHIN_CONFIG['min_memory_gb']}GB)")
    except ImportError:
        pass  # psutil 없으면 건너뜀

    # 3. 모델 경로 확인 (선택적)
    model_path = get_model_path()
    if not model_path.exists():
        # HuggingFace에서 다운로드 가능하므로 경고만
        logger.info(f"로컬 모델 없음: {model_path}")

    if errors:
        return False, "; ".join(errors)
    return True, None
