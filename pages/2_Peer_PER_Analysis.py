"""
Peer PER 분석 페이지
- 기업 소개서 PDF 분석
- 유사 상장 기업 PER 조회
- Peer 벤치마킹
- 매출 프로젝션 지원
"""

import streamlit as st
import asyncio
from pathlib import Path
import pandas as pd

# 공통 모듈 임포트
from shared.config import initialize_session_state, get_avatar_image, initialize_agent
from shared.auth import check_authentication
from shared.sidebar import render_sidebar

# 페이지 설정
st.set_page_config(
    page_title="Peer PER 분석 | VC 투자 분석",
    page_icon="🔍",
    layout="wide",
)

# 초기화
initialize_session_state()
check_authentication()
initialize_agent()

# 아바타 이미지 로드
avatar_image = get_avatar_image()

# 사이드바 렌더링
render_sidebar()

# ========================================
# 메인 영역
# ========================================
st.markdown("# 🔍 Peer PER 분석")
st.markdown("유사 상장 기업의 PER을 분석하여 적정 밸류에이션을 산정합니다")

st.divider()

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
        st.session_state.peer_pdf_name = pdf_file.name
        st.success(f"업로드 완료: {pdf_file.name}")

st.divider()

# 채팅 컨테이너
chat_container = st.container(border=True, height=550)

with chat_container:
    chat_area = st.container(height=470)

    with chat_area:
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
| 5. 프로젝션 지원 | Peer 데이터 기반 매출 프로젝션 |

---

### 프로젝션 지원 기능

PER 분석 완료 후 **매출 프로젝션**을 도와드립니다:
- **목표 기업가치 역산**: "2028년에 500억 이상" → 필요 매출/이익 계산
- **순방향 프로젝션**: 현재 매출 기준 연도별 성장 예측
- **Peer 벤치마크 적용**: 유사 기업 평균 영업이익률, 성장률 참고

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
    user_input = st.chat_input("Peer 분석 관련 질문...", key="peer_chat_input")

# ========================================
# 결과 표시 영역
# ========================================
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
# 메시지 처리
# ========================================
if user_input:
    # PDF 경로 자동 추가
    if st.session_state.peer_pdf_path:
        pdf_name = st.session_state.get("peer_pdf_name", "")

        # PDF 파일명이 입력에 포함되어 있으면 경로로 치환
        if pdf_name and pdf_name in user_input:
            user_input = user_input.replace(pdf_name, st.session_state.peer_pdf_path)

        # "분석" 키워드가 있고 PDF 경로가 없으면 자동 추가
        elif "분석" in user_input and st.session_state.peer_pdf_path not in user_input:
            # PDF, pdf, 파일 등의 키워드가 있으면 경로 추가
            if any(keyword in user_input.lower() for keyword in ["pdf", "파일", "자료", "ir"]):
                user_input = f"{st.session_state.peer_pdf_path} 파일을 " + user_input
            # 단순히 "분석해줘"만 입력한 경우
            elif user_input.strip() in ["분석해줘", "분석", "분석해", "분석 해줘"]:
                user_input = f"{st.session_state.peer_pdf_path} 파일을 분석해줘"

    st.session_state.peer_messages.append({"role": "user", "content": user_input})

    # 실시간 스트리밍 표시를 위한 placeholder 생성
    with chat_area:
        with st.chat_message("assistant", avatar=avatar_image):
            response_placeholder = st.empty()
            tool_container = st.container()

    # 에이전트 응답 생성 (실시간 스트리밍) - Peer 모드
    async def stream_peer_response_realtime():
        full_response = ""
        tool_messages = []

        async for chunk in st.session_state.agent.chat(user_input, mode="peer"):
            if "**도구:" in chunk:
                tool_messages.append(chunk.strip())
                # 도구 메시지도 실시간 표시
                with tool_container:
                    st.caption(chunk.strip())
            else:
                full_response += chunk
                # 실시간으로 응답 업데이트
                response_placeholder.markdown(full_response + "▌")

        # 최종 응답 (커서 제거)
        response_placeholder.markdown(full_response)
        return full_response, tool_messages

    assistant_response, tool_messages = asyncio.run(stream_peer_response_realtime())

    for tool_msg in tool_messages:
        st.session_state.peer_messages.append({"role": "tool", "content": tool_msg})

    st.session_state.peer_messages.append({"role": "assistant", "content": assistant_response})

    st.rerun()

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
