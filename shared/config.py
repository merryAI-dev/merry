"""
세션 상태 초기화 및 설정 모듈
"""

import streamlit as st
from PIL import Image
from pathlib import Path


# 이미지 경로
HEADER_IMAGE_PATH = "image-removebg-preview-5.png"
AVATAR_IMAGE_PATH = "image-removebg-preview-6.png"


def initialize_session_state():
    """앱 전역 세션 상태 초기화"""
    defaults = {
        # 인증
        "user_email": None,

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

        # 파일 관리
        "uploaded_file_path": None,

        # 피드백
        "message_feedback": {},
        "feedback_input_visible": {},
        "feedback_text": {},
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


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

            # 사용자가 입력한 API 키 및 user_id 사용
            user_api_key = get_user_api_key()
            user_id = get_user_id()

            if user_api_key:
                st.session_state.agent = VCAgent(
                    api_key=user_api_key,
                    user_id=user_id
                )
            else:
                # 환경변수 fallback (로컬 개발용)
                st.session_state.agent = VCAgent(user_id=user_id)
        except ValueError as e:
            st.error(f"{str(e)}")
            st.info("API 키가 필요합니다.")
            st.stop()
