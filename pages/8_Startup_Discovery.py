"""
스타트업 발굴 지원 페이지

정부 정책 자료와 IRIS+ 임팩트 기준으로 유망 산업/스타트업 영역을 추천합니다.
"""

import streamlit as st
import asyncio
import os
import json
from pathlib import Path
from datetime import datetime

# 공통 모듈 임포트
from shared.config import initialize_session_state, get_avatar_image, get_user_avatar_image, inject_custom_css
from shared.auth import check_authentication, get_user_email, get_user_api_key
from shared.sidebar import render_sidebar

# 에이전트 임포트
from agent.discovery_agent import DiscoveryAgent, run_discovery_analysis

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent

# 페이지 설정
st.set_page_config(
    page_title="스타트업 발굴 지원 | AC",
    page_icon="AC",
    layout="wide",
)

# 초기화
initialize_session_state()
check_authentication()
inject_custom_css()

# 아바타 이미지 로드
avatar_image = get_avatar_image()
user_avatar_image = get_user_avatar_image()

# Discovery 전용 세션 상태 초기화
if "discovery_messages" not in st.session_state:
    st.session_state.discovery_messages = []
if "discovery_pdf_paths" not in st.session_state:
    st.session_state.discovery_pdf_paths = []
if "discovery_text_content" not in st.session_state:
    st.session_state.discovery_text_content = ""
if "discovery_interest_areas" not in st.session_state:
    st.session_state.discovery_interest_areas = []
if "discovery_policy_analysis" not in st.session_state:
    st.session_state.discovery_policy_analysis = None
if "discovery_iris_mapping" not in st.session_state:
    st.session_state.discovery_iris_mapping = None
if "discovery_recommendations" not in st.session_state:
    st.session_state.discovery_recommendations = None
if "discovery_agent" not in st.session_state:
    st.session_state.discovery_agent = None
if "discovery_show_welcome" not in st.session_state:
    st.session_state.discovery_show_welcome = True


def get_discovery_agent():
    """Discovery 에이전트 초기화 또는 반환"""
    if st.session_state.discovery_agent is None:
        user_email = get_user_email() or "anonymous"
        user_api_key = get_user_api_key()
        st.session_state.discovery_agent = DiscoveryAgent(
            user_id=user_email,
            api_key=user_api_key or None
        )
    return st.session_state.discovery_agent


def save_uploaded_file(uploaded_file):
    """업로드된 파일을 temp 디렉토리에 저장"""
    user_email = get_user_email() or "anonymous"
    user_dir = PROJECT_ROOT / "temp" / user_email
    user_dir.mkdir(parents=True, exist_ok=True)

    file_path = user_dir / uploaded_file.name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return str(file_path)


# ========================================
# 메인 영역
# ========================================
st.markdown("# 스타트업 발굴 지원")
st.markdown("정부 정책 자료를 분석하고 IRIS+ 임팩트 기준으로 유망 산업을 추천합니다.")

# 가이드 표시 (분석 전에만)
if st.session_state.discovery_show_welcome and not st.session_state.discovery_recommendations:
    st.markdown("""
    ### 사용 방법

    1. **PDF 업로드**: 정부 정책 PDF 파일을 업로드하세요 (다중 선택 가능)
    2. **관심 분야 입력**: 관심 있는 산업 분야를 입력하세요
    3. **분석 시작**: "분석 시작" 버튼을 클릭하세요

    ### 분석 내용

    - **정부 정책 분석**: PDF에서 정책 테마, 예산 배분, 타겟 산업을 추출합니다
    - **IRIS+ 매핑**: 정책을 IRIS+ 임팩트 메트릭과 SDG에 매핑합니다
    - **산업 추천**: 정책 방향과 임팩트 기준을 종합하여 유망 산업을 추천합니다
    """)

st.markdown("---")

# ========================================
# 입력 영역 (가이드 아래)
# ========================================
st.markdown("### 분석 설정")

# PDF 업로드
st.markdown("**정책 자료 업로드**")
uploaded_files = st.file_uploader(
    "PDF 파일을 선택하세요 (다중 선택 가능)",
    type=["pdf"],
    accept_multiple_files=True,
    key="discovery_pdf_uploader",
    label_visibility="collapsed"
)

if uploaded_files:
    new_paths = []
    for uploaded_file in uploaded_files:
        file_path = save_uploaded_file(uploaded_file)
        if file_path not in st.session_state.discovery_pdf_paths:
            st.session_state.discovery_pdf_paths.append(file_path)
            new_paths.append(file_path)

    if new_paths:
        st.success(f"{len(new_paths)}개 파일 업로드됨")

