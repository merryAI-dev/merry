"""
공공입찰 검색 - 나라장터 입찰공고 검색 및 분석
"""

import streamlit as st
import requests
import json
import os
from datetime import datetime, timedelta
import pandas as pd


st.set_page_config(page_title="공공입찰 검색", page_icon="🏛️", layout="wide")

st.title("🏛️ 공공입찰 검색")
st.markdown("나라장터 입찰공고를 검색하고 분석합니다.")

# API 설정
API_KEY = os.environ.get("G2B_API_KEY", "")
BASE_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService"


def search_with_openapi(keyword: str, from_date: str, to_date: str, bid_type: str = "용역", num_of_rows: int = 20):
    """공공데이터포털 API로 검색"""
    if not API_KEY:
        return None, "API 키가 설정되지 않았습니다."

    # 입찰 유형별 엔드포인트
    endpoints = {
        "용역": "/getBidPblancListInfoServc",
        "물품": "/getBidPblancListInfoThng",
        "공사": "/getBidPblancListInfoCnstwk",
        "외자": "/getBidPblancListInfoFrgcpt",
    }

    endpoint = BASE_URL + endpoints.get(bid_type, endpoints["용역"])

    params = {
        "serviceKey": API_KEY,
        "numOfRows": num_of_rows,
        "pageNo": 1,
        "type": "json",
        "inqryDiv": "1",
        "inqryBgnDt": from_date.replace("-", "") + "0000",
        "inqryEndDt": to_date.replace("-", "") + "2359",
    }

    if keyword:
        params["bidNtceNm"] = keyword

    try:
        response = requests.get(endpoint, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if "response" in data:
            header = data["response"].get("header", {})
            body = data["response"].get("body", {})

            if header.get("resultCode") == "00":
                items = body.get("items", [])
                total = body.get("totalCount", 0)
                return items, f"총 {total}건 중 {len(items)}건 조회"
            else:
                return None, f"API 오류: {header.get('resultMsg')}"

        return None, "응답 형식 오류"

    except Exception as e:
        return None, f"요청 실패: {str(e)}"


def search_with_crawling(keyword: str, from_date: str, to_date: str, num_of_rows: int = 20):
    """나라장터 직접 크롤링으로 검색"""

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9",
    })

    # 세션 초기화
    try:
        session.get("https://www.g2b.go.kr/", timeout=10)
        session.get("https://www.g2b.go.kr/pn/pnp/pnpe/BidPbac/selectBidPbacLst.do", timeout=10)
    except:
        return None, "세션 초기화 실패"

    url = "https://www.g2b.go.kr/pn/pnp/pnpe/BidPbac/selectBidPbacScrollTypeList.do"

    payload = {
        "dlBidPbancLstM": {
            "untyBidPbancNo": "",
            "bidPbancNo": "",
            "bidPbancOrd": "",
            "prcmBsneUntyNoOrd": "",
            "prcmBsneSeCd": "0000 조070001 조070002 조070003 조070004 조070005 민079999",
            "bidPbancNm": keyword if keyword else "",
            "pbancPstgDt": "",
            "ldocNoVal": "",
            "bidPrspPrce": "",
            "ctrtDmndRcptNo": "",
            "dmstcOvrsSeCd": "",
            "pbancKndCd": "공440002",
            "ctrtTyCd": "",
            "bidCtrtMthdCd": "",
            "scsbdMthdCd": "",
            "fromBidDt": from_date.replace("-", ""),
            "toBidDt": to_date.replace("-", ""),
            "minBidPrspPrce": "",
            "maxBidPrspPrce": "",
            "bsneAllYn": "Y",
            "frcpYn": "Y",
            "rsrvYn": "Y",
            "laseYn": "Y",
            "untyGrpGb": "",
            "dmstNm": "",
            "pbancPicNm": "",
            "odnLmtLgdngCd": "",
            "odnLmtLgdngNm": "",
            "intpCd": "",
            "intpNm": "",
            "dtlsPrnmNo": "",
            "dtlsPrnmNm": "",
            "slprRcptDdlnYn": "",
            "lcrtTyCd": "",
            "isMas": "",
            "isElpdt": "",
            "oderInstUntyGrpNo": "",
            "esdacYn": "",
            "infoSysCd": "정010029",
            "contxtSeCd": "콘010006",
            "bidDateType": "R",
            "brcoOrgnCd": "",
            "deptOrgnCd": "",
            "isShop": "",
            "srchTy": "0",
            "cangParmVal": "",
            "currentPage": "",
            "recordCountPerPage": str(num_of_rows),
            "startIndex": 1,
            "endIndex": num_of_rows,
        }
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://www.g2b.go.kr",
        "Referer": "https://www.g2b.go.kr/pn/pnp/pnpe/BidPbac/selectBidPbacLst.do",
        "menu-info": '{"menuNo":"01175","menuCangVal":"PNPE001_01","bsneClsfCd":"%EC%97%85130026","scrnNo":"00941"}',
    }

    try:
        response = session.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        if "result" in data:
            items = data["result"]
            return items, f"{len(items)}건 조회"

        return None, "응답 형식 오류"

    except Exception as e:
        return None, f"요청 실패: {str(e)}"


