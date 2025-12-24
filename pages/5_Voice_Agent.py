"""
Voice Agent Page (Naver CLOVA STT/TTS)
"""

from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

import streamlit as st

from shared.auth import check_authentication, get_user_id
from shared.config import initialize_agent, initialize_session_state, inject_custom_css
from shared.clova_speech import clova_credentials_present, clova_stt, clova_tts
from shared.local_speech import local_stt_faster_whisper, local_tts_mms, local_tts_piper
try:
    from shared.voice_logs import (
        append_checkin_summary,
        append_voice_log,
        build_checkin_context_text,
        build_checkin_summaries_context_text,
        build_checkin_summary_text,
        get_checkin_context_all,
        get_checkin_context_days,
        get_checkin_context,
        get_latest_checkin,
        get_latest_checkin_summary,
        get_checkin_summaries,
    )
    VOICE_LOGS_IMPORT_ERROR = None
except Exception as exc:
    VOICE_LOGS_IMPORT_ERROR = exc

    def _empty_context(*_args, **_kwargs):
        return {"start": "", "end": "", "voice_logs": [], "chat_messages": []}

    def _empty_text(*_args, **_kwargs):
        return ""

    def _empty_list(*_args, **_kwargs):
        return []

    def _noop(*_args, **_kwargs):
        return None

    append_checkin_summary = _noop
    append_voice_log = _noop
    build_checkin_context_text = _empty_text
    build_checkin_summaries_context_text = _empty_text
    build_checkin_summary_text = _empty_text
    get_checkin_context_all = _empty_context
    get_checkin_context_days = _empty_context
    get_checkin_context = _empty_context
    get_latest_checkin = _noop
    get_latest_checkin_summary = _noop
    get_checkin_summaries = _empty_list
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

if VOICE_LOGS_IMPORT_ERROR:
    st.error(
        "voice_logs 로드 실패: "
        f"{type(VOICE_LOGS_IMPORT_ERROR).__name__}: {VOICE_LOGS_IMPORT_ERROR}"
    )
    st.caption("Streamlit Cloud 로그에서 상세 원인을 확인해주세요.")

# Defaults for local STT
if not st.session_state.whisper_model:
    st.session_state.whisper_model = "small"
if not st.session_state.whisper_language:
    st.session_state.whisper_language = "ko"
if not st.session_state.mms_model_id:
    st.session_state.mms_model_id = "facebook/mms-tts-kss"


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
        audio_file = st.audio_input("음성 입력", key="voice_audio_input")
    else:
        audio_file = st.file_uploader(
            "오디오 업로드 (WAV/MP3)",
            type=["wav", "mp3"],
            key="voice_audio_upload",
        )

    if audio_file:
        audio_bytes = audio_file.read()
        mime = getattr(audio_file, "type", None)

    if audio_bytes is not None:
        st.session_state.voice_last_audio_size = len(audio_bytes)

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
    if clova_credentials_present() and st.session_state.voice_tts_provider != "clova":
        st.caption("Streamlit 배포에서는 CLOVA TTS가 안정적입니다.")

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
    st.checkbox(
        "음성 입력 정제 (Claude)",
        value=st.session_state.voice_refine_enabled,
        key="voice_refine_enabled",
        help="STT 결과를 Claude로 정제해서 대화 입력에 사용합니다.",
    )
    st.caption("브라우저에서 재생 버튼을 눌러야 음성이 출력됩니다.")
    with st.expander("입력 상태", expanded=False):
        last_audio_size = st.session_state.get("voice_last_audio_size")
        if last_audio_size:
            st.caption(f"마지막 오디오 크기: {last_audio_size} bytes")
        else:
            st.caption("최근 오디오 입력이 없습니다.")

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
context_scope = st.selectbox(
    "컨텍스트 범위",
    options=["어제", "최근 7일", "전체 로그"],
    index=2,
)
use_full_context = False
if context_scope == "전체 로그":
    use_full_context = st.checkbox(
        "모든 로그 세션 사용 (제한 없음)",
        value=True,
        help="Supabase 전체 로그를 컨텍스트로 사용합니다. 데이터가 많으면 느릴 수 있습니다.",
    )

context_limit = st.slider(
    "컨텍스트 최대 항목",
    min_value=10,
    max_value=200,
    value=60,
    step=10,
    disabled=use_full_context,
)
fetch_limit = None if use_full_context else context_limit
context_item_limit = None if use_full_context else context_limit
summary_limit = None if use_full_context else 15

if context_scope == "어제":
    checkin_context = get_checkin_context(user_id, day_offset=1, limit=context_limit)
elif context_scope == "최근 7일":
    checkin_context = get_checkin_context_days(user_id, days=7, limit=context_limit)
else:
    checkin_context = get_checkin_context_all(user_id, limit=fetch_limit)

preview_items = min(context_limit, 8)
checkin_context_text = build_checkin_context_text(checkin_context, max_items=context_item_limit)
checkin_context_preview = build_checkin_context_text(checkin_context, max_items=preview_items)
checkin_summary = get_latest_checkin_summary(user_id, day_offset=1)
checkin_summary_text = build_checkin_summary_text(checkin_summary) if checkin_summary else ""
checkin_summaries = get_checkin_summaries(user_id, limit=summary_limit)
checkin_summaries_text = build_checkin_summaries_context_text(
    checkin_summaries,
    max_items=None if use_full_context else 8,
)
checkin_summaries_preview = build_checkin_summaries_context_text(checkin_summaries, max_items=5)

