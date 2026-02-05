"""
세션 상태 초기화 및 설정 모듈
"""

import os
import streamlit as st
from PIL import Image
from pathlib import Path


# 이미지 경로
HEADER_IMAGE_PATH = "image-removebg-preview-5.png"
AVATAR_IMAGE_PATH = "image-removebg-preview-6.png"
USER_AVATAR_IMAGE_PATH = "Unknown.png"


def initialize_session_state():
    """앱 전역 세션 상태 초기화"""
    _apply_streamlit_secrets_to_env()
    defaults = {
        # 인증
        "user_email": None,
        "team_id": None,
        "team_label": "",
        "member_id": None,
        "member_name": "",
        "pending_session_id": None,

        # 에이전트 (공유)
        "agent": None,

        # Exit 프로젝션
        "exit_messages": [],
        "exit_user_info_collected": False,
        "exit_show_welcome": True,
        "projection_data": None,
        "exit_projection_assumptions": None,
        "uploaded_file_name": None,

        # Peer PER 분석
        "peer_messages": [],
        "peer_pdf_path": None,
        "peer_pdf_name": None,
        "peer_analysis_result": None,

        # 기업현황 진단시트
        "diagnosis_messages": [],
        "diagnosis_excel_path": None,
        "diagnosis_excel_name": None,
        "diagnosis_show_welcome": True,
        "diagnosis_analysis_result": None,
        "diagnosis_draft_path": None,
        "diagnosis_draft_progress": None,

        # 투자심사 보고서 (인수인의견 스타일)
        "report_messages": [],
        "report_file_path": None,
        "report_file_name": None,
        "report_files": [],
        "report_file_types": {},
        "report_doc_weights": {
            "IR": 0.4,
            "요약보고서": 0.3,
            "사업자등록증": 0.2,
            "기타": 0.1,
        },
        "report_uploaded_names": [],
        "report_draft_content": "",
        "report_show_welcome": True,
        "report_quick_command": None,
        "report_evidence": None,
        "report_deep_analysis": None,
        "report_deep_lens": None,
        "report_deep_scoring": None,
        "report_deep_hallucination": None,
        "report_deep_impact": None,
        "report_deep_logs": [],
        "report_deep_step": 0,
        "report_deep_error": None,
        "dart_api_key": "",
        "report_deep_mode": os.getenv("VC_REPORT_DEEP_MODE", "1").lower() not in ["0", "false", "no"],
        "report_deep_autorun": os.getenv("VC_REPORT_DEEP_AUTORUN", "1").lower() not in ["0", "false", "no"],
        "report_deep_multi": os.getenv("VC_MULTI_MODEL_OPINIONS", "1").lower() not in ["0", "false", "no"],

        # 파일 관리
        "uploaded_file_path": None,

        # 피드백
        "message_feedback": {},
        "feedback_input_visible": {},
        "feedback_text": {},

        # 홈 안내 챗봇
        "home_messages": [],
        "home_route_target": None,
        "home_route_label": "",
        "home_router_state": {"candidates": []},

        "sidebar_cache": {},

        "collab_brief": None,
        "collab_brief_error": None,
        "collab_brief_model": "claude-opus-4-5-20251101",
        "collab_last_move": "",

        # 펀드 대시보드
        "fund_selected_fund": "전체",
        "fund_selected_company": None,
        "fund_date_range": None,
        "fund_kpi_selected": "매출액 (백만원)",
        "fund_compare_companies": [],
        "fund_view_mode": "summary",

        "voice_messages": [],
        "voice_mode": "checkin",
        "voice_last_transcript": "",
        "voice_last_error": None,
        "voice_last_audio": None,
        "voice_last_audio_size": 0,
        "naver_api_key_id": "",
        "naver_api_key": "",
        "voice_speaker": "nara",
        "voice_stt_provider": "local_whisper",
        "voice_tts_provider": "local_mms",
        "voice_tts_enabled": False,
        "voice_auto_play": False,
        "voice_auto_play_index": None,
        "voice_audio_display_count": 1,
        "voice_prefer_clova": True,
        "voice_fast_mode": True,
        "voice_fast_model": "claude-3-5-haiku-20241022",
        "whisper_model": "small",
        "whisper_compute_type": "int8",
        "whisper_language": "ko",
        "piper_model_path": "",
        "piper_config_path": "",
        "piper_bin_path": "piper",
        "mms_model_id": "facebook/mms-tts-kss",
        "voice_refine_enabled": True,

        "contract_term_sheet_path": None,
        "contract_term_sheet_name": "",
        "contract_investment_path": None,
        "contract_investment_name": "",
        "contract_analysis": {},
        "contract_search_query": "",
        "contract_masking": True,
        "contract_cache_version": 0,
        "contract_ocr_mode": "자동(권장)",
        "contract_ocr_model": "claude-opus-4-5-20251101",
        "contract_ocr_refine": True,
        "contract_ocr_refine_model": "claude-opus-4-5-20251101",
        "contract_ocr_lang": "kor+eng",
        "contract_llm_opinion": True,
        "contract_opinion_model": "claude-opus-4-5-20251101",
        "contract_opinion_text": "",
        "contract_opinion_cache_key": "",
        "contract_analysis_mode": "빠른 스캔",
        "contract_ocr_strategy": "밀도 기반(빠름)",
        "contract_ocr_budget": 6,
        "contract_chat": [],
        "contract_show_file_names": False,

        # 스타트업 발굴 지원
        "discovery_messages": [],
        "discovery_pdf_paths": [],
        "discovery_interest_areas": [],
        "discovery_policy_analysis": None,
        "discovery_iris_mapping": None,
        "discovery_recommendations": None,
        "discovery_agent": None,
        "discovery_show_welcome": True,

        # 체크인 피드백 (각 페이지에서 수집)
        "checkin_feedbacks": [],  # [{page, title, content, created_at, status}]
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def add_checkin_feedback(page: str, title: str, content: str, status: str = "pending"):
    """체크인 피드백 추가"""
    from datetime import datetime

    if "checkin_feedbacks" not in st.session_state:
        st.session_state.checkin_feedbacks = []

    feedback = {
        "page": page,
        "title": title,
        "content": content,
        "created_at": datetime.now().isoformat(),
        "status": status  # pending, reviewed, actioned
    }
    st.session_state.checkin_feedbacks.append(feedback)
    return feedback


def get_checkin_feedbacks(page: str = None, status: str = None):
    """체크인 피드백 조회"""
    feedbacks = st.session_state.get("checkin_feedbacks", [])

    if page:
        feedbacks = [f for f in feedbacks if f.get("page") == page]
    if status:
        feedbacks = [f for f in feedbacks if f.get("status") == status]

    # 최신순 정렬
    feedbacks.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return feedbacks


def update_feedback_status(index: int, status: str):
    """피드백 상태 업데이트"""
    if "checkin_feedbacks" in st.session_state:
        if 0 <= index < len(st.session_state.checkin_feedbacks):
            st.session_state.checkin_feedbacks[index]["status"] = status


def render_feedback_input(page_name: str, page_title: str):
    """각 페이지에서 사용할 피드백 입력 UI"""
    with st.expander("💬 체크인 피드백 남기기", expanded=False):
        feedback_title = st.text_input(
            "제목",
            placeholder="예: PER 배수 조정 필요",
            key=f"feedback_title_{page_name}"
        )
        feedback_content = st.text_area(
            "내용",
            placeholder="피드백 내용을 입력하세요...",
            height=100,
            key=f"feedback_content_{page_name}"
        )

        if st.button("피드백 저장", key=f"feedback_save_{page_name}"):
            if feedback_title and feedback_content:
                add_checkin_feedback(
                    page=page_name,
                    title=feedback_title,
                    content=feedback_content
                )
                st.success("피드백이 저장되었습니다!")
                st.rerun()
            else:
                st.warning("제목과 내용을 모두 입력해주세요.")


def _apply_streamlit_secrets_to_env() -> None:
    """Expose Streamlit secrets as environment variables when available."""
    try:
        secrets = st.secrets
    except Exception:
        return
    if not secrets:
        return
    for key, value in secrets.items():
        if isinstance(value, (dict, list)):
            continue
        os.environ.setdefault(key, str(value))


@st.cache_resource(show_spinner=False)
def get_header_image() -> Image.Image:
    """헤더 이미지 로드"""
    with Image.open(HEADER_IMAGE_PATH) as img:
        return img.copy()


@st.cache_resource(show_spinner=False)
def get_avatar_image() -> Image.Image:
    """아바타 이미지 로드 및 변환 (빨간색 테마)"""
    with Image.open(AVATAR_IMAGE_PATH) as img:
        avatar_original = img.convert("RGBA")

    # 픽셀 데이터 가져오기
    pixels = avatar_original.load()
    width, height = avatar_original.size

    # 색상 변환: 빨간색 계열이 아닌 색상을 빨간색으로 변환
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]

            # 투명하지 않은 픽셀만 처리
            if a > 0:
                # 빨간색 계열이 아닌 색상을 빨간색으로 변환
                if r < 200 or g > 100 or b > 100:
                    brightness = (r + g + b) // 3
                    pixels[x, y] = (min(255, brightness + 100), brightness // 3, brightness // 3, a)

    # 흰색 배경 생성
    white_bg = Image.new('RGBA', avatar_original.size, (255, 255, 255, 255))
    # 흰색 배경 위에 아바타 합성
    avatar_image = Image.alpha_composite(white_bg, avatar_original)
    # RGB로 변환 (Streamlit에서 사용하기 위해)
    avatar_image = avatar_image.convert('RGB')

    return avatar_image


@st.cache_resource(show_spinner=False)
def get_user_avatar_image() -> Image.Image:
    """사용자 아바타 이미지 로드"""
    with Image.open(USER_AVATAR_IMAGE_PATH) as img:
        return img.convert("RGB")


def inject_custom_css():
    """빨간색 버튼 및 커스텀 스타일 주입"""
    st.markdown("""
    <style>
    /* Primary 버튼 빨간색 */
    .stButton > button[kind="primary"] {
        background-color: #dc2626 !important;
        border-color: #dc2626 !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #b91c1c !important;
        border-color: #b91c1c !important;
    }
    .stButton > button[kind="primary"]:active {
        background-color: #991b1b !important;
        border-color: #991b1b !important;
    }

    /* Secondary 버튼 */
    .stButton > button[kind="secondary"] {
        border-color: #dc2626 !important;
        color: #dc2626 !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background-color: #fef2f2 !important;
        border-color: #b91c1c !important;
        color: #b91c1c !important;
    }
    </style>
    """, unsafe_allow_html=True)


def initialize_agent():
    """VCAgent 초기화 - 사용자 API 키 및 user_id 사용"""
    if st.session_state.agent is None:
        try:
            from agent.vc_agent import VCAgent
            from shared.auth import get_user_api_key, get_user_id
            from shared.session_utils import load_session_by_id

            # 사용자가 입력한 API 키 및 user_id 사용
            user_api_key = get_user_api_key()
            user_id = get_user_id()
            member_name = st.session_state.get("member_name") or None
            team_id = st.session_state.get("team_id") or user_id

            if user_api_key:
                st.session_state.agent = VCAgent(
                    api_key=user_api_key,
                    user_id=user_id,
                    member_name=member_name,
                    team_id=team_id
                )
            else:
                # 환경변수 fallback (로컬 개발용)
                st.session_state.agent = VCAgent(user_id=user_id, member_name=member_name, team_id=team_id)

            pending_session_id = st.session_state.get("pending_session_id")
            if pending_session_id:
                load_session_by_id(st.session_state.agent, pending_session_id)
                st.session_state.pending_session_id = None
        except ValueError as e:
            st.error(f"{str(e)}")
            st.info("API 키가 필요합니다.")
            st.stop()
