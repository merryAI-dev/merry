"""
나라장터 입찰공고정보서비스 Open API
공공데이터포털: https://www.data.go.kr/data/15127772/openapi.do

Base URL: apis.data.go.kr/1230000/ad/BidPublicInfoService
"""

import requests
import json
from datetime import datetime, timedelta
from urllib.parse import quote_plus
import os


# API 키 설정 (환경변수 또는 직접 입력)
API_KEY = os.environ.get("G2B_API_KEY", "YOUR_API_KEY_HERE")

BASE_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService"


def search_service_bids(
    keyword: str = None,
    from_date: str = None,
    to_date: str = None,
    num_of_rows: int = 10,
    page_no: int = 1,
):
    """
    용역 입찰공고 목록 조회

    Args:
        keyword: 검색 키워드 (공고명)
        from_date: 시작일 (YYYYMMDD)
        to_date: 종료일 (YYYYMMDD)
        num_of_rows: 한 페이지 결과 수
        page_no: 페이지 번호
    """
    endpoint = f"{BASE_URL}/getBidPblancListInfoServc"

    # 기본 날짜 설정 (최근 30일)
    if not to_date:
        to_date = datetime.now().strftime("%Y%m%d") + "0000"
    else:
        to_date = to_date + "0000"

    if not from_date:
        from_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d") + "0000"
    else:
        from_date = from_date + "0000"

    params = {
        "serviceKey": API_KEY,
        "numOfRows": num_of_rows,
        "pageNo": page_no,
        "type": "json",
        "inqryDiv": "1",  # 1: 공고일시 기준
        "inqryBgnDt": from_date,
        "inqryEndDt": to_date,
    }

    # 키워드 검색 (공고명)
    if keyword:
        params["bidNtceNm"] = keyword

    print(f"🔍 용역 입찰공고 검색 중...")
    print(f"   기간: {from_date[:8]} ~ {to_date[:8]}")
    if keyword:
        print(f"   키워드: {keyword}")

    try:
        response = requests.get(endpoint, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        # 응답 구조 확인
        if "response" in data:
            header = data["response"].get("header", {})
            body = data["response"].get("body", {})

            result_code = header.get("resultCode")
            result_msg = header.get("resultMsg")

            if result_code == "00":
                total_count = body.get("totalCount", 0)
                items = body.get("items", [])

                print(f"✅ 검색 결과: 총 {total_count}건\n")

                if items:
                    for i, item in enumerate(items, 1):
                        print(f"[{i}] {item.get('bidNtceNm', 'N/A')}")
                        print(f"    공고번호: {item.get('bidNtceNo', 'N/A')}-{item.get('bidNtceOrd', '')}")
                        print(f"    발주기관: {item.get('ntceInsttNm', 'N/A')}")
                        print(f"    공고일시: {item.get('bidNtceDt', 'N/A')}")
                        print(f"    개찰일시: {item.get('opengDt', 'N/A')}")
                        print(f"    추정가격: {item.get('presmptPrce', 'N/A')}")
                        print(f"    입찰방식: {item.get('bidMethdNm', 'N/A')}")
                        print()

                return items
            else:
                print(f"❌ API 오류: {result_msg}")
                return None
        else:
            print(f"⚠️ 예상치 못한 응답 형식:")
            print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ 요청 실패: {e}")
        return None


def search_service_bids_pps(
    keyword: str = None,
    from_date: str = None,
    to_date: str = None,
    num_of_rows: int = 10,
    page_no: int = 1,
):
    """
    나라장터 검색조건으로 용역 입찰공고 조회
    (더 다양한 검색 옵션 지원)
    """
    endpoint = f"{BASE_URL}/getBidPblancListInfoServcPPSSrch"

    if not to_date:
        to_date = datetime.now().strftime("%Y%m%d") + "2359"
    else:
        to_date = to_date + "2359"

    if not from_date:
        from_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d") + "0000"
    else:
        from_date = from_date + "0000"

    params = {
        "serviceKey": API_KEY,
        "numOfRows": num_of_rows,
        "pageNo": page_no,
        "type": "json",
        "inqryDiv": "1",
        "inqryBgnDt": from_date,
        "inqryEndDt": to_date,
    }

    if keyword:
        params["bidNtceNm"] = keyword

    try:
        response = requests.get(endpoint, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if "response" in data:
            body = data["response"].get("body", {})
            return body.get("items", [])

    except Exception as e:
        print(f"❌ 오류: {e}")
        return None


def get_bid_attachments(bid_ntce_no: str, bid_ntce_ord: str = "00"):
    """
    입찰공고 첨부파일 정보 조회 (e발주)

    Args:
        bid_ntce_no: 입찰공고번호
        bid_ntce_ord: 입찰공고차수 (기본값: 00)
    """
    endpoint = f"{BASE_URL}/getBidPblancListInfoEorderAtchFileInfo"

    params = {
        "serviceKey": API_KEY,
        "numOfRows": 100,
        "pageNo": 1,
        "type": "json",
        "bidNtceNo": bid_ntce_no,
    }

    print(f"📎 첨부파일 조회: {bid_ntce_no}")

    try:
        response = requests.get(endpoint, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if "response" in data:
            body = data["response"].get("body", {})
            items = body.get("items", [])

            if items:
                print(f"✅ 첨부파일: {len(items)}개\n")
                for item in items:
                    print(f"  📄 {item.get('atchFileNm', 'N/A')}")
                    print(f"     URL: {item.get('atchFileUrl', 'N/A')}")
                    print()
            else:
                print("   첨부파일 없음")

            return items

    except Exception as e:
        print(f"❌ 오류: {e}")
        return None


def get_bid_detail(bid_ntce_no: str, bid_ntce_ord: str = "00"):
    """
    입찰공고 상세정보 조회 (용역)
    """
    # 용역 상세 조회 API 사용
    endpoint = f"{BASE_URL}/getBidPblancListInfoServc"

    params = {
        "serviceKey": API_KEY,
        "numOfRows": 1,
        "pageNo": 1,
        "type": "json",
        "bidNtceNo": bid_ntce_no,
    }

    try:
        response = requests.get(endpoint, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if "response" in data:
            body = data["response"].get("body", {})
            items = body.get("items", [])

            if items:
                item = items[0]
                print("=== 입찰공고 상세정보 ===")
                print(f"공고명: {item.get('bidNtceNm', 'N/A')}")
                print(f"공고번호: {item.get('bidNtceNo', 'N/A')}-{item.get('bidNtceOrd', '')}")
                print(f"발주기관: {item.get('ntceInsttNm', 'N/A')}")
                print(f"수요기관: {item.get('dminsttNm', 'N/A')}")
                print(f"공고일시: {item.get('bidNtceDt', 'N/A')}")
                print(f"개찰일시: {item.get('opengDt', 'N/A')}")
                print(f"입찰마감: {item.get('bidClseDt', 'N/A')}")
                print(f"추정가격: {item.get('presmptPrce', 'N/A')}")
                print(f"사업금액: {item.get('asignBdgtAmt', 'N/A')}")
                print(f"입찰방식: {item.get('bidMethdNm', 'N/A')}")
                print(f"낙찰방법: {item.get('sucsfbidMthdNm', 'N/A')}")
                print(f"계약구분: {item.get('cntrctCnclsMthdNm', 'N/A')}")
                return item

    except Exception as e:
        print(f"❌ 오류: {e}")
        return None


if __name__ == "__main__":
    print("=" * 60)
    print("나라장터 입찰공고정보서비스 API 테스트")
    print("=" * 60)

    if API_KEY == "YOUR_API_KEY_HERE":
        print("\n⚠️ API 키를 설정해주세요!")
        print("   방법 1: 환경변수 설정")
        print("   $ export G2B_API_KEY='발급받은키'")
        print("\n   방법 2: 코드에서 직접 수정")
        print("   API_KEY = '발급받은키'")
    else:
        # 테스트: 액셀러레이팅 관련 용역 입찰공고 검색
        print("\n[테스트] 용역 입찰공고 검색")
        results = search_service_bids(keyword="액셀러레이팅", num_of_rows=5)

        if results and len(results) > 0:
            # 첫 번째 결과의 상세정보 조회
            first_bid = results[0]
            bid_no = first_bid.get("bidNtceNo")

            print("\n[테스트] 첨부파일 조회")
            get_bid_attachments(bid_no)
