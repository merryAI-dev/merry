"""
VC Investment Agent - Web UI

실행: streamlit run app.py
"""

import streamlit as st
import asyncio
from pathlib import Path
import pandas as pd
import altair as alt
from PIL import Image

from agent.vc_agent import VCAgent

# 페이지 설정
st.set_page_config(
    page_title="VC 투자 분석 에이전트",
    page_icon="🔴",
    layout="wide",
)

# ========================================
# Google OAuth 인증 (Streamlit Cloud)
# ========================================
ALLOWED_DOMAIN = "mysc.co.kr"

def verify_email_domain(email: str) -> bool:
    """@mysc.co.kr 도메인 검증"""
    if not email:
        return False
    domain = email.split("@")[-1].lower()
    return domain == ALLOWED_DOMAIN

# Streamlit Cloud 인증 확인
user_email = None

# 방법 1: Streamlit Cloud SSO (experimental_user) - try/except로 안전하게 접근
try:
    if hasattr(st, 'experimental_user'):
        email = st.experimental_user.email
        if email:
            user_email = email
except (AttributeError, KeyError):
    pass

# 방법 2: secrets에 테스트용 이메일 설정
if not user_email:
    try:
        if 'test_email' in st.secrets:
            user_email = st.secrets['test_email']
    except Exception:
        pass

# 인증되지 않은 경우
if not user_email:
    st.image("image-removebg-preview-5.png", width=300)
    st.markdown("## VC 투자 분석 에이전트")
    st.warning("이 앱은 MYSC 임직원 전용입니다.")
    st.markdown("""
### Streamlit Cloud 인증 설정 필요

이 앱은 **Streamlit Cloud SSO**를 통해 Google 인증을 사용합니다.

**설정 방법:**
1. Streamlit Cloud → App Settings → Sharing
2. "Who can view this app" → **Only specific people**
3. Viewer emails에 `@mysc.co.kr` 도메인 사용자 추가
4. 또는 Secrets에 `test_email = "your@mysc.co.kr"` 추가하여 테스트
    """)
    st.stop()

# 도메인 검증
if not verify_email_domain(user_email):
    st.image("image-removebg-preview-5.png", width=300)
    st.error(f"접근이 거부되었습니다.")
    st.markdown(f"현재 로그인: **{user_email}**")
    st.markdown("@mysc.co.kr 도메인만 접근이 허용됩니다.")
    st.stop()

# 이미지 로드 (상대 경로 사용)
HEADER_IMAGE_PATH = "image-removebg-preview-5.png"
AVATAR_IMAGE_PATH = "image-removebg-preview-6.png"

header_image = Image.open(HEADER_IMAGE_PATH)

