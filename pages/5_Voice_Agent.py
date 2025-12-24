"""
Voice Agent Page (Naver CLOVA STT/TTS)
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

import streamlit as st

from shared.auth import check_authentication, get_user_id
from shared.config import initialize_agent, initialize_session_state, inject_custom_css
from shared.clova_speech import clova_credentials_present, clova_stt, clova_tts
from shared.local_speech import local_stt_faster_whisper, local_tts_mms, local_tts_piper
from shared.voice_logs import (
    append_checkin_summary,
    append_voice_log,
    build_checkin_context_text,
    build_checkin_summary_text,
    get_checkin_context,
    get_latest_checkin,
    get_latest_checkin_summary,
)
# ========================================
# Page setup
# ========================================
st.set_page_config(
    page_title="Voice Agent | VC 투자 분석",
    page_icon="VC",
    layout="wide",
)

initialize_session_state()
check_authentication()
initialize_agent()
inject_custom_css()


def _apply_naverc_key_from_sidebar():
    key_id = st.session_state.get("naver_api_key_id", "").strip()
    key = st.session_state.get("naver_api_key", "").strip()
    if key_id and key:
        os.environ["NAVER_CLOUD_API_KEY_ID"] = key_id
        os.environ["NAVER_CLOUD_API_KEY"] = key


def _capture_audio() -> Tuple[Optional[bytes], Optional[str]]:
    """Capture audio using built-in audio_input or file upload fallback."""
    audio_bytes = None
    mime = None

    if hasattr(st, "audio_input"):
        audio_file = st.audio_input("음성 입력")
    else:
        audio_file = st.file_uploader("오디오 업로드 (WAV/MP3)", type=["wav", "mp3"])

    if audio_file:
        audio_bytes = audio_file.read()
        mime = getattr(audio_file, "type", None)

    return audio_bytes, mime


def _reset_voice_session():
    st.session_state.voice_messages = []
    st.session_state.voice_last_transcript = ""
    st.session_state.voice_last_error = None
    if st.session_state.agent:
        st.session_state.agent.voice_conversation_history = []


# ========================================
# Sidebar (keys + voice controls)
# ========================================
with st.sidebar:
    st.markdown("### Naver CLOVA 설정")
    st.caption("API 키는 세션에만 적용됩니다.")

    st.text_input(
        "API Key ID",
        type="password",
        key="naver_api_key_id",
        placeholder="X-NCP-APIGW-API-KEY-ID",
    )
    st.text_input(
        "API Key",
        type="password",
        key="naver_api_key",
        placeholder="X-NCP-APIGW-API-KEY",
    )
    _apply_naverc_key_from_sidebar()

    if clova_credentials_present():
        st.success("CLOVA 키가 적용되었습니다.")
    else:
        st.warning("CLOVA 키가 필요합니다.")

    st.divider()
    st.markdown("### 음성 엔진")
    st.selectbox(
        "STT Provider",
        options=["local_whisper", "clova"],
        index=0 if st.session_state.voice_stt_provider == "local_whisper" else 1,
        key="voice_stt_provider",
    )
    st.selectbox(
        "TTS Provider",
        options=["local_mms", "local_piper", "clova"],
        index=0
        if st.session_state.voice_tts_provider == "local_mms"
        else 1
        if st.session_state.voice_tts_provider == "local_piper"
        else 2,
        key="voice_tts_provider",
    )

    if st.session_state.voice_stt_provider == "local_whisper":
        st.text_input(
            "Whisper Model (size or path)",
            key="whisper_model",
            placeholder="small | medium | /path/to/model",
        )
        st.selectbox(
            "Compute Type",
            options=["int8", "int8_float16", "float16", "float32"],
            index=0,
            key="whisper_compute_type",
        )
        st.text_input(
            "Language",
            key="whisper_language",
            placeholder="ko",
        )
        st.caption("faster-whisper와 ffmpeg 필요")

    if st.session_state.voice_tts_provider == "local_mms":
        st.text_input(
            "MMS Model ID",
            key="mms_model_id",
            placeholder="facebook/mms-tts-kss",
        )
        st.caption("transformers + torch + soundfile 필요")

    if st.session_state.voice_tts_provider == "local_piper":
        st.text_input(
            "Piper Model Path (.onnx)",
            key="piper_model_path",
            placeholder="/path/to/ko_KR.onnx",
        )
        st.text_input(
            "Piper Config Path (.json, optional)",
            key="piper_config_path",
            placeholder="/path/to/ko_KR.json",
        )
        st.text_input(
            "Piper Binary",
            key="piper_bin_path",
            placeholder="piper",
        )
        st.caption("piper 바이너리 필요")

    st.divider()
    st.markdown("### TTS 설정")
    speaker = st.text_input("Speaker", value=st.session_state.get("voice_speaker", "nara"))
    speed = st.slider("Speed", min_value=-5, max_value=5, value=0)
    pitch = st.slider("Pitch", min_value=-5, max_value=5, value=0)
    volume = st.slider("Volume", min_value=-5, max_value=5, value=0)

    st.session_state.voice_speaker = speaker

    st.divider()
    if st.button("대화 초기화", type="secondary", use_container_width=True):
        _reset_voice_session()
        st.rerun()


# ========================================
# Main UI
# ========================================
st.markdown("# Voice Agent")
st.caption("로컬 STT/TTS 또는 Naver CLOVA로 음성 대화를 제공합니다.")

user_id = get_user_id()
last_checkin = get_latest_checkin(user_id)
checkin_context = get_checkin_context(user_id, day_offset=1, limit=20)
checkin_context_text = build_checkin_context_text(checkin_context, max_items=6)
checkin_summary = get_latest_checkin_summary(user_id, day_offset=1)
checkin_summary_text = build_checkin_summary_text(checkin_summary) if checkin_summary else ""

if checkin_summary_text:
    st.info(f"어제 체크인 요약 (Supabase):\n\n{checkin_summary_text}")
elif checkin_context_text:
    st.info(f"어제 기록 요약 (Supabase):\n\n{checkin_context_text}")
elif last_checkin:
    st.info(
        f"최근 체크인: {last_checkin.get('timestamp', '')}\n\n"
        f"{last_checkin.get('assistant_text', '')[:200]}..."
    )

st.divider()

mode = st.radio(
    "모드 선택",
    options=[
        ("checkin", "데일리 체크인"),
        ("1on1", "원온원"),
        ("chat", "자유 대화"),
    ],
    format_func=lambda x: x[1],
    horizontal=True,
)
st.session_state.voice_mode = mode[0]

checkin_seed = st.button("체크인 시작", type="primary", use_container_width=False)

# Chat history
for msg in st.session_state.voice_messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("audio"):
            st.audio(msg["audio"], format=msg.get("audio_format", "audio/mp3"))

st.divider()

col1, col2 = st.columns([2, 1])

with col1:
    audio_bytes, _mime = _capture_audio()
    text_input = st.text_input("텍스트 입력 (선택)", key="voice_text_input", placeholder="말하지 않고 텍스트로 입력할 수 있습니다.")

with col2:
    send_clicked = st.button("전송", type="primary", use_container_width=True)


def _resolve_user_text() -> Tuple[Optional[str], Optional[str]]:
    """Return (final_text, transcript) where transcript is raw STT output."""
    if text_input.strip():
        return text_input.strip(), None

    if not audio_bytes:
        return None, None

    if st.session_state.voice_stt_provider == "local_whisper":
        stt_result = local_stt_faster_whisper(
            audio_bytes,
            model_size_or_path=st.session_state.whisper_model,
            language=st.session_state.whisper_language or "ko",
            compute_type=st.session_state.whisper_compute_type,
        )
    else:
        stt_result = clova_stt(audio_bytes)

    if not stt_result.get("success"):
        st.session_state.voice_last_error = stt_result.get("error")
        return None, None

    transcript = (stt_result.get("text") or "").strip()
    return transcript, transcript


if checkin_seed:
    seed = "오늘 체크인을 시작합니다. 어제 로그를 반영해 간단히 안부를 묻고, 학습과 감정 상태를 짧게 언급한 뒤, 오늘 목표를 2~4개 질문으로 확인해줘."
    send_clicked = True
    text_input = seed

if send_clicked:
    st.session_state.voice_last_error = None
    user_text, transcript = _resolve_user_text()

    if not user_text:
        st.warning("입력 또는 음성 녹음이 필요합니다.")
    else:
        st.session_state.voice_last_transcript = transcript or ""
        st.session_state.voice_messages.append({"role": "user", "content": user_text})

        last_checkin_text = checkin_summary_text or checkin_context_text or (
            last_checkin.get("assistant_text") if last_checkin else None
        )
        voice_mode = f"voice_{st.session_state.voice_mode}"
        response = st.session_state.agent.chat_sync(
            user_message=user_text,
            mode=voice_mode,
            allow_tools=False,
            context_text=last_checkin_text,
        )

        if st.session_state.voice_tts_provider == "local_mms":
            tts_result = local_tts_mms(
                response,
                model_id=st.session_state.mms_model_id,
            )
        elif st.session_state.voice_tts_provider == "local_piper":
            tts_result = local_tts_piper(
                response,
                model_path=st.session_state.piper_model_path,
                config_path=st.session_state.piper_config_path or None,
                piper_bin=st.session_state.piper_bin_path,
            )
        else:
            tts_result = clova_tts(
                response,
                speaker=st.session_state.voice_speaker,
                speed=speed,
                volume=volume,
                pitch=pitch,
            )

        audio_out = tts_result.get("audio") if tts_result.get("success") else None
        audio_format = tts_result.get("format", "audio/mp3")
        if not tts_result.get("success"):
            st.session_state.voice_last_error = tts_result.get("error")

        st.session_state.voice_messages.append(
            {
                "role": "assistant",
                "content": response,
                "audio": audio_out,
                "audio_format": audio_format,
            }
        )

        session_id = st.session_state.agent.memory.session_id
        if st.session_state.voice_mode in ("checkin", "1on1"):
            summary = st.session_state.agent.summarize_checkin_sync(
                mode=st.session_state.voice_mode,
                context_text=checkin_context_text or "",
            )
            append_checkin_summary(
                user_id,
                {
                    "mode": st.session_state.voice_mode,
                    "session_id": session_id,
                    "summary_date": checkin_context.get("start", "")[:10],
                    "summary_json": summary,
                },
            )
        append_voice_log(
            user_id,
            {
                "mode": st.session_state.voice_mode,
                "session_id": session_id,
                "user_text": user_text,
                "assistant_text": response,
                "transcript": transcript or "",
            },
        )

        st.rerun()


if st.session_state.voice_last_transcript:
    st.caption(f"STT 인식 결과: {st.session_state.voice_last_transcript}")

if st.session_state.voice_last_error:
    st.error(f"음성 처리 오류: {st.session_state.voice_last_error}")