context_payload = ""
context_display = ""
if context_scope == "전체 로그":
    if checkin_summaries_text:
        context_payload = f"[최근 체크인 요약]\n{checkin_summaries_text}\n\n[최근 로그]\n{checkin_context_text}"
    else:
        context_payload = checkin_context_text

    if checkin_summaries_preview:
        context_display = f"[최근 체크인 요약]\n{checkin_summaries_preview}\n\n[최근 로그]\n{checkin_context_preview}"
    else:
        context_display = checkin_context_preview
else:
    context_payload = checkin_summary_text or checkin_context_text
    context_display = checkin_summary_text or checkin_context_preview

voice_log_count = len(checkin_context.get("voice_logs", []))
chat_log_count = len(checkin_context.get("chat_messages", []))
summary_count = len(checkin_summaries) if checkin_summaries else 0

if context_display:
    st.info(
        "컨텍스트 로드 완료 · "
        f"체크인 요약 {summary_count}개, "
        f"음성 로그 {voice_log_count}개, "
        f"채팅 로그 {chat_log_count}개"
    )
    with st.expander("컨텍스트 미리보기", expanded=False):
        st.write(context_display)
    if context_payload and context_payload != context_display:
        with st.expander("컨텍스트 전체 보기", expanded=False):
            st.caption("전체 로그가 많으면 느릴 수 있습니다.")
            st.write(context_payload)
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
        if msg.get("raw_transcript"):
            st.caption(f"STT 원문: {msg['raw_transcript']}")
        if msg.get("refined_text"):
            st.caption("정제 텍스트:")
        st.write(msg["content"])
        if msg.get("tts_note"):
            st.caption(msg["tts_note"])
        if msg.get("tts_error"):
            st.caption(f"TTS 오류: {msg['tts_error']}")
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
            model_size_or_path=(st.session_state.whisper_model or "small").strip(),
            language=(st.session_state.whisper_language or "ko").strip(),
            compute_type=st.session_state.whisper_compute_type,
        )
    else:
        stt_result = clova_stt(audio_bytes)

    if not stt_result.get("success"):
        st.session_state.voice_last_error = stt_result.get("error")
        return None, None

    transcript = (stt_result.get("text") or "").strip()
    return transcript, transcript


def _run_tts_with_fallback(
    text: str,
    speed: int,
    volume: int,
    pitch: int,
) -> Dict[str, Optional[bytes]]:
    providers = [st.session_state.voice_tts_provider]
    if st.session_state.voice_tts_provider in ("local_mms", "local_piper") and clova_credentials_present():
        providers.append("clova")

    errors = []
    for provider in providers:
        if provider == "local_mms":
            model_id = (st.session_state.mms_model_id or "facebook/mms-tts-kss").strip()
            tts_result = local_tts_mms(
                text,
                model_id=model_id,
            )
        elif provider == "local_piper":
            tts_result = local_tts_piper(
                text,
                model_path=st.session_state.piper_model_path,
                config_path=st.session_state.piper_config_path or None,
                piper_bin=st.session_state.piper_bin_path,
            )
        else:
            tts_result = clova_tts(
                text,
                speaker=st.session_state.voice_speaker,
                speed=speed,
                volume=volume,
                pitch=pitch,
            )

        if tts_result.get("success"):
            tts_result["provider"] = provider
            if errors:
                tts_result["fallback_used"] = True
                tts_result["fallback_error"] = " / ".join(errors)
            return tts_result

        errors.append(f"{provider}: {tts_result.get('error') or 'unknown error'}")

    return {
        "success": False,
        "audio": None,
        "error": " / ".join(errors) if errors else "TTS 실패",
        "format": "audio/mpeg",
    }


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
        refined_text = None
        if transcript and st.session_state.voice_refine_enabled:
            refined_text = st.session_state.agent.refine_voice_input_sync(transcript)
            if refined_text:
                user_text = refined_text

        st.session_state.voice_last_transcript = transcript or ""
        st.session_state.voice_messages.append(
            {
                "role": "user",
                "content": user_text,
                "raw_transcript": transcript or None,
                "refined_text": refined_text or None,
            }
        )

        last_checkin_text = context_payload or checkin_summary_text or checkin_context_text or (
            last_checkin.get("assistant_text") if last_checkin else None
        )
        voice_mode = f"voice_{st.session_state.voice_mode}"
        response = st.session_state.agent.chat_sync(
            user_message=user_text,
            mode=voice_mode,
            allow_tools=False,
            context_text=last_checkin_text,
        )

        tts_result = _run_tts_with_fallback(
            response,
            speed=speed,
            volume=volume,
            pitch=pitch,
        )
        selected_provider = st.session_state.voice_tts_provider
        used_provider = tts_result.get("provider", selected_provider)
        audio_out = tts_result.get("audio") if tts_result.get("success") else None
        audio_format = tts_result.get("format") or ("audio/mpeg" if used_provider == "clova" else "audio/wav")
        tts_note = None
        tts_error = None
        if not tts_result.get("success"):
            tts_error = tts_result.get("error")
            st.session_state.voice_last_error = tts_error
        elif used_provider != selected_provider:
            tts_note = f"TTS 자동 전환: {selected_provider} → {used_provider}"

        st.session_state.voice_messages.append(
            {
                "role": "assistant",
                "content": response,
                "audio": audio_out,
                "audio_format": audio_format,
                "tts_note": tts_note,
                "tts_error": tts_error,
            }
        )

        session_id = st.session_state.agent.memory.session_id
        if st.session_state.voice_mode in ("checkin", "1on1"):
            summary = st.session_state.agent.summarize_checkin_sync(
                mode=st.session_state.voice_mode,
                context_text=context_payload or "",
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