# 아바타 이미지를 흰색 배경, 빨간색 선으로 변환
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
            # (기존 색상이 진한 정도를 유지하면서 빨간색으로)
            if r < 200 or g > 100 or b > 100:  # 빨간색이 아닌 경우
                brightness = (r + g + b) // 3
                # 빨간색으로 변환 (밝기 유지)
                pixels[x, y] = (min(255, brightness + 100), brightness // 3, brightness // 3, a)

# 흰색 배경 생성
white_bg = Image.new('RGBA', avatar_original.size, (255, 255, 255, 255))
# 흰색 배경 위에 아바타 합성
avatar_image = Image.alpha_composite(white_bg, avatar_original)
# RGB로 변환 (Streamlit에서 사용하기 위해)
avatar_image = avatar_image.convert('RGB')

# 헤더
st.image(header_image, width=300)
st.markdown("Exit 프로젝션, PER 분석, IRR 계산을 메리와 대화하면서 수행하세요")

st.divider()

# 세션 상태 초기화
if "agent" not in st.session_state:
    try:
        st.session_state.agent = VCAgent()
    except ValueError as e:
        st.error(f"{str(e)}")
        st.info(".env 파일에 ANTHROPIC_API_KEY를 설정하세요")
        st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "projection_data" not in st.session_state:
    st.session_state.projection_data = None

if "message_feedback" not in st.session_state:
    st.session_state.message_feedback = {}

if "user_info_collected" not in st.session_state:
    st.session_state.user_info_collected = False

if "show_welcome" not in st.session_state:
    st.session_state.show_welcome = True

if "feedback_input_visible" not in st.session_state:
    st.session_state.feedback_input_visible = {}

if "feedback_text" not in st.session_state:
    st.session_state.feedback_text = {}

# Peer PER 분석 탭 관련 세션 상태
if "peer_messages" not in st.session_state:
    st.session_state.peer_messages = []

if "peer_analysis_result" not in st.session_state:
    st.session_state.peer_analysis_result = None

if "current_tab" not in st.session_state:
    st.session_state.current_tab = "Exit 프로젝션"

if "peer_pdf_path" not in st.session_state:
    st.session_state.peer_pdf_path = None

# 레이아웃: 왼쪽 사이드바 + 메인 영역
cols = st.columns([1, 3])

# ========================================
# 왼쪽 사이드바
# ========================================
with cols[0]:
    left_container = st.container(border=True, height=800)

    with left_container:
        # 로그인 정보
        st.markdown(f"**{user_email}**")
        # Streamlit Cloud SSO는 자동 로그아웃 지원하지 않음
        st.caption("Streamlit Cloud SSO 인증")

        st.divider()

        st.markdown("### 파일 업로드")

        uploaded_file = st.file_uploader(
            "투자검토 엑셀",
            type=["xlsx", "xls"],
            help="분석할 투자검토 엑셀 파일",
            label_visibility="collapsed"
        )

        if uploaded_file:
            # 임시 파일 저장
            temp_path = Path("temp") / uploaded_file.name
            temp_path.parent.mkdir(exist_ok=True)

            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            st.success(f"{uploaded_file.name}")
            st.session_state.uploaded_file_path = str(temp_path)

        st.divider()

        # 빠른 명령어
        st.markdown("### 빠른 명령어")

        if uploaded_file:
            if st.button("파일 분석", use_container_width=True, type="primary"):
                st.session_state.quick_command = f"{uploaded_file.name} 파일을 분석해줘"

            if st.button("Exit 프로젝션", use_container_width=True, type="primary"):
                st.session_state.quick_command = f"{uploaded_file.name}을 2030년 PER 10,20,30배로 분석하고 Exit 프로젝션 생성해줘"
        else:
            st.info("파일을 먼저 업로드하세요")

        st.divider()

        # 세션 관리
        st.markdown("### 세션 관리")

        # 메모리 정보
        if hasattr(st.session_state.agent, 'memory'):
            memory = st.session_state.agent.memory

            # 최근 세션 목록
            recent_sessions = memory.get_recent_sessions(limit=10)

            if recent_sessions:
                # 세션 선택 드롭다운 (현재 세션 정보 포함)
                current_user_info = memory.session_metadata.get("user_info", {})
                if current_user_info.get("nickname") and current_user_info.get("company"):
                    current_label = f"현재: {current_user_info['nickname']} - {current_user_info['company']}"
                else:
                    current_label = "현재 세션"

                session_options = [current_label] + [
                    f"{s['session_id']} ({s['message_count']}개 메시지)"
                    for s in recent_sessions
                    if s['session_id'] != memory.session_id
                ]

                selected_session = st.selectbox(
                    "세션 선택",
                    options=session_options,
                    key="session_selector",
                    label_visibility="collapsed"
                )

                # 세션 불러오기 버튼
                if not selected_session.startswith("현재"):
                    if st.button("세션 불러오기", use_container_width=True, type="primary", key="load_session"):
                        # 선택된 세션 ID 추출
                        selected_session_id = selected_session.split(" ")[0]

                        # 세션 데이터 로드
                        session_data = memory.load_session(selected_session_id)

                        if session_data:
                            # 메시지 복원
                            st.session_state.messages = []
                            for msg in session_data["messages"]:
                                st.session_state.messages.append({
                                    "role": msg["role"],
                                    "content": msg["content"]
                                })

                            # 에이전트 컨텍스트 복원
                            st.session_state.agent.context["analyzed_files"] = session_data.get("analyzed_files", [])
                            st.session_state.agent.memory.session_metadata["analyzed_files"] = session_data.get("analyzed_files", [])
                            st.session_state.agent.memory.session_metadata["generated_files"] = session_data.get("generated_files", [])
                            st.session_state.agent.memory.session_metadata["user_info"] = session_data.get("user_info", {})
                            st.session_state.agent.memory.session_id = session_data.get("session_id")

                            # 대화 히스토리 복원
                            st.session_state.agent.conversation_history = []
                            for msg in session_data["messages"]:
                                if msg["role"] in ["user", "assistant"]:
                                    st.session_state.agent.conversation_history.append({
                                        "role": msg["role"],
                                        "content": msg["content"]
                                    })

                            # 사용자 정보 수집 상태 복원
                            user_info = session_data.get("user_info", {})
                            if user_info.get("nickname") and user_info.get("company"):
                                st.session_state.user_info_collected = True
                            else:
                                st.session_state.user_info_collected = False

                            st.success(f"세션 {selected_session_id} 불러오기 완료")
                            st.rerun()
                        else:
                            st.error("세션을 불러올 수 없습니다.")

        st.divider()

        # 컨텍스트 정보
        st.markdown("### 분석 현황")

        # 메모리 정보
        if hasattr(st.session_state.agent, 'memory'):
            memory = st.session_state.agent.memory

            # 사용자 정보
            user_info = memory.session_metadata.get("user_info", {})
            if user_info.get("nickname") and user_info.get("company"):
                st.markdown(f"**담당자**: {user_info['nickname']}")
                st.markdown(f"**분석 기업**: {user_info['company']}")
                st.divider()

            # 분석된 파일
            if memory.session_metadata["analyzed_files"]:
                st.markdown("**분석된 파일:**")
                for file in memory.session_metadata["analyzed_files"]:
                    st.caption(f"• {Path(file).name}")

            # 생성된 파일
            if memory.session_metadata["generated_files"]:
                st.markdown("**생성된 파일:**")
                for file in memory.session_metadata["generated_files"]:
                    st.caption(f"{file}")

            # 세션 정보
            st.caption(f"메시지: {len(memory.session_metadata['messages'])}개")
            st.caption(f"세션 ID: {memory.session_id}")

            # 피드백 통계
            if hasattr(st.session_state.agent, 'feedback'):
                feedback_stats = st.session_state.agent.feedback.get_feedback_stats()
                if feedback_stats["total_feedback"] > 0:
                    st.markdown("**피드백 통계:**")
                    st.caption(f"총 피드백: {feedback_stats['total_feedback']}개")
                    st.caption(f"👍 긍정: {feedback_stats['positive_feedback']}개")
                    st.caption(f"👎 부정: {feedback_stats['negative_feedback']}개")
                    st.caption(f"만족도: {feedback_stats['satisfaction_rate']*100:.0f}%")

            # 히스토리 내보내기
            if st.button("히스토리 내보내기", use_container_width=True, type="primary", key="export_history"):
                export_path = memory.export_session()
                st.success(f"내보내기 완료: {export_path}")
        else:
            analyzed_files = st.session_state.agent.context.get("analyzed_files", [])
            if analyzed_files:
                st.markdown("**분석된 파일:**")
                for file in analyzed_files:
                    st.caption(f"• {Path(file).name}")
            else:
                st.caption("분석된 파일 없음")

        st.divider()

        # 세션 초기화
        if st.button("대화 초기화", use_container_width=True, type="secondary"):
            st.session_state.agent.reset()
            st.session_state.messages = []
            st.session_state.projection_data = None
            st.rerun()

# ========================================
# 메인 영역 - 탭 구조
# ========================================
with cols[1]:
    # 탭 생성
    tab1, tab2 = st.tabs(["Exit 프로젝션", "Peer PER 분석"])

    # ========================================
    # 탭 1: Exit 프로젝션 (기존 기능)
    # ========================================
    with tab1:
        exit_container = st.container(border=True, height=800)

        with exit_container:
            # 채팅 영역
            chat_area = st.container(height=720)

            with chat_area:
                # 환영 메시지 (최초 1회만)
                if st.session_state.show_welcome and not st.session_state.user_info_collected:
                    with st.chat_message("assistant", avatar=avatar_image):
                        st.markdown("""안녕하세요, 메리입니다.

VC 투자 분석을 시작하기 전에 몇 가지 정보를 알려주세요:
- **사내기업가 별명**: 누구신가요?
- **분석 대상 기업**: 어떤 기업을 분석하시나요?

예시: "홍길동, ABC스타트업" 또는 "김철수 / XYZ테크"

이 정보는 세션 ID로 사용되어 나중에 대화를 쉽게 찾을 수 있습니다.""")

                    st.session_state.show_welcome = False

                for idx, msg in enumerate(st.session_state.messages):
                    if msg["role"] == "user":
                        with st.chat_message("user"):
                            st.markdown(msg["content"])
                    elif msg["role"] == "assistant":
                        with st.chat_message("assistant", avatar=avatar_image):
                            st.markdown(msg["content"])

                            # 피드백 버튼
                            feedback_cols = st.columns([1, 1, 1, 9])
                            feedback_key = f"msg_{idx}"

                            with feedback_cols[0]:
                                if st.button("👍", key=f"thumbs_up_{idx}", use_container_width=True):
                                    user_msg = ""
                                    for i in range(idx-1, -1, -1):
                                        if st.session_state.messages[i]["role"] == "user":
                                            user_msg = st.session_state.messages[i]["content"]
                                            break
                                    st.session_state.agent.feedback.add_feedback(
                                        user_message=user_msg,
                                        assistant_response=msg["content"],
                                        feedback_type="thumbs_up",
                                        context={"message_index": idx}
                                    )
                                    st.session_state.message_feedback[feedback_key] = "thumbs_up"
                                    st.rerun()

                            with feedback_cols[1]:
                                if st.button("👎", key=f"thumbs_down_{idx}", use_container_width=True):
                                    user_msg = ""
                                    for i in range(idx-1, -1, -1):
                                        if st.session_state.messages[i]["role"] == "user":
                                            user_msg = st.session_state.messages[i]["content"]
                                            break
                                    st.session_state.agent.feedback.add_feedback(
                                        user_message=user_msg,
                                        assistant_response=msg["content"],
                                        feedback_type="thumbs_down",
                                        context={"message_index": idx}
                                    )
                                    st.session_state.message_feedback[feedback_key] = "thumbs_down"
                                    st.rerun()

                            with feedback_cols[2]:
                                if st.button("💬", key=f"feedback_text_btn_{idx}", use_container_width=True, help="텍스트 피드백 추가"):
                                    if feedback_key not in st.session_state.feedback_input_visible:
                                        st.session_state.feedback_input_visible[feedback_key] = True
                                    else:
                                        st.session_state.feedback_input_visible[feedback_key] = not st.session_state.feedback_input_visible[feedback_key]
                                    st.rerun()

                            # 텍스트 피드백 입력창
                            if st.session_state.feedback_input_visible.get(feedback_key, False):
                                text_feedback = st.text_area(
                                    "자세한 피드백을 입력하세요:",
                                    key=f"feedback_textarea_{idx}",
                                    placeholder="예: 응답이 너무 길어요...",
                                    height=80
                                )

                                submit_cols = st.columns([1, 1, 8])
                                with submit_cols[0]:
                                    if st.button("제출", key=f"submit_feedback_{idx}", type="primary", use_container_width=True):
                                        if text_feedback.strip():
                                            user_msg = ""
                                            for i in range(idx-1, -1, -1):
                                                if st.session_state.messages[i]["role"] == "user":
                                                    user_msg = st.session_state.messages[i]["content"]
                                                    break
                                            st.session_state.agent.feedback.add_feedback(
                                                user_message=user_msg,
                                                assistant_response=msg["content"],
                                                feedback_type="text_feedback",
                                                feedback_value=text_feedback,
                                                context={"message_index": idx}
                                            )
                                            st.session_state.feedback_text[feedback_key] = text_feedback
                                            st.session_state.feedback_input_visible[feedback_key] = False
                                            st.success("피드백이 저장되었습니다!")
                                            st.rerun()
                                        else:
                                            st.warning("피드백을 입력해주세요")

                                with submit_cols[1]:
                                    if st.button("취소", key=f"cancel_feedback_{idx}", use_container_width=True):
                                        st.session_state.feedback_input_visible[feedback_key] = False
                                        st.rerun()

                            # 피드백 상태 표시
                            if feedback_key in st.session_state.message_feedback:
                                feedback_status = st.session_state.message_feedback[feedback_key]
                                if feedback_status == "thumbs_up":
                                    st.caption("피드백: 도움이 되었습니다")
                                elif feedback_status == "thumbs_down":
                                    st.caption("피드백: 개선이 필요합니다")

                            if feedback_key in st.session_state.feedback_text:
                                st.caption(f"상세 피드백: {st.session_state.feedback_text[feedback_key][:50]}...")

                    elif msg["role"] == "tool":
                        with st.chat_message("assistant", avatar=avatar_image):
                            st.caption(msg["content"])

            # 입력창
            exit_user_input = st.chat_input("메시지를 입력하세요...", key="exit_chat_input")

    # ========================================
    # 탭 2: Peer PER 분석 (새 기능)
    # ========================================
    with tab2:
        peer_container = st.container(border=True, height=800)

        with peer_container:
            # PDF 업로드 영역
            st.markdown("### 기업 자료 업로드")
            pdf_cols = st.columns([2, 1])

            with pdf_cols[0]:
                pdf_file = st.file_uploader(
                    "기업 소개서 / IR 자료 (PDF)",
                    type=["pdf"],
                    key="peer_pdf_uploader",
                    help="비즈니스 모델을 분석할 PDF 파일"
                )

            with pdf_cols[1]:
                if pdf_file:
                    # 임시 파일 저장
                    pdf_temp_path = Path("temp") / pdf_file.name
                    pdf_temp_path.parent.mkdir(exist_ok=True)
                    with open(pdf_temp_path, "wb") as f:
                        f.write(pdf_file.getbuffer())
                    st.session_state.peer_pdf_path = str(pdf_temp_path)
                    st.success(f"{pdf_file.name}")

            st.divider()

            # 채팅 영역
            peer_chat_area = st.container(height=550)

            with peer_chat_area:
                # 환영 메시지
                if not st.session_state.peer_messages:
                    with st.chat_message("assistant", avatar=avatar_image):
                        st.markdown("""**Peer PER 분석 모드**입니다.

투자 대상 기업의 **유사 상장 기업 PER**을 분석하여 적정 밸류에이션을 산정합니다.

---

### 시작하기

1. 위 영역에 **기업 소개서 / IR 자료 (PDF)**를 업로드하세요
2. 아래 입력창에 **"분석해줘"** 라고 입력하세요

---

### 분석 과정

| 단계 | 내용 |
|------|------|
| 1. PDF 분석 | 비즈니스 모델, 산업, 타겟 고객 파악 |
| 2. 확인 요청 | 분석 결과가 맞는지 확인 |
| 3. Peer 검색 | 유사 상장 기업 제안 |
| 4. PER 조회 | 각 기업 PER, 매출, 영업이익률 비교 |

---

PDF가 없어도 직접 기업을 지정할 수 있습니다:
- "Salesforce, ServiceNow, Workday PER 비교해줘"
- "국내 SaaS 기업 PER 알려줘"
""")

                # 메시지 표시
                for idx, msg in enumerate(st.session_state.peer_messages):
                    if msg["role"] == "user":
                        with st.chat_message("user"):
                            st.markdown(msg["content"])
                    elif msg["role"] == "assistant":
                        with st.chat_message("assistant", avatar=avatar_image):
                            st.markdown(msg["content"])
                    elif msg["role"] == "tool":
                        with st.chat_message("assistant", avatar=avatar_image):
                            st.caption(msg["content"])

            # 입력창
            peer_user_input = st.chat_input("Peer 분석 관련 질문...", key="peer_chat_input")

            # 결과 표시 영역
            if st.session_state.peer_analysis_result:
                st.divider()
                st.markdown("### Peer 기업 PER 비교")

                result = st.session_state.peer_analysis_result
                if "peers" in result:
                    # DataFrame 생성
                    peer_df = pd.DataFrame([
                        {
                            "기업명": p.get("company_name", "N/A"),
                            "티커": p.get("ticker", "N/A"),
                            "산업": p.get("industry", "N/A"),
                            "PER": f"{p.get('trailing_per', 'N/A'):.1f}x" if p.get('trailing_per') else "N/A",
                            "Forward PER": f"{p.get('forward_per', 'N/A'):.1f}x" if p.get('forward_per') else "N/A",
                            "매출": p.get("revenue_formatted", "N/A"),
                            "영업이익률": f"{p.get('operating_margin', 0)*100:.1f}%" if p.get('operating_margin') else "N/A"
                        }
                        for p in result["peers"]
                    ])
                    st.dataframe(peer_df, use_container_width=True, hide_index=True)

                    # 통계
                    if "statistics" in result and "trailing_per" in result["statistics"]:
                        stats = result["statistics"]["trailing_per"]
                        stat_cols = st.columns(3)
                        with stat_cols[0]:
                            st.metric("평균 PER", f"{stats.get('mean', 'N/A')}x")
                        with stat_cols[1]:
                            st.metric("중간값 PER", f"{stats.get('median', 'N/A')}x")
                        with stat_cols[2]:
                            st.metric("PER 범위", f"{stats.get('min', 'N/A')} ~ {stats.get('max', 'N/A')}x")

# ========================================
# Exit 탭 메시지 처리
# ========================================
# 변수 초기화 (탭에서 정의되지 않았을 경우)
if 'exit_user_input' not in dir():
    exit_user_input = None
if 'peer_user_input' not in dir():
    peer_user_input = None

# 빠른 명령어 처리
if "quick_command" in st.session_state:
    exit_user_input = st.session_state.quick_command
    del st.session_state.quick_command

# Exit 탭 메시지 처리
if exit_user_input:
    import re

    # 사용자 정보 수집 (최초 1회)
    if not st.session_state.user_info_collected:
        parsed = re.split(r'[,/]', exit_user_input, maxsplit=1)

        if len(parsed) >= 2:
            nickname = parsed[0].strip()
            company_raw = parsed[1].strip()
            company = re.split(r'\s+(분석|검토|해줘|부탁|요청)', company_raw)[0].strip()

            st.session_state.agent.memory.set_user_info(nickname, company, google_email=user_email)
            st.session_state.user_info_collected = True

            confirmation = f"반갑습니다, **{nickname}**님! **{company}** 투자 분석을 시작하겠습니다.\n\n세션 ID: `{st.session_state.agent.memory.session_id}`"

            st.session_state.messages.append({"role": "user", "content": exit_user_input})
            st.session_state.messages.append({"role": "assistant", "content": confirmation})
            st.rerun()
        else:
            st.session_state.messages.append({"role": "user", "content": exit_user_input})
            st.session_state.messages.append({
                "role": "assistant",
                "content": "정보를 정확히 파악하지 못했습니다. 다음 형식으로 다시 알려주세요:\n\n예시: \"홍길동, ABC스타트업\" 또는 \"김철수 / XYZ테크\""
            })
            st.rerun()
    else:
        # 파일 경로 자동 치환
        if uploaded_file and uploaded_file.name in exit_user_input:
            exit_user_input = exit_user_input.replace(uploaded_file.name, st.session_state.uploaded_file_path)

        st.session_state.messages.append({"role": "user", "content": exit_user_input})

        # 에이전트 응답 생성 (스트리밍) - Exit 모드
        async def stream_exit_response():
            full_response = ""
            tool_messages = []

            async for chunk in st.session_state.agent.chat(exit_user_input, mode="exit"):
                if "**도구:" in chunk:
                    tool_messages.append(chunk.strip())
                else:
                    full_response += chunk

            return full_response, tool_messages

        assistant_response, tool_messages = asyncio.run(stream_exit_response())

        for tool_msg in tool_messages:
            st.session_state.messages.append({"role": "tool", "content": tool_msg})

        st.session_state.messages.append({"role": "assistant", "content": assistant_response})
        st.rerun()

# ========================================
# Peer 탭 메시지 처리
# ========================================
if peer_user_input:
    # PDF 경로 자동 추가
    if pdf_file and st.session_state.peer_pdf_path:
        if pdf_file.name in peer_user_input or "PDF" in peer_user_input or "pdf" in peer_user_input:
            peer_user_input = peer_user_input.replace(pdf_file.name, st.session_state.peer_pdf_path)
            if "분석" in peer_user_input and st.session_state.peer_pdf_path not in peer_user_input:
                peer_user_input = f"{st.session_state.peer_pdf_path} 파일을 " + peer_user_input

    st.session_state.peer_messages.append({"role": "user", "content": peer_user_input})

    # 에이전트 응답 생성 (스트리밍) - Peer 모드
    async def stream_peer_response():
        full_response = ""
        tool_messages = []

        async for chunk in st.session_state.agent.chat(peer_user_input, mode="peer"):
            if "**도구:" in chunk:
                tool_messages.append(chunk.strip())
            else:
                full_response += chunk

        return full_response, tool_messages

    assistant_response, tool_messages = asyncio.run(stream_peer_response())

    for tool_msg in tool_messages:
        st.session_state.peer_messages.append({"role": "tool", "content": tool_msg})

    st.session_state.peer_messages.append({"role": "assistant", "content": assistant_response})

    # PER 분석 결과 저장 (도구 결과에서 추출)
    # 이 부분은 도구 실행 결과를 파싱해서 peer_analysis_result에 저장하는 로직
    # 현재는 에이전트가 analyze_peer_per 도구를 호출하면 결과를 저장

    st.rerun()

# ========================================
# 하단: Exit 프로젝션 시각화
# ========================================
if st.session_state.projection_data:
    st.divider()
    st.markdown("## Exit 프로젝션 시각화")

    df = st.session_state.projection_data

    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("PER:O", title="PER 배수"),
            y=alt.Y("IRR:Q", title="IRR (%)"),
            color=alt.Color("PER:N", legend=None),
            tooltip=["PER", "IRR", "Multiple"]
        )
        .properties(height=300)
    )

    st.altair_chart(chart, use_container_width=True)

# 푸터
st.divider()
st.markdown(
    """
    <div style="text-align: center; color: #64748b; font-size: 0.875rem;">
        Powered by Claude Opus 4.5 | VC Investment Agent v0.3.0
    </div>
    """,
    unsafe_allow_html=True
)