# 업로드된 파일 목록
if st.session_state.discovery_pdf_paths:
    st.markdown("**업로드된 파일:**")
    for i, path in enumerate(st.session_state.discovery_pdf_paths):
        col1, col2 = st.columns([6, 1])
        with col1:
            st.caption(f"📄 {Path(path).name}")
        with col2:
            if st.button("삭제", key=f"remove_pdf_{i}"):
                st.session_state.discovery_pdf_paths.pop(i)
                st.rerun()

# 텍스트/아티클 입력
st.markdown("**또는 텍스트로 입력**")
text_content = st.text_area(
    "정책 기사, 보도자료 등을 붙여넣으세요",
    value=st.session_state.discovery_text_content,
    height=150,
    placeholder="예: 정부가 2025년 탄소중립 로드맵을 발표했다. 주요 내용은...",
    key="discovery_text_input",
    label_visibility="collapsed"
)
st.session_state.discovery_text_content = text_content

# 관심 분야 입력 (텍스트 입력으로 변경)
st.markdown("**관심 분야**")
interest_input = st.text_input(
    "관심 분야를 입력하세요 (쉼표로 구분)",
    value=", ".join(st.session_state.discovery_interest_areas) if st.session_state.discovery_interest_areas else "",
    placeholder="예: 에너지, 탄소중립, 모빌리티, AI, 헬스케어",
    key="discovery_interest_input",
    label_visibility="collapsed"
)

# 관심 분야 파싱 및 저장
if interest_input:
    parsed_interests = [x.strip() for x in interest_input.split(",") if x.strip()]
    st.session_state.discovery_interest_areas = parsed_interests
else:
    st.session_state.discovery_interest_areas = []

# 버튼 영역
col1, col2, col3 = st.columns([2, 2, 6])

# PDF 또는 텍스트 중 하나라도 있으면 분석 가능
has_content = len(st.session_state.discovery_pdf_paths) > 0 or len(st.session_state.discovery_text_content.strip()) > 0

with col1:
    analyze_btn = st.button(
        "분석 시작",
        type="primary",
        disabled=not has_content,
        use_container_width=True
    )

with col2:
    reset_btn = st.button(
        "초기화",
        use_container_width=True
    )

if reset_btn:
    st.session_state.discovery_messages = []
    st.session_state.discovery_pdf_paths = []
    st.session_state.discovery_text_content = ""
    st.session_state.discovery_interest_areas = []
    st.session_state.discovery_policy_analysis = None
    st.session_state.discovery_iris_mapping = None
    st.session_state.discovery_recommendations = None
    st.session_state.discovery_agent = None
    st.session_state.discovery_show_welcome = True
    st.rerun()

# 현재 상태 표시
if st.session_state.discovery_policy_analysis or st.session_state.discovery_iris_mapping or st.session_state.discovery_recommendations:
    st.markdown("---")
    status_cols = st.columns(3)

    with status_cols[0]:
        if st.session_state.discovery_policy_analysis:
            st.success("✅ 정책 분석 완료")
        else:
            st.info("⏳ 정책 분석 대기")

    with status_cols[1]:
        if st.session_state.discovery_iris_mapping:
            st.success("✅ IRIS+ 매핑 완료")
        else:
            st.info("⏳ IRIS+ 매핑 대기")

    with status_cols[2]:
        if st.session_state.discovery_recommendations:
            rec_count = len(st.session_state.discovery_recommendations.get("recommendations", []))
            st.success(f"✅ 추천 생성 완료 ({rec_count}개)")
        else:
            st.info("⏳ 추천 생성 대기")

# ========================================
# 분석 실행
# ========================================
if analyze_btn and has_content:
    st.session_state.discovery_show_welcome = False

    with st.spinner("정책 자료 분석 중... (약 1-2분 소요)"):
        try:
            result = run_discovery_analysis(
                pdf_paths=st.session_state.discovery_pdf_paths if st.session_state.discovery_pdf_paths else None,
                text_content=st.session_state.discovery_text_content if st.session_state.discovery_text_content.strip() else None,
                interest_areas=st.session_state.discovery_interest_areas,
                focus_keywords=None,
                api_key=get_user_api_key() or None
            )

            if result.get("success"):
                st.session_state.discovery_policy_analysis = result.get("policy_analysis")
                st.session_state.discovery_iris_mapping = result.get("iris_mapping")
                st.session_state.discovery_recommendations = result.get("recommendations")

                # 분석 결과 메시지 추가
                summary = "분석이 완료되었습니다.\n\n"

                if result.get("policy_analysis"):
                    themes = result["policy_analysis"].get("policy_themes", [])
                    summary += f"**정책 테마:** {', '.join(themes[:5])}\n\n"

                if result.get("iris_mapping"):
                    sdgs = result["iris_mapping"].get("aggregate_sdgs", [])
                    summary += f"**연계 SDG:** {sdgs}\n\n"

                if result.get("recommendations"):
                    recs = result["recommendations"].get("recommendations", [])
                    if recs:
                        summary += "**추천 산업:**\n"
                        for i, rec in enumerate(recs[:5], 1):
                            summary += f"{i}. {rec.get('industry', 'N/A')} (점수: {rec.get('total_score', 0):.2f})\n"

                st.session_state.discovery_messages.append({
                    "role": "assistant",
                    "content": summary
                })

                st.success("분석 완료!")
                st.rerun()
            else:
                errors = result.get("errors", ["알 수 없는 오류"])
                st.error(f"분석 실패: {', '.join(errors)}")

        except Exception as e:
            st.error(f"분석 중 오류 발생: {str(e)}")

