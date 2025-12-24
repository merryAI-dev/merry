"""
Local speech helpers (STT/TTS) for CPU-first deployments.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
from functools import lru_cache
from typing import Dict, Optional


def _normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


@lru_cache(maxsize=2)
def _get_whisper_model(model_size_or_path: str, device: str, compute_type: str):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ImportError("faster-whisper가 필요합니다.") from exc

    return WhisperModel(
        model_size_or_path,
        device=device,
        compute_type=compute_type,
    )


def local_stt_faster_whisper(
    audio_bytes: bytes,
    model_size_or_path: str = "small",
    language: str = "ko",
    device: str = "cpu",
    compute_type: str = "int8",
) -> Dict[str, Optional[str]]:
    if not audio_bytes:
        return {"success": False, "text": None, "error": "오디오 데이터가 비어 있습니다."}

    try:
        model = _get_whisper_model(model_size_or_path, device, compute_type)
    except ImportError as exc:
        return {"success": False, "text": None, "error": str(exc)}
    except Exception as exc:
        return {"success": False, "text": None, "error": f"모델 로드 실패: {exc}"}

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_file.write(audio_bytes)
        temp_path = temp_file.name

    try:
        segments, _info = model.transcribe(
            temp_path,
            language=language,
            beam_size=5,
        )
        text = " ".join(_normalize_text(seg.text) for seg in segments if seg.text)
        return {"success": True, "text": text, "error": None}
    except Exception as exc:
        return {"success": False, "text": None, "error": f"STT 실패: {exc}"}
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


def _resolve_piper_binary(piper_bin: str) -> Optional[str]:
    if not piper_bin:
        return None
    if os.path.isfile(piper_bin) and os.access(piper_bin, os.X_OK):
        return piper_bin
    resolved = shutil.which(piper_bin)
    return resolved


def local_tts_piper(
    text: str,
    model_path: str,
    config_path: Optional[str] = None,
    piper_bin: str = "piper",
) -> Dict[str, Optional[bytes]]:
    text = _normalize_text(text)
    if not text:
        return {"success": False, "audio": None, "error": "텍스트가 비어 있습니다.", "format": "audio/wav"}

    if not model_path:
        return {
            "success": False,
            "audio": None,
            "error": "Piper 모델 경로가 필요합니다.",
            "format": "audio/wav",
        }

    if not os.path.isfile(model_path):
        return {
            "success": False,
            "audio": None,
            "error": f"모델 파일이 없습니다: {model_path}",
            "format": "audio/wav",
        }

    piper_exec = _resolve_piper_binary(piper_bin)
    if not piper_exec:
        return {
            "success": False,
            "audio": None,
            "error": "piper 실행 파일을 찾을 수 없습니다.",
            "format": "audio/wav",
        }

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as out_file:
        out_path = out_file.name

    cmd = [piper_exec, "--model", model_path, "--output_file", out_path]
    if config_path:
        cmd.extend(["--config", config_path])

    try:
        subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        with open(out_path, "rb") as f:
            audio_bytes = f.read()
        return {"success": True, "audio": audio_bytes, "error": None, "format": "audio/wav"}
    except subprocess.CalledProcessError as exc:
        err = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else str(exc)
        return {"success": False, "audio": None, "error": f"TTS 실패: {err}", "format": "audio/wav"}
    except Exception as exc:
        return {"success": False, "audio": None, "error": f"TTS 실패: {exc}", "format": "audio/wav"}
    finally:
        try:
            os.remove(out_path)
        except OSError:
            pass


@lru_cache(maxsize=2)
def _get_mms_pipeline(model_id: str):
    try:
        from transformers import pipeline
    except ImportError as exc:
        raise ImportError("transformers가 필요합니다.") from exc

    return pipeline("text-to-speech", model=model_id, device=-1)


def local_tts_mms(
    text: str,
    model_id: str = "facebook/mms-tts-kss",
) -> Dict[str, Optional[bytes]]:
    text = _normalize_text(text)
    if not text:
        return {"success": False, "audio": None, "error": "텍스트가 비어 있습니다.", "format": "audio/wav"}

    try:
        tts_pipeline = _get_mms_pipeline(model_id)
    except ImportError as exc:
        return {"success": False, "audio": None, "error": str(exc), "format": "audio/wav"}
    except Exception as exc:
        return {"success": False, "audio": None, "error": f"모델 로드 실패: {exc}", "format": "audio/wav"}

    try:
        result = tts_pipeline(text)
        audio = result.get("audio")
        sample_rate = result.get("sampling_rate", 22050)
        if audio is None:
            return {"success": False, "audio": None, "error": "TTS 출력이 비었습니다.", "format": "audio/wav"}

        try:
            import soundfile as sf
        except ImportError as exc:
            return {"success": False, "audio": None, "error": "soundfile이 필요합니다.", "format": "audio/wav"}

        buffer = io.BytesIO()
        sf.write(buffer, audio, sample_rate, format="WAV")
        return {"success": True, "audio": buffer.getvalue(), "error": None, "format": "audio/wav"}
    except Exception as exc:
        return {"success": False, "audio": None, "error": f"TTS 실패: {exc}", "format": "audio/wav"}