def format_crawling_result(items):
    """크롤링 결과를 DataFrame으로 변환"""
    if not items:
        return pd.DataFrame()

    records = []
    for item in items:
        # HTML 엔티티 정리
        name = item.get("bidPbancNm", "")
        name = name.replace("&#40;", "(").replace("&#41;", ")").replace("&lt;br/&gt;", " ")

        date_str = item.get("pbancPstgDt", "")
        date_str = date_str.replace("&lt;br/&gt;", " ").replace("&#40;", "(").replace("&#41;", ")")

        records.append({
            "공고명": name,
            "공고번호": f"{item.get('bidPbancUntyNo', '')}-{item.get('bidPbancUntyOrd', '')}",
            "발주기관": item.get("dmstNm", ""),
            "공고일시": date_str,
            "상태": item.get("pbancSttsNm", ""),
            "추정가격": item.get("prspPrce", 0),
            "배정예산": item.get("alotBgtAmt", 0),
            "낙찰방법": item.get("scsbdMthdNm", ""),
        })

    return pd.DataFrame(records)


def format_api_result(items):
    """API 결과를 DataFrame으로 변환"""
    if not items:
        return pd.DataFrame()

    records = []
    for item in items:
        records.append({
            "공고명": item.get("bidNtceNm", ""),
            "공고번호": f"{item.get('bidNtceNo', '')}-{item.get('bidNtceOrd', '')}",
            "발주기관": item.get("ntceInsttNm", ""),
            "공고일시": item.get("bidNtceDt", ""),
            "개찰일시": item.get("opengDt", ""),
            "추정가격": item.get("presmptPrce", 0),
            "입찰방식": item.get("bidMethdNm", ""),
            "낙찰방법": item.get("sucsfbidMthdNm", ""),
        })

    return pd.DataFrame(records)


# 사이드바 설정
with st.sidebar:
    st.header("🔧 설정")

    # API 키 입력
    api_key_input = st.text_input(
        "공공데이터포털 API 키",
        value=API_KEY,
        type="password",
        help="data.go.kr에서 발급받은 인증키"
    )
    if api_key_input:
        API_KEY = api_key_input

    st.divider()

    # 데이터 소스 선택
    data_source = st.radio(
        "데이터 소스",
        ["자동 선택", "공공데이터 API", "나라장터 크롤링"],
        help="API 키가 있으면 API 사용, 없으면 크롤링"
    )

    st.divider()

    st.markdown("### 📊 검색 통계")
    if "search_count" not in st.session_state:
        st.session_state.search_count = 0
    st.metric("검색 횟수", st.session_state.search_count)


# 메인 검색 폼
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    keyword = st.text_input(
        "🔍 검색어",
        placeholder="예: 액셀러레이팅, 인공지능, 소프트웨어",
        help="공고명에서 검색"
    )

with col2:
    from_date = st.date_input(
        "시작일",
        value=datetime.now() - timedelta(days=30),
    )

