"""
VC 투자 분석 에이전트 - 홈페이지

실행: streamlit run app.py
"""

import streamlit as st
from PIL import Image

from shared.config import initialize_session_state
# from shared.auth import check_authentication  # 인증 비활성화

# 페이지 설정
st.set_page_config(
    page_title="VC 투자 분석 에이전트",
    page_icon="🔴",
    layout="wide",
)

# 초기화
initialize_session_state()
# check_authentication()  # 인증 비활성화

# 이미지 로드
HEADER_IMAGE_PATH = "image-removebg-preview-5.png"
header_image = Image.open(HEADER_IMAGE_PATH)

# ========================================
# 헤더
# ========================================
st.image(header_image, width=300)
st.markdown("# VC 투자 분석 에이전트")
st.markdown("Exit 프로젝션, PER 분석, IRR 계산을 메리와 대화하면서 수행하세요")

st.divider()

# ========================================
# 기능 선택
# ========================================
col1, col2 = st.columns(2)

with col1:
    st.markdown("### 📊 Exit 프로젝션")
    st.markdown("""
**투자검토 엑셀 파일 기반 Exit 분석**

- 투자검토 엑셀 파일 파싱
- PER 기반 시나리오 분석
- IRR 및 멀티플 계산
- Exit 프로젝션 엑셀 생성
- 기본/고급/완전판 3-Tier 분석

**사용 예시:**
- "파일을 분석해줘"
- "2030년 PER 10,20,30배로 Exit 프로젝션 생성해줘"
- "SAFE 전환 시나리오 분석해줘"
    """)

    if st.button("Exit 프로젝션 시작", type="primary", use_container_width=True, key="start_exit"):
        st.switch_page("pages/1_Exit_Projection.py")

with col2:
    st.markdown("### 🔍 Peer PER 분석")
    st.markdown("""
**유사 상장 기업 PER 조회 및 밸류에이션**

- 기업 소개서 PDF 분석
- 비즈니스 모델 기반 Peer 검색
- Yahoo Finance PER 조회
- Peer 벤치마킹 비교표
- 매출 프로젝션 지원

**사용 예시:**
- "PDF 분석해줘"
- "Salesforce, ServiceNow PER 비교해줘"
- "목표 기업가치 500억이면 필요 매출은?"
    """)

    if st.button("Peer PER 분석 시작", type="primary", use_container_width=True, key="start_peer"):
        st.switch_page("pages/2_Peer_PER_Analysis.py")

st.divider()

# ========================================
# 사용 가이드
# ========================================
st.markdown("## 사용 가이드")

with st.expander("Exit 프로젝션 워크플로우", expanded=False):
    st.markdown("""
### 1. 엑셀 파일 업로드
사이드바에서 투자검토 엑셀 파일을 업로드합니다.

### 2. 사용자 정보 입력
"홍길동, ABC스타트업" 형식으로 담당자와 기업명을 입력합니다.

### 3. 파일 분석
"파일 분석해줘"로 엑셀에서 투자조건, IS요약, Cap Table을 추출합니다.

### 4. Exit 프로젝션 생성
PER 배수와 목표 연도를 지정하여 프로젝션을 생성합니다.

**지원 분석 레벨:**
| 레벨 | 내용 |
|------|------|
| 기본 | 회사제시/심사역제시 기준 단순 Exit |
| 고급 | 부분 매각 + NPV 할인 |
| 완전 | SAFE 전환 + 콜옵션 + 희석 효과 |
    """)

with st.expander("Peer PER 분석 워크플로우", expanded=False):
    st.markdown("""
### 1. PDF 업로드 (선택)
기업 소개서나 IR 자료를 업로드합니다.

### 2. PDF 분석
"분석해줘"로 비즈니스 모델, 산업, 타겟 고객을 파악합니다.

### 3. Peer 기업 선정
메리가 유사 상장 기업을 제안합니다. 추가/수정 가능합니다.

### 4. PER 조회
Yahoo Finance에서 각 기업의 PER, 매출, 영업이익률을 조회합니다.

### 5. 프로젝션 지원
Peer 데이터 기반으로 매출 프로젝션을 도와드립니다:
- **역산**: 목표 기업가치 → 필요 매출/이익
- **순방향**: 현재 매출 → 연도별 성장 예측
    """)

with st.expander("티커 형식 가이드", expanded=False):
    st.markdown("""
### 미국 주식
- 심볼 그대로 사용: `AAPL`, `MSFT`, `GOOGL`

### 한국 주식
- KOSPI: `005930.KS` (삼성전자)
- KOSDAQ: `035720.KQ` (카카오)

### 예시
```
"Salesforce(CRM), ServiceNow(NOW), Workday(WDAY) PER 비교해줘"
"삼성전자(005930.KS), SK하이닉스(000660.KS) PER 알려줘"
```
    """)

# ========================================
# 푸터
# ========================================
st.divider()
st.markdown(
    """
    <div style="text-align: center; color: #64748b; font-size: 0.875rem;">
        Powered by Claude Opus 4.5 | VC Investment Agent v0.3.0
    </div>
    """,
    unsafe_allow_html=True
)