# ========================================
# 분석 결과 탭
# ========================================
if st.session_state.discovery_policy_analysis or st.session_state.discovery_recommendations:
    st.markdown("---")
    tab1, tab2, tab3, tab4 = st.tabs(["추천 결과", "정책 분석", "IRIS+ 매핑", "대화"])

    # 탭 1: 추천 결과
    with tab1:
        if st.session_state.discovery_recommendations:
            recs = st.session_state.discovery_recommendations.get("recommendations", [])

            if recs:
                st.markdown("### 유망 산업 추천")

                for i, rec in enumerate(recs, 1):
                    with st.expander(f"**{i}. {rec.get('industry', 'N/A')}** (총점: {rec.get('total_score', 0):.2f})", expanded=(i <= 3)):
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.metric("정책 점수", f"{rec.get('policy_score', 0):.2f}")
                        with col2:
                            st.metric("임팩트 점수", f"{rec.get('impact_score', 0):.2f}")
                        with col3:
                            interest_match = "✅ 관심 분야" if rec.get('interest_match') else "-"
                            st.metric("관심 매칭", interest_match)

                        # 추천 근거
                        if rec.get("rationale"):
                            st.markdown("**추천 근거:**")
                            st.info(rec.get("rationale"))

                        # 근거 문서
                        evidence = rec.get("evidence", [])
                        if evidence:
                            st.markdown("**정책 근거:**")
                            for ev in evidence:
                                st.caption(f"- {ev}")

                        # IRIS+ 코드
                        iris_codes = rec.get("iris_codes", [])
                        if iris_codes:
                            st.markdown(f"**IRIS+ 코드:** `{', '.join(iris_codes)}`")

                        # SDG
                        sdgs = rec.get("sdgs", [])
                        if sdgs:
                            st.markdown(f"**연계 SDG:** {sdgs}")

                        # 스타트업 아이디어
                        examples = rec.get("startup_examples", [])
                        if examples:
                            st.markdown("**스타트업 아이디어:**")
                            for ex in examples:
                                st.caption(f"- {ex}")

            # 신흥 분야
            emerging = st.session_state.discovery_recommendations.get("emerging_areas", [])
            if emerging:
                st.markdown("---")
                st.markdown("### 주목할 신흥 분야")
                for area in emerging:
                    st.warning(f"**{area.get('industry', 'N/A')}**: {area.get('reason', '')}")

            # 주의 분야
            caution = st.session_state.discovery_recommendations.get("caution_areas", [])
            if caution:
                st.markdown("---")
                st.markdown("### 주의 필요 분야")
                for area in caution:
                    st.error(f"**{area.get('industry', 'N/A')}**: {area.get('reason', '')}")

            # 요약
            summary = st.session_state.discovery_recommendations.get("summary")
            if summary:
                st.markdown("---")
                st.markdown("### 종합 요약")
                st.info(summary)

        else:
            st.info("분석을 시작하면 추천 결과가 여기에 표시됩니다.")

    # 탭 2: 정책 분석
    with tab2:
        if st.session_state.discovery_policy_analysis:
            policy = st.session_state.discovery_policy_analysis

            # 정책 테마
            themes = policy.get("policy_themes", [])
            if themes:
                st.markdown("### 정책 테마")
                st.markdown(", ".join([f"`{t}`" for t in themes]))

            # 타겟 산업
            industries = policy.get("target_industries", [])
            if industries:
                st.markdown("### 타겟 산업")
                st.markdown(", ".join([f"`{i}`" for i in industries]))

            # 예산 정보
            budget_info = policy.get("budget_info", {})
            if budget_info:
                st.markdown("### 예산 배분")
                for policy_name, budget in budget_info.items():
                    st.caption(f"- **{policy_name}**: {budget}")

            # 핵심 정책
            key_policies = policy.get("key_policies", [])
            if key_policies:
                st.markdown("### 핵심 정책")
                for kp in key_policies[:10]:
                    with st.expander(kp.get("name", "정책")):
                        st.markdown(f"**설명:** {kp.get('description', 'N/A')}")
                        if kp.get("budget"):
                            st.markdown(f"**예산:** {kp.get('budget')}")
                        if kp.get("page"):
                            st.caption(f"출처: p.{kp.get('page')}")

        else:
            st.info("분석을 시작하면 정책 분석 결과가 여기에 표시됩니다.")

    # 탭 3: IRIS+ 매핑
    with tab3:
        if st.session_state.discovery_iris_mapping:
            iris = st.session_state.discovery_iris_mapping

            # 연계 SDG
            aggregate_sdgs = iris.get("aggregate_sdgs", [])
            if aggregate_sdgs:
                st.markdown("### 연계 SDG")
                sdg_cols = st.columns(min(len(aggregate_sdgs), 6))
                for i, sdg in enumerate(aggregate_sdgs[:6]):
                    with sdg_cols[i]:
                        st.metric(f"SDG {sdg}", "✅")

            # SDG 상세 정보
            sdg_details = iris.get("sdg_details", [])
            if sdg_details:
                st.markdown("### SDG 상세")
                for detail in sdg_details:
                    st.caption(f"- **SDG {detail.get('number')}**: {detail.get('name_kr', detail.get('name', ''))}")

            # 매핑 결과
            mappings = iris.get("mappings", [])
            if mappings:
                st.markdown("### IRIS+ 메트릭 매핑")
                for mapping in mappings:
                    theme = mapping.get("theme", "")
                    metrics = mapping.get("iris_metrics", [])

                    if metrics:
                        with st.expander(f"**{theme}** ({len(metrics)}개 메트릭)"):
                            for m in metrics:
                                st.markdown(f"- `{m.get('code')}` {m.get('name_kr', m.get('name', ''))}")
                                if m.get("sdgs"):
                                    st.caption(f"  연계 SDG: {m.get('sdgs')}")

            # 전체 메트릭 목록
            aggregate_metrics = iris.get("aggregate_metrics", [])
            if aggregate_metrics:
                st.markdown("### 전체 IRIS+ 메트릭")
                st.code(", ".join(aggregate_metrics))

        else:
            st.info("분석을 시작하면 IRIS+ 매핑 결과가 여기에 표시됩니다.")

    # 탭 4: 대화
    with tab4:
        st.markdown("### 대화형 추천")
        st.caption("분석 결과에 대해 질문하거나 추가 추천을 요청하세요.")

        # 대화 기록 표시
        for message in st.session_state.discovery_messages:
            if message["role"] == "user":
                with st.chat_message("user", avatar=user_avatar_image):
                    st.markdown(message["content"])
            else:
                with st.chat_message("assistant", avatar=avatar_image):
                    st.markdown(message["content"])

        # 채팅 입력
        user_input = st.chat_input("질문을 입력하세요...", key="discovery_chat_input")

        if user_input:
            # 사용자 메시지 추가
            st.session_state.discovery_messages.append({
                "role": "user",
                "content": user_input
            })

            with st.chat_message("user", avatar=user_avatar_image):
                st.markdown(user_input)

            with st.chat_message("assistant", avatar=avatar_image):
                try:
                    agent = get_discovery_agent()

                    # 컨텍스트 설정
                    agent.policy_analysis = st.session_state.discovery_policy_analysis
                    agent.iris_mapping = st.session_state.discovery_iris_mapping
                    agent.recommendations = st.session_state.discovery_recommendations
                    agent.interest_areas = st.session_state.discovery_interest_areas
                    agent.pdf_paths = st.session_state.discovery_pdf_paths

                    # 응답 생성
                    response_placeholder = st.empty()
                    response_container = [""]  # mutable container for async closure

                    async def get_response():
                        async for chunk in agent.chat(user_input, stream=True):
                            response_container[0] += chunk
                            response_placeholder.markdown(response_container[0] + "▌")
                        response_placeholder.markdown(response_container[0])

                    asyncio.run(get_response())

                    st.session_state.discovery_messages.append({
                        "role": "assistant",
                        "content": response_container[0]
                    })

                except Exception as e:
                    st.error(f"오류 발생: {str(e)}")

            st.rerun()

# 분석 결과 없을 때 대화 탭만 표시
elif st.session_state.discovery_messages:
    st.markdown("---")
    st.markdown("### 대화 기록")

    for message in st.session_state.discovery_messages:
        if message["role"] == "user":
            with st.chat_message("user", avatar=user_avatar_image):
                st.markdown(message["content"])
        else:
            with st.chat_message("assistant", avatar=avatar_image):
                st.markdown(message["content"])
