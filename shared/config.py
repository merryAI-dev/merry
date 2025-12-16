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

        # Peer PER 분석
        "peer_messages": [],
        "peer_pdf_path": None,
        "peer_analysis_result": None,

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


def get_header_image() -> Image.Image:
    """헤더 이미지 로드"""
    return Image.open(HEADER_IMAGE_PATH)


def get_avatar_image() -> Image.Image:
    """아바타 이미지 로드 및 변환 (빨간색 테마)"""
    avatar_original = Image.open(AVATAR_IMAGE_PATH)

    # RGBA로 변환 (투명도 있는 경우)
    if avatar_original.mode != 'RGBA':
        avatar_original = avatar_original.convert('RGBA')

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


def initialize_agent():
    """VCAgent 초기화 - 사용자 API 키 사용"""
    if st.session_state.agent is None:
        try:
            from agent.vc_agent import VCAgent
            from shared.auth import get_user_api_key

            # 사용자가 입력한 API 키 사용
            user_api_key = get_user_api_key()
            if user_api_key:
                st.session_state.agent = VCAgent(api_key=user_api_key)
            else:
                # 환경변수 fallback (로컬 개발용)
                st.session_state.agent = VCAgent()
        except ValueError as e:
            st.error(f"{str(e)}")
            st.info("API 키가 필요합니다.")
            st.stop()