with col3:
    to_date = st.date_input(
        "종료일",
        value=datetime.now(),
    )

# 추가 옵션
col4, col5 = st.columns([1, 1])

with col4:
    bid_type = st.selectbox(
        "입찰 유형",
        ["용역", "물품", "공사", "외자"],
        help="API 사용 시에만 적용"
    )

with col5:
    num_results = st.slider("결과 수", 10, 100, 20)

# 검색 버튼
if st.button("🔍 검색", type="primary", use_container_width=True):
    st.session_state.search_count += 1

    with st.spinner("검색 중..."):
        # 데이터 소스 결정
        use_api = False
        if data_source == "공공데이터 API":
            use_api = True
        elif data_source == "자동 선택":
            use_api = bool(API_KEY)

        if use_api and API_KEY:
            items, message = search_with_openapi(
                keyword,
                from_date.strftime("%Y-%m-%d"),
                to_date.strftime("%Y-%m-%d"),
                bid_type,
                num_results
            )
            df = format_api_result(items) if items else pd.DataFrame()
            source_label = "📡 공공데이터 API"
        else:
            items, message = search_with_crawling(
                keyword,
                from_date.strftime("%Y-%m-%d"),
                to_date.strftime("%Y-%m-%d"),
                num_results
            )
            df = format_crawling_result(items) if items else pd.DataFrame()
            source_label = "🌐 나라장터 크롤링"

    # 결과 표시
    st.divider()

    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.subheader("📋 검색 결과")
    with col_b:
        st.caption(f"{source_label} | {message}")

    if not df.empty:
        # 금액 포맷팅
        if "추정가격" in df.columns:
            df["추정가격(억)"] = df["추정가격"].apply(
                lambda x: f"{x/100000000:.1f}억" if pd.notna(x) and x > 0 else "-"
            )

        # 테이블 표시
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "공고명": st.column_config.TextColumn("공고명", width="large"),
                "추정가격": st.column_config.NumberColumn("추정가격", format="%d원"),
            }
        )

        # 다운로드 버튼
        csv = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "📥 CSV 다운로드",
            csv,
            file_name=f"입찰공고_{keyword}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

        # 통계
        st.divider()
        st.subheader("📊 간단 통계")

        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.metric("총 공고 수", len(df))
        with col_s2:
            if "발주기관" in df.columns:
                st.metric("발주기관 수", df["발주기관"].nunique())
        with col_s3:
            if "추정가격" in df.columns:
                total = df["추정가격"].sum()
                if total > 0:
                    st.metric("총 추정가격", f"{total/100000000:.1f}억원")

        # 발주기관별 현황
        if "발주기관" in df.columns:
            st.markdown("**발주기관별 공고 수**")
            org_counts = df["발주기관"].value_counts().head(10)
            st.bar_chart(org_counts)

    else:
        st.warning("검색 결과가 없습니다.")


# 안내 섹션
with st.expander("ℹ️ 사용 안내"):
    st.markdown("""
    ### 데이터 소스

    1. **공공데이터 API** (권장)
       - 공공데이터포털(data.go.kr)에서 API 키 발급 필요
       - "나라장터 입찰공고정보서비스" 활용신청
       - 더 안정적이고 상세한 정보 제공

    2. **나라장터 크롤링**
       - API 키 없이 사용 가능
       - 기본적인 공고 정보만 제공
       - 서버 상태에 따라 불안정할 수 있음

    ### 검색 팁

    - **액셀러레이팅**: 창업지원, 액셀러레이터 관련 용역
    - **인공지능, AI**: AI/ML 관련 사업
    - **소프트웨어, SW개발**: IT 개발 용역
    - **컨설팅**: 경영/기술 컨설팅

    ### API 키 발급 방법

    1. [공공데이터포털](https://www.data.go.kr) 회원가입
    2. "나라장터 입찰공고정보서비스" 검색
    3. 활용신청 클릭 (자동승인)
    4. 마이페이지 > 데이터활용 > 인증키 확인
    """)


# 푸터
st.divider()
st.caption("데이터 출처: 조달청 나라장터 (g2b.go.kr)")
