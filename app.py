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

# 이미지 로드
HEADER_IMAGE_PATH = "/Users/boram/Library/CloudStorage/GoogleDrive-mwbyun1220@mysc.co.kr/공유 드라이브/C. 조직 (랩, 팀, 위원회, 클럽)/00.AX솔루션/projection_helper/image-removebg-preview-5.png"
AVATAR_IMAGE_PATH = "/Users/boram/Library/CloudStorage/GoogleDrive-mwbyun1220@mysc.co.kr/공유 드라이브/C. 조직 (랩, 팀, 위원회, 클럽)/00.AX솔루션/projection_helper/image-removebg-preview-6.png"

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

# 레이아웃: 왼쪽 사이드바 + 메인 영역
cols = st.columns([1, 3])

# ========================================
# 왼쪽 사이드바
# ========================================
with cols[0]:
    left_container = st.container(border=True, height=800)

    with left_container:
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
# 메인 영역
# ========================================
with cols[1]:
    main_container = st.container(border=True, height=800)

    with main_container:
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
                                # 이전 메시지 찾기 (user)
                                user_msg = ""
                                for i in range(idx-1, -1, -1):
                                    if st.session_state.messages[i]["role"] == "user":
                                        user_msg = st.session_state.messages[i]["content"]
                                        break

                                # 피드백 저장
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
                                # 이전 메시지 찾기 (user)
                                user_msg = ""
                                for i in range(idx-1, -1, -1):
                                    if st.session_state.messages[i]["role"] == "user":
                                        user_msg = st.session_state.messages[i]["content"]
                                        break

                                # 피드백 저장
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
                                # 텍스트 입력창 토글
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
                                placeholder="예: 응답이 너무 길어요 / 설명이 부족해요 / 이 부분이 잘못되었어요...",
                                height=80
                            )

                            submit_cols = st.columns([1, 1, 8])
                            with submit_cols[0]:
                                if st.button("제출", key=f"submit_feedback_{idx}", type="primary", use_container_width=True):
                                    if text_feedback.strip():
                                        # 이전 메시지 찾기
                                        user_msg = ""
                                        for i in range(idx-1, -1, -1):
                                            if st.session_state.messages[i]["role"] == "user":
                                                user_msg = st.session_state.messages[i]["content"]
                                                break

                                        # 텍스트 피드백 저장
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
                                st.caption("피드백: 👍 도움이 되었습니다")
                            elif feedback_status == "thumbs_down":
                                st.caption("피드백: 👎 개선이 필요합니다")

                        # 텍스트 피드백 표시
                        if feedback_key in st.session_state.feedback_text:
                            st.caption(f"💬 상세 피드백: {st.session_state.feedback_text[feedback_key][:50]}...")

                elif msg["role"] == "tool":
                    with st.chat_message("assistant", avatar=avatar_image):
                        st.caption(msg["content"])

        # 입력창
        user_input = st.chat_input("메시지를 입력하세요...")

# 빠른 명령어 처리
if "quick_command" in st.session_state:
    user_input = st.session_state.quick_command
    del st.session_state.quick_command

# 메시지 처리
if user_input:
    # 사용자 정보 수집 (최초 1회)
    if not st.session_state.user_info_collected:
        # 별명과 기업명 파싱
        import re

        # 쉼표 또는 슬래시로 분리
        parsed = re.split(r'[,/]', user_input, maxsplit=1)

        if len(parsed) >= 2:
            nickname = parsed[0].strip()
            company_raw = parsed[1].strip()

            # 기업명에서 "분석", "검토", "해줘" 등 불필요한 단어 제거
            company = re.split(r'\s+(분석|검토|해줘|부탁|요청)', company_raw)[0].strip()

            # 세션 ID 업데이트
            st.session_state.agent.memory.set_user_info(nickname, company)
            st.session_state.user_info_collected = True

            # 확인 메시지
            confirmation = f"반갑습니다, **{nickname}**님! **{company}** 투자 분석을 시작하겠습니다.\n\n세션 ID: `{st.session_state.agent.memory.session_id}`"

            st.session_state.messages.append({
                "role": "user",
                "content": user_input
            })
            st.session_state.messages.append({
                "role": "assistant",
                "content": confirmation
            })

            st.rerun()
        else:
            # 파싱 실패 시 다시 요청
            st.session_state.messages.append({
                "role": "user",
                "content": user_input
            })
            st.session_state.messages.append({
                "role": "assistant",
                "content": "정보를 정확히 파악하지 못했습니다. 다음 형식으로 다시 알려주세요:\n\n예시: \"홍길동, ABC스타트업\" 또는 \"김철수 / XYZ테크\""
            })
            st.rerun()

    else:
        # 파일 경로 자동 치환
        if uploaded_file and uploaded_file.name in user_input:
            user_input = user_input.replace(uploaded_file.name, st.session_state.uploaded_file_path)

        # 사용자 메시지 즉시 표시
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })

        # 사용자 메시지 즉시 렌더링
        with chat_area:
            with st.chat_message("user"):
                st.markdown(user_input)

        # Assistant 응답을 위한 빈 컨테이너 생성
        with chat_area:
            with st.chat_message("assistant", avatar=avatar_image):
                message_placeholder = st.empty()
                tool_placeholder = st.empty()

        # 에이전트 응답 생성 (스트리밍)
        async def stream_response():
            full_response = ""
            tool_messages = []

            async for chunk in st.session_state.agent.chat(user_input):
                # 도구 사용 메시지 분리
                if "**도구:" in chunk:
                    tool_messages.append(chunk.strip())
                    # 도구 사용 메시지 실시간 표시
                    tool_placeholder.markdown("\n\n".join(tool_messages))
                else:
                    full_response += chunk
                    # 응답 실시간 업데이트
                    message_placeholder.markdown(full_response + "▌")

            # 최종 응답 (커서 제거)
            message_placeholder.markdown(full_response)

            return full_response, tool_messages

    # 비동기 실행
    assistant_response, tool_messages = asyncio.run(stream_response())

    # 도구 사용 메시지 저장
    for tool_msg in tool_messages:
        st.session_state.messages.append({
            "role": "tool",
            "content": tool_msg
        })

    # Assistant 메시지 저장
    st.session_state.messages.append({
        "role": "assistant",
        "content": assistant_response
    })

# ========================================
# 하단: Exit 프로젝션 시각화
# ========================================
if st.session_state.projection_data:
    st.divider()
    st.markdown("## Exit 프로젝션 시각화")

    df = st.session_state.projection_data

    # Altair 차트
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
