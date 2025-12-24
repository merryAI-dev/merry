"""
Naver CLOVA Speech helpers (STT / TTS)
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Dict, Optional


CLOVA_STT_ENDPOINT = "https://naveropenapi.apigw.ntruss.com/recog/v1/stt"
CLOVA_TTS_ENDPOINT = "https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts"


def _get_clova_credentials() -> Dict[str, str]:
    """Read CLOVA credentials from environment."""
    return {
        "key_id": os.getenv("NAVER_CLOUD_API_KEY_ID", "").strip(),
        "key": os.getenv("NAVER_CLOUD_API_KEY", "").strip(),
    }


def clova_credentials_present() -> bool:
    creds = _get_clova_credentials()
    return bool(creds["key_id"] and creds["key"])


def _build_headers() -> Dict[str, str]:
    creds = _get_clova_credentials()
    if not creds["key_id"] or not creds["key"]:
        raise ValueError("NAVER_CLOUD_API_KEY_ID/NAVER_CLOUD_API_KEY가 필요합니다.")
    return {
        "X-NCP-APIGW-API-KEY-ID": creds["key_id"],
        "X-NCP-APIGW-API-KEY": creds["key"],
    }


def clova_stt(audio_bytes: bytes, lang: str = "Kor") -> Dict[str, Optional[str]]:
    """Run CLOVA Speech Recognition (STT).

    Args:
        audio_bytes: raw audio bytes (WAV recommended)
        lang: language code (Kor, Jpn, Eng, Chn)
    """
    if not audio_bytes:
        return {"success": False, "error": "오디오 데이터가 비어 있습니다.", "text": None}

    try:
        headers = _build_headers()
    except ValueError as exc:
        return {"success": False, "error": str(exc), "text": None}

    query = urllib.parse.urlencode({"lang": lang})
    url = f"{CLOVA_STT_ENDPOINT}?{query}"

    req = urllib.request.Request(url, data=audio_bytes, method="POST")
    req.add_header("Content-Type", "application/octet-stream")
    for key, value in headers.items():
        req.add_header(key, value)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
        data = json.loads(body)
        return {"success": True, "text": data.get("text"), "error": None}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return {"success": False, "error": f"HTTP {exc.code}: {detail}", "text": None}
    except Exception as exc:
        return {"success": False, "error": str(exc), "text": None}


def clova_tts(
    text: str,
    speaker: str = "nara",
    speed: int = 0,
    volume: int = 0,
    pitch: int = 0,
    format: str = "mp3",
) -> Dict[str, Optional[bytes]]:
    """Run CLOVA Voice Premium (TTS).

    Args:
        text: text to synthesize
        speaker: voice name (Naver CLOVA Voice)
        speed: -5 to +5
        volume: -5 to +5
        pitch: -5 to +5
        format: mp3 or wav
    """
    audio_format = "audio/mpeg" if format == "mp3" else f"audio/{format}"

    if not text:
        return {"success": False, "error": "텍스트가 비어 있습니다.", "audio": None, "format": audio_format}

    try:
        headers = _build_headers()
    except ValueError as exc:
        return {"success": False, "error": str(exc), "audio": None, "format": audio_format}

    payload = {
        "speaker": speaker,
        "speed": str(speed),
        "volume": str(volume),
        "pitch": str(pitch),
        "format": format,
        "text": text,
    }

    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(CLOVA_TTS_ENDPOINT, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
    for key, value in headers.items():
        req.add_header(key, value)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            audio_bytes = resp.read()
        return {"success": True, "audio": audio_bytes, "error": None, "format": audio_format}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return {"success": False, "error": f"HTTP {exc.code}: {detail}", "audio": None, "format": audio_format}
    except Exception as exc:
        return {"success": False, "error": str(exc), "audio": None, "format": audio_format}
