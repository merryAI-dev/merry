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
from shared.discovery_store import DiscoveryRecordStore

# 에이전트 임포트
from agent.discovery_agent import DiscoveryAgent, run_discovery_analysis, run_fusion_proposals
from agent.interactive_critic_agent import InteractiveCriticAgent
from agent.feedback import FeedbackSystem

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent

# 페이지 설정
st.set_page_config(
    page_title="스타트업 발굴 지원 | 메리",
    page_icon="image-removebg-preview-5.png",
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
if "discovery_hypotheses" not in st.session_state:
    st.session_state.discovery_hypotheses = None
if "discovery_verification" not in st.session_state:
    st.session_state.discovery_verification = None
if "discovery_report_path" not in st.session_state:
    st.session_state.discovery_report_path = None
if "discovery_session_id" not in st.session_state:
    st.session_state.discovery_session_id = None
if "discovery_checkpoint_path" not in st.session_state:
    st.session_state.discovery_checkpoint_path = None
if "discovery_agent" not in st.session_state:
    st.session_state.discovery_agent = None
if "discovery_critic_agent" not in st.session_state:
    st.session_state.discovery_critic_agent = None
if "discovery_critic_messages" not in st.session_state:
    st.session_state.discovery_critic_messages = []
if "discovery_chat_mode" not in st.session_state:
    st.session_state.discovery_chat_mode = "추천 Q&A"
if "discovery_show_welcome" not in st.session_state:
    st.session_state.discovery_show_welcome = True
if "discovery_autonomous_mode" not in st.session_state:
    st.session_state.discovery_autonomous_mode = True
if "discovery_document_weight" not in st.session_state:
    st.session_state.discovery_document_weight = 0.7
if "discovery_fusion_proposals" not in st.session_state:
    st.session_state.discovery_fusion_proposals = []
if "discovery_fusion_feedback" not in st.session_state:
    st.session_state.discovery_fusion_feedback = {}


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


def build_discovery_context() -> str:
    """현재 분석 결과를 요약해 비판적 검토에 제공"""
    parts = []

    policy = st.session_state.discovery_policy_analysis or {}
    iris = st.session_state.discovery_iris_mapping or {}
    recs = st.session_state.discovery_recommendations or {}

    themes = policy.get("policy_themes", [])
    if themes:
        parts.append(f"정책 테마: {', '.join(themes[:6])}")

    industries = policy.get("target_industries", [])
    if industries:
        parts.append(f"타겟 산업: {', '.join(industries[:6])}")

    budget = policy.get("budget_info", {})
    if budget:
        budget_lines = [f"{k}: {v}" for k, v in list(budget.items())[:4]]
        parts.append(f"예산 정보: {', '.join(budget_lines)}")

    sdgs = iris.get("aggregate_sdgs", [])
    if sdgs:
        parts.append(f"연계 SDG: {sdgs}")

    metrics = iris.get("aggregate_metrics", [])
    if metrics:
        parts.append(f"IRIS+ 메트릭: {', '.join(metrics[:8])}")

    recommendations = recs.get("recommendations", [])
    if recommendations:
        summary_lines = []
        for rec in recommendations[:4]:
            industry = rec.get("industry", "N/A")
            score = rec.get("total_score", 0)
            summary_lines.append(f"{industry} (총점 {score:.2f})")
        parts.append("추천 요약: " + "; ".join(summary_lines))

    weighting = recs.get("weighting", {}) if isinstance(recs, dict) else {}
    doc_weight = weighting.get("document_weight", st.session_state.get("discovery_document_weight"))
    if doc_weight is not None:
        try:
            parts.append(f"문서 가중치: {float(doc_weight):.0%}")
        except (TypeError, ValueError):
            pass

    fusion_proposals = st.session_state.discovery_fusion_proposals or []
    fusion_feedback = st.session_state.discovery_fusion_feedback or {}
    if fusion_proposals:
        accepted = sum(
            1 for item in fusion_feedback.values()
            if isinstance(item, dict) and item.get("rating") == "좋음"
        )
        parts.append(f"융합안: {len(fusion_proposals)}개 (좋음 {accepted}개)")

    hypotheses = st.session_state.discovery_hypotheses or {}
    if hypotheses.get("summary"):
        parts.append(f"가설 요약: {hypotheses.get('summary')}")

    verification = st.session_state.discovery_verification or {}
    trust_score = verification.get("trust_score")
    if trust_score is not None:
        parts.append(f"신뢰점수: {trust_score:.1f}")
    logic_score = verification.get("logic_score")
    if logic_score is not None:
        parts.append(f"논리점수: {logic_score:.1f}")

    return " | ".join(parts) if parts else "분석 결과가 아직 없습니다."


def get_critic_agent():
    """비판적 검토 에이전트 초기화 또는 반환"""
    if st.session_state.discovery_critic_agent is None:
        user_api_key = get_user_api_key()
        st.session_state.discovery_critic_agent = InteractiveCriticAgent(
            api_key=user_api_key or None,
            response_language="Korean",
        )
    return st.session_state.discovery_critic_agent


def get_discovery_store() -> DiscoveryRecordStore:
    """세션/리포트 저장소"""
    user_email = get_user_email() or "anonymous"
    return DiscoveryRecordStore(user_email)


def load_discovery_session(session_data: dict) -> None:
    """저장된 세션을 UI 상태로 로드"""
    st.session_state.discovery_policy_analysis = session_data.get("policy_analysis")
    st.session_state.discovery_iris_mapping = session_data.get("iris_mapping")
    st.session_state.discovery_recommendations = session_data.get("recommendations")
    st.session_state.discovery_hypotheses = session_data.get("hypotheses")
    st.session_state.discovery_verification = session_data.get("verification")
    st.session_state.discovery_interest_areas = session_data.get("interest_areas") or []
    st.session_state.discovery_pdf_paths = session_data.get("pdf_paths") or []
    st.session_state.discovery_fusion_proposals = session_data.get("fusion_proposals") or []
    st.session_state.discovery_fusion_feedback = session_data.get("fusion_feedback") or {}
    st.session_state.discovery_session_id = session_data.get("session_id")
    st.session_state.discovery_report_path = session_data.get("report_path")
    if session_data.get("document_weight") is not None:
        st.session_state.discovery_document_weight = session_data.get("document_weight")
    st.session_state.discovery_show_welcome = False


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

# 리서치 메리 사전 융합안
st.markdown("**리서치 메리 융합안**")
fusion_cols = st.columns([2, 2, 6])
with fusion_cols[0]:
    generate_fusion_btn = st.button(
        "융합안 생성",
        disabled=not st.session_state.discovery_interest_areas,
        use_container_width=True,
        key="generate_fusion_proposals",
    )
with fusion_cols[1]:
    reset_fusion_btn = st.button(
        "평가 초기화",
        disabled=not st.session_state.discovery_fusion_proposals,
        use_container_width=True,
        key="reset_fusion_feedback",
    )

if reset_fusion_btn:
    st.session_state.discovery_fusion_feedback = {}
    for idx, proposal in enumerate(st.session_state.discovery_fusion_proposals, 1):
        proposal_id = str(proposal.get("id", "")).strip() or f"fusion_{idx}"
        st.session_state.pop(f"fusion_rating_{proposal_id}", None)
        st.session_state.pop(f"fusion_comment_{proposal_id}", None)
    st.success("융합안 평가를 초기화했습니다.")

if generate_fusion_btn:
    with st.spinner("리서치 메리가 융합안을 구성 중입니다..."):
        fusion_result = run_fusion_proposals(
            interest_areas=st.session_state.discovery_interest_areas,
            policy_analysis=st.session_state.discovery_policy_analysis,
            iris_mapping=st.session_state.discovery_iris_mapping,
            proposal_count=4,
            api_key=get_user_api_key() or None,
        )
        if fusion_result.get("success"):
            for idx, proposal in enumerate(st.session_state.discovery_fusion_proposals, 1):
                proposal_id = str(proposal.get("id", "")).strip() or f"fusion_{idx}"
                st.session_state.pop(f"fusion_rating_{proposal_id}", None)
                st.session_state.pop(f"fusion_comment_{proposal_id}", None)
            st.session_state.discovery_fusion_proposals = fusion_result.get("proposals", [])
            st.session_state.discovery_fusion_feedback = {}
            st.success("융합안 생성 완료. 아래에서 평가해 주세요.")
        else:
            st.error(f"융합안 생성 실패: {fusion_result.get('error')}")

fusion_proposals = st.session_state.discovery_fusion_proposals
if fusion_proposals:
    st.caption("관심 분야와 정책 키워드의 융합안을 먼저 검토해 주세요. 평가는 가설 생성에 반영됩니다.")
    for idx, proposal in enumerate(fusion_proposals, 1):
        proposal_id = str(proposal.get("id", "")).strip() or f"fusion_{idx}"
        title = proposal.get("title") or "융합안"
        basis = proposal.get("fusion_basis") or []
        concept = proposal.get("concept") or ""
        validation_questions = proposal.get("validation_questions") or []
        risks = proposal.get("risks") or []

        with st.expander(title, expanded=False):
            if basis:
                st.caption(f"융합 키워드: {', '.join([str(item) for item in basis if str(item).strip()])}")
            if concept:
                st.markdown(f"**개념:** {concept}")
            if validation_questions:
                st.markdown("**검증 질문:**")
                for question in validation_questions:
                    st.caption(f"- {question}")
            if risks:
                st.markdown("**리스크:**")
                for risk in risks:
                    st.caption(f"- {risk}")

            stored_feedback = st.session_state.discovery_fusion_feedback.get(proposal_id, {})
            rating_value = stored_feedback.get("rating")
            rating_options = ["좋음", "보통", "아님"]
            rating_index = rating_options.index(rating_value) if rating_value in rating_options else 0
            st.radio(
                "평가",
                options=rating_options,
                index=rating_index,
                horizontal=True,
                key=f"fusion_rating_{proposal_id}",
            )
            st.text_input(
                "추가 의견",
                value=stored_feedback.get("comment", ""),
                key=f"fusion_comment_{proposal_id}",
            )

    if st.button("평가 저장", key="save_fusion_feedback"):
        feedback = {}
        for idx, proposal in enumerate(fusion_proposals, 1):
            proposal_id = str(proposal.get("id", "")).strip() or f"fusion_{idx}"
            rating = st.session_state.get(f"fusion_rating_{proposal_id}")
            comment = st.session_state.get(f"fusion_comment_{proposal_id}", "")
            if rating:
                feedback[proposal_id] = {
                    "rating": rating,
                    "comment": comment,
                }
        st.session_state.discovery_fusion_feedback = feedback
        accepted = sum(
            1 for item in feedback.values()
            if isinstance(item, dict) and item.get("rating") == "좋음"
        )
        st.success(f"평가 저장 완료 · 좋음 {accepted}개")

# 분석 옵션
st.markdown("**분석 옵션**")
st.session_state.discovery_autonomous_mode = st.checkbox(
    "자율 검증 모드 (가설 생성 + 슈퍼메리 검증)",
    value=st.session_state.discovery_autonomous_mode
)

doc_weight_pct = st.slider(
    "문서 가중치",
    min_value=0,
    max_value=100,
    value=int(st.session_state.discovery_document_weight * 100),
    step=5,
    help="정책 문서 기반 점수와 관심 분야 기반 점수의 비중을 조절합니다.",
)
st.session_state.discovery_document_weight = doc_weight_pct / 100
st.caption(f"관심 분야 가중치: {100 - doc_weight_pct}%")
st.caption("관심 분야가 비어 있으면 문서 가중치가 자동으로 100% 적용됩니다.")

# 버튼 영역
col1, col2, col3 = st.columns([2, 2, 6])

# PDF/텍스트/관심 분야 중 하나라도 있으면 분석 가능
has_content = (
    len(st.session_state.discovery_pdf_paths) > 0
    or len(st.session_state.discovery_text_content.strip()) > 0
    or len(st.session_state.discovery_interest_areas) > 0
)

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
    st.session_state.discovery_hypotheses = None
    st.session_state.discovery_verification = None
    st.session_state.discovery_report_path = None
    st.session_state.discovery_session_id = None
    st.session_state.discovery_checkpoint_path = None
    st.session_state.discovery_agent = None
    st.session_state.discovery_critic_agent = None
    st.session_state.discovery_critic_messages = []
    st.session_state.discovery_chat_mode = "추천 Q&A"
    st.session_state.discovery_show_welcome = True
    st.session_state.discovery_document_weight = 0.7
    st.session_state.discovery_fusion_proposals = []
    st.session_state.discovery_fusion_feedback = {}
    st.rerun()

# 세션 관리/복구
with st.expander("세션 기록/복구", expanded=False):
    store = get_discovery_store()
    col_a, col_b = st.columns([2, 3])
    with col_a:
        if st.button("최근 체크포인트 복구", use_container_width=True):
            checkpoint = store.load_latest_checkpoint()
            if checkpoint:
                load_discovery_session(checkpoint)
                st.session_state.discovery_checkpoint_path = checkpoint.get("checkpoint_path")
                st.success("체크포인트를 복구했습니다.")
                st.rerun()
            else:
                st.info("복구할 체크포인트가 없습니다.")

    with col_b:
        search_query = st.text_input(
            "세션 검색 (테마/산업/요약)",
            key="discovery_session_search",
            label_visibility="visible",
        )

    sessions = store.search_sessions(search_query, limit=8)
    if sessions:
        for session in sessions:
            cols = st.columns([6, 2])
            with cols[0]:
                st.caption(
                    f"{session.get('session_id')} · {session.get('created_at')} · "
                    f"신뢰 {session.get('trust_score', 'N/A')}"
                )
                if session.get("summary"):
                    st.caption(session.get("summary"))
            with cols[1]:
                if st.button("불러오기", key=f"load_session_{session.get('session_id')}"):
                    session_data = store.load_session(session.get("session_id"))
                    if session_data:
                        load_discovery_session(session_data)
                        st.success("세션을 불러왔습니다.")
                        st.rerun()
    else:
        st.caption("저장된 세션이 없습니다.")

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
    if st.session_state.discovery_fusion_proposals:
        feedback = {}
        for idx, proposal in enumerate(st.session_state.discovery_fusion_proposals, 1):
            proposal_id = str(proposal.get("id", "")).strip() or f"fusion_{idx}"
            rating = st.session_state.get(f"fusion_rating_{proposal_id}")
            comment = st.session_state.get(f"fusion_comment_{proposal_id}", "")
            if rating:
                feedback[proposal_id] = {
                    "rating": rating,
                    "comment": comment,
                }
        if feedback:
            st.session_state.discovery_fusion_feedback = feedback

    with st.spinner("정책 자료 분석 중... (약 1-2분 소요)"):
        try:
            result = run_discovery_analysis(
                pdf_paths=st.session_state.discovery_pdf_paths if st.session_state.discovery_pdf_paths else None,
                text_content=st.session_state.discovery_text_content if st.session_state.discovery_text_content.strip() else None,
                interest_areas=st.session_state.discovery_interest_areas,
                focus_keywords=None,
                api_key=get_user_api_key() or None,
                autonomous_mode=st.session_state.discovery_autonomous_mode,
                document_weight=st.session_state.discovery_document_weight,
                fusion_proposals=st.session_state.discovery_fusion_proposals,
                fusion_feedback=st.session_state.discovery_fusion_feedback,
            )

            if result.get("success"):
                st.session_state.discovery_policy_analysis = result.get("policy_analysis")
                st.session_state.discovery_iris_mapping = result.get("iris_mapping")
                st.session_state.discovery_recommendations = result.get("recommendations")
                st.session_state.discovery_hypotheses = result.get("hypotheses")
                st.session_state.discovery_verification = result.get("verification")
                st.session_state.discovery_report_path = result.get("report_path")
                st.session_state.discovery_session_id = result.get("session_id")
                st.session_state.discovery_checkpoint_path = result.get("checkpoint_path")

                # 분석 결과 메시지 추가
                summary = "분석이 완료되었습니다.\n\n"

                doc_weight = result.get("document_weight", st.session_state.discovery_document_weight)
                if doc_weight is not None:
                    try:
                        summary += f"**문서 가중치:** {float(doc_weight):.0%}\n\n"
                    except (TypeError, ValueError):
                        pass

                fusion_proposals = st.session_state.discovery_fusion_proposals
                fusion_feedback = st.session_state.discovery_fusion_feedback
                if fusion_proposals:
                    accepted = sum(
                        1 for item in fusion_feedback.values()
                        if isinstance(item, dict) and item.get("rating") == "좋음"
                    )
                    summary += f"**융합안 반영:** {len(fusion_proposals)}개 (좋음 {accepted}개)\n\n"

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

                verification = result.get("verification") or {}
                if verification.get("trust_score") is not None:
                    summary += f"\n**신뢰점수:** {verification.get('trust_score'):.1f} ({verification.get('trust_level', 'N/A')})\n"
                if verification.get("logic_score") is not None:
                    summary += f"**논리점수:** {verification.get('logic_score'):.1f}\n"

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
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["추천 결과", "정책 분석", "IRIS+ 매핑", "가설/검증", "대화"])

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

                        sources = rec.get("sources", [])
                        if sources:
                            st.markdown("**출처:**")
                            for source in sources:
                                st.caption(f"- {source}")

                        assumptions = rec.get("assumptions", [])
                        if assumptions:
                            st.markdown("**가정:**")
                            for item in assumptions:
                                st.caption(f"- {item}")

                        uncertainties = rec.get("uncertainties", [])
                        if uncertainties:
                            st.markdown("**불확실성:**")
                            for item in uncertainties:
                                st.caption(f"- {item}")

                        markers = rec.get("evidence_markers", [])
                        if markers:
                            st.markdown("**근거 마커:**")
                            for marker in markers:
                                statement = marker.get("statement", "")
                                source = marker.get("source", "")
                                effect = marker.get("effect_size", "")
                                st.caption(f"- {marker.get('marker', '')} {statement} ({source}) {effect}")

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

                        cautions = rec.get("cautions", [])
                        if cautions:
                            st.markdown("**유의점:**")
                            for item in cautions:
                                st.caption(f"- {item}")

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

            source_reliability = policy.get("source_reliability", [])
            if source_reliability:
                avg_rel = sum(source_reliability) / len(source_reliability)
                st.metric("출처 신뢰도(평균)", f"{avg_rel:.2f}")

            warnings = policy.get("warnings", [])
            if warnings:
                st.markdown("### 주의사항")
                for w in warnings:
                    st.caption(f"- {w}")
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

    # 탭 4: 가설/검증
    with tab4:
        st.markdown("### 가설 및 검증 결과")
        st.caption("사고 과정은 논리 체크리스트 형태로 제공되며, 내부 추론 상세는 노출하지 않습니다.")

        hypotheses = st.session_state.discovery_hypotheses or {}
        if hypotheses.get("hypotheses"):
            st.markdown("#### 리서치 메리 가설")
            for idx, hypo in enumerate(hypotheses.get("hypotheses", []), 1):
                with st.expander(f"{idx}. {hypo.get('hypothesis', '가설')}", expanded=(idx <= 3)):
                    st.markdown(f"**근거:** {hypo.get('rationale', 'N/A')}")
                    evidence_needed = hypo.get("evidence_needed", [])
                    if evidence_needed:
                        st.markdown("**필요 근거:**")
                        for item in evidence_needed:
                            st.caption(f"- {item}")
                    signals = hypo.get("signals", [])
                    if signals:
                        st.markdown("**관찰 신호:**")
                        for item in signals:
                            st.caption(f"- {item}")
                    risks = hypo.get("risks", [])
                    if risks:
                        st.markdown("**리스크:**")
                        for item in risks:
                            st.caption(f"- {item}")
                    logic_steps = hypo.get("logic_steps", [])
                    if logic_steps:
                        st.markdown("**논리 단계:**")
                        for step in logic_steps:
                            st.caption(
                                f"- 전제: {step.get('premise')} → 추론: {step.get('inference')} "
                                f"(리스크: {step.get('risk')})"
                            )
                    if hypo.get("confidence") is not None:
                        st.caption(f"신뢰도 추정치: {hypo.get('confidence')}")
        else:
            st.info("가설 결과가 없습니다.")

        verification = st.session_state.discovery_verification or {}
        if verification:
            st.markdown("---")
            st.markdown("#### 서브메리 논리 점검")
            trust_score = verification.get("trust_score")
            trust_level = verification.get("trust_level", "N/A")
            if trust_score is not None:
                st.metric("신뢰점수", f"{trust_score:.1f} ({trust_level})")

            logic_score = verification.get("logic_score")
            if logic_score is not None:
                st.metric("논리점수", f"{logic_score:.1f}")

            process_trace = verification.get("process_trace", {})
            if process_trace:
                with st.expander("전체 과정 로그", expanded=False):
                    data_summary = process_trace.get("data_summary", {})
                    if data_summary:
                        st.markdown("**입력/데이터 상태:**")
                        for key, value in data_summary.items():
                            st.caption(f"- {key}: {value}")

                    trust_breakdown = process_trace.get("trust_breakdown", {})
                    if trust_breakdown:
                        st.markdown("**신뢰점수 계산 내역:**")
                        for key, value in trust_breakdown.items():
                            st.caption(f"- {key}: {value}")

            sub_mary = verification.get("sub_mary", {})
            if sub_mary.get("summary"):
                st.markdown("**서브메리 요약:**")
                st.info(sub_mary.get("summary"))

            sub_steps = sub_mary.get("reasoning_steps", [])
            if sub_steps:
                st.markdown("**서브메리 검증 단계:**")
                for step in sub_steps:
                    st.caption(
                        f"- [{step.get('status', 'warn')}] {step.get('step')}: {step.get('note')}"
                    )

            logic_checks = sub_mary.get("logic_checks", [])
            if logic_checks:
                st.markdown("**논리 체크리스트:**")
                for check in logic_checks:
                    status = check.get("status", "warn")
                    st.caption(
                        f"- [{status}] {check.get('claim')} · 전제: {check.get('premise')} · "
                        f"취약점: {check.get('logic_gap')} · 보완: {check.get('fix')}"
                    )

            st.markdown("---")
            st.markdown("#### 슈퍼메리 검증")
            quality_gate = verification.get("quality_gate", {})
            if quality_gate:
                st.markdown("**품질 게이트:**")
                st.caption(f"점수: {quality_gate.get('quality_score', 'N/A')}")
                issues = quality_gate.get("issues", [])
                if issues:
                    st.caption("이슈:")
                    for issue in issues:
                        st.caption(f"- {issue.get('industry')}: {', '.join(issue.get('issues', []))}")

            super_mary = verification.get("super_mary", {})
            if super_mary.get("summary"):
                st.markdown("**슈퍼메리 요약:**")
                st.info(super_mary.get("summary"))

            reasoning_steps = super_mary.get("reasoning_steps", [])
            if reasoning_steps:
                st.markdown("**슈퍼메리 검증 단계:**")
                for step in reasoning_steps:
                    st.caption(
                        f"- [{step.get('status', 'warn')}] {step.get('step')}: {step.get('note')}"
                    )

            sub_review = super_mary.get("sub_mary_review", [])
            if sub_review:
                st.markdown("**서브메리 검증 결과:**")
                for item in sub_review:
                    st.caption(
                        f"- [{item.get('assessment', 'partial')}] {item.get('sub_claim')} · "
                        f"근거: {item.get('reason')} · 보완: {item.get('correction')}"
                    )

            challenges = super_mary.get("challenges", [])
            if challenges:
                st.markdown("**챌린지 로그:**")
                for ch in challenges:
                    severity = ch.get("severity", "low")
                    st.caption(f"- [{severity}] {ch.get('challenge')} (근거 필요: {ch.get('needed_evidence')})")
        else:
            st.info("검증 결과가 없습니다.")

        report_path = st.session_state.discovery_report_path
        if report_path:
            st.markdown("---")
            st.markdown("#### 리포트")
            st.caption(f"저장 위치: {report_path}")
            if st.button("리포트 재생성", key="regen_discovery_report"):
                store = get_discovery_store()
                session_id = st.session_state.discovery_session_id or store.create_session_id()
                payload = {
                    "created_at": datetime.now().isoformat(),
                    "interest_areas": st.session_state.discovery_interest_areas,
                    "pdf_paths": st.session_state.discovery_pdf_paths,
                    "policy_analysis": st.session_state.discovery_policy_analysis,
                    "iris_mapping": st.session_state.discovery_iris_mapping,
                    "recommendations": st.session_state.discovery_recommendations,
                    "hypotheses": st.session_state.discovery_hypotheses,
                    "verification": st.session_state.discovery_verification,
                    "document_weight": st.session_state.discovery_document_weight,
                    "fusion_proposals": st.session_state.discovery_fusion_proposals,
                    "fusion_feedback": st.session_state.discovery_fusion_feedback,
                }
                stored = store.save_session(session_id, payload, write_report=True)
                st.session_state.discovery_report_path = stored.get("report_path")
                st.session_state.discovery_session_id = stored.get("session_id")
                st.success("리포트를 재생성했습니다.")

        st.markdown("---")
        st.markdown("#### 피드백 회고")
        rating = st.slider("추천 만족도 (1~5)", min_value=1, max_value=5, value=3, key="discovery_feedback_rating")
        feedback_text = st.text_area("추가 피드백", key="discovery_feedback_text")
        if st.button("피드백 저장", key="save_discovery_feedback"):
            feedback = FeedbackSystem(
                session_id=st.session_state.discovery_session_id,
                user_id=get_user_email() or "anonymous",
            )
            context = {
                "trust_score": (verification or {}).get("trust_score"),
                "recommendation_summary": (st.session_state.discovery_recommendations or {}).get("summary"),
                "comment": feedback_text,
            }
            feedback.add_feedback(
                user_message="startup_discovery_feedback",
                assistant_response=(verification or {}).get("verification_summary", ""),
                feedback_type="rating",
                feedback_value=rating,
                context=context,
            )
            stats = feedback.get_feedback_stats()
            influence = stats.get("satisfaction_rate", 0.0) * 100
            st.success(f"피드백 저장 완료 · 영향 점수 {influence:.1f}%")

    # 탭 5: 대화
    with tab5:
        st.markdown("### 대화형 추천")
        st.caption("분석 결과에 대해 질문하거나 추가 추천을 요청하세요.")

        mode = st.radio(
            "대화 모드",
            options=["추천 Q&A", "비판적 검토"],
            horizontal=True,
            index=0 if st.session_state.discovery_chat_mode == "추천 Q&A" else 1,
        )
        st.session_state.discovery_chat_mode = mode

        if mode == "비판적 검토":
            st.info("비판적 검토 모드: `feedback:`으로 시작하면 사용자 피드백을 비판적으로 검토합니다.")

        with st.expander("리서치 트래커", expanded=False):
            st.caption(build_discovery_context())

            status_cols = st.columns(5)
            with status_cols[0]:
                st.caption("정책 분석")
                st.write("✅" if st.session_state.discovery_policy_analysis else "⏳")
            with status_cols[1]:
                st.caption("IRIS+ 매핑")
                st.write("✅" if st.session_state.discovery_iris_mapping else "⏳")
            with status_cols[2]:
                st.caption("추천")
                st.write("✅" if st.session_state.discovery_recommendations else "⏳")
            with status_cols[3]:
                st.caption("가설")
                st.write("✅" if st.session_state.discovery_hypotheses else "⏳")
            with status_cols[4]:
                st.caption("검증")
                st.write("✅" if st.session_state.discovery_verification else "⏳")

            recs = st.session_state.discovery_recommendations or {}
            weighting = recs.get("weighting", {}) if isinstance(recs, dict) else {}
            doc_weight = weighting.get("document_weight", st.session_state.discovery_document_weight)
            try:
                st.caption(f"문서 가중치: {float(doc_weight):.0%}")
            except (TypeError, ValueError):
                pass

            fusion_proposals = st.session_state.discovery_fusion_proposals or []
            if fusion_proposals:
                fusion_feedback = st.session_state.discovery_fusion_feedback or {}
                accepted = sum(
                    1 for item in fusion_feedback.values()
                    if isinstance(item, dict) and item.get("rating") == "좋음"
                )
                st.caption(f"융합안 평가: 좋음 {accepted} / 전체 {len(fusion_proposals)}")

            if st.session_state.discovery_pdf_paths:
                st.markdown("**사용 문서:**")
                for path in st.session_state.discovery_pdf_paths:
                    st.caption(f"- {Path(path).name}")

            report_path = st.session_state.discovery_report_path
            if report_path:
                st.markdown("**리포트:**")
                st.caption(report_path)

            verification = st.session_state.discovery_verification or {}
            process_trace = verification.get("process_trace", {})
            if process_trace:
                st.markdown("**전체 과정 로그:**")
                data_summary = process_trace.get("data_summary", {})
                for key, value in data_summary.items():
                    st.caption(f"- {key}: {value}")
                trust_breakdown = process_trace.get("trust_breakdown", {})
                if trust_breakdown:
                    st.markdown("**신뢰점수 계산 내역:**")
                    for key, value in trust_breakdown.items():
                        st.caption(f"- {key}: {value}")

        # 대화 기록 표시
        message_pool = (
            st.session_state.discovery_critic_messages
            if mode == "비판적 검토"
            else st.session_state.discovery_messages
        )

        for message in message_pool:
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
            message_pool.append({
                "role": "user",
                "content": user_input
            })

            with st.chat_message("user", avatar=user_avatar_image):
                st.markdown(user_input)

            with st.chat_message("assistant", avatar=avatar_image):
                research_status = st.status("리서치 진행 중...", expanded=False, state="running")
                try:
                    response_placeholder = st.empty()
                    response_container = [""]  # mutable container for async closure

                    if mode == "비판적 검토":
                        critic_agent = get_critic_agent()
                        critic_agent.set_context(build_discovery_context())

                        async def get_response():
                            async for chunk in critic_agent.chat(user_input):
                                response_container[0] += chunk
                                response_placeholder.markdown(response_container[0] + "▌")
                            response_placeholder.markdown(response_container[0])

                        asyncio.run(get_response())
                    else:
                        agent = get_discovery_agent()

                        # 컨텍스트 설정
                        agent.policy_analysis = st.session_state.discovery_policy_analysis
                        agent.iris_mapping = st.session_state.discovery_iris_mapping
                        agent.recommendations = st.session_state.discovery_recommendations
                        agent.interest_areas = st.session_state.discovery_interest_areas
                        agent.pdf_paths = st.session_state.discovery_pdf_paths
                        agent.document_weight = st.session_state.discovery_document_weight
                        agent.fusion_proposals = st.session_state.discovery_fusion_proposals
                        agent.fusion_feedback = st.session_state.discovery_fusion_feedback

                        async def get_response():
                            async for chunk in agent.chat(user_input, stream=True):
                                response_container[0] += chunk
                                response_placeholder.markdown(response_container[0] + "▌")
                            response_placeholder.markdown(response_container[0])

                        asyncio.run(get_response())

                    message_pool.append({
                        "role": "assistant",
                        "content": response_container[0]
                    })
                    research_status.update(label="리서치 완료", state="complete")

                except Exception as e:
                    research_status.update(label="리서치 중 오류 발생", state="error")
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
