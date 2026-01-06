"""
나라장터 입찰공고 파일 다운로드 자동화
Playwright로 k00 캡처 → requests로 파일 다운로드

사용법:
    # 검색 결과만 보기
    python g2b_file_downloader.py "검색어" --list-only

    # 특정 인덱스 공고만 다운로드
    python g2b_file_downloader.py "검색어" --indices 1,2,3

    # 전체 다운로드
    python g2b_file_downloader.py "검색어" --output ./downloads
"""

import asyncio
import json
import os
import re
import requests
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote
from typing import List, Dict, Optional

# Playwright import (설치 필요: pip install playwright && playwright install)
try:
    from playwright.async_api import async_playwright, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Warning: Playwright not installed. Run: pip install playwright && playwright install chromium")


class G2BFileDownloader:
    """나라장터 입찰공고 파일 다운로드 클래스"""

    def __init__(self, output_dir: str = "/tmp/g2b_downloads"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.captured_k00_values: List[Dict] = []
        self.session = None
        self.bid_list: List[Dict] = []

    def _init_session(self):
        """requests 세션 초기화"""
        if self.session is None:
            self.session = requests.Session()
            self.session.headers.update({
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "*/*",
                "Accept-Language": "ko-KR,ko;q=0.9",
            })
            # 쿠키 획득
            self.session.get("https://www.g2b.go.kr/", timeout=10)

    def search_bids(self, keyword: str, days_back: int = 30, num_results: int = 20) -> List[Dict]:
        """
        나라장터 입찰공고 검색 (크롤링)

        Args:
            keyword: 검색 키워드
            days_back: 며칠 전부터 검색할지
            num_results: 검색 결과 수

        Returns:
            입찰공고 목록
        """
        self._init_session()

        # 세션 초기화
        self.session.get("https://www.g2b.go.kr/pn/pnp/pnpe/BidPbac/selectBidPbacLst.do", timeout=10)

        url = "https://www.g2b.go.kr/pn/pnp/pnpe/BidPbac/selectBidPbacScrollTypeList.do"

        to_date = datetime.now().strftime("%Y%m%d")
        from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")

        payload = {
            "dlBidPbancLstM": {
                "untyBidPbancNo": "",
                "bidPbancNo": "",
                "bidPbancOrd": "",
                "prcmBsneUntyNoOrd": "",
                "prcmBsneSeCd": "0000 조070001 조070002 조070003 조070004 조070005 민079999",
                "bidPbancNm": keyword,
                "pbancPstgDt": "",
                "ldocNoVal": "",
                "bidPrspPrce": "",
                "ctrtDmndRcptNo": "",
                "dmstcOvrsSeCd": "",
                "pbancKndCd": "공440002",  # 용역
                "ctrtTyCd": "",
                "bidCtrtMthdCd": "",
                "scsbdMthdCd": "",
                "fromBidDt": from_date,
                "toBidDt": to_date,
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
                "recordCountPerPage": str(num_results),
                "startIndex": 1,
                "endIndex": num_results
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
            response = self.session.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            if "result" in data:
                self.bid_list = data["result"]
                return self.bid_list

        except Exception as e:
            print(f"검색 실패: {e}")
            return []

        return []

    def print_bid_list(self) -> None:
        """입찰공고 목록 출력"""
        if not self.bid_list:
            print("검색 결과가 없습니다.")
            return

        print(f"\n{'='*70}")
        print(f"검색 결과: {len(self.bid_list)}건")
        print(f"{'='*70}\n")

        for i, item in enumerate(self.bid_list, 1):
            name = item.get("bidPbancNm", "N/A")
            # HTML 엔티티 정리
            name = name.replace("&#40;", "(").replace("&#41;", ")").replace("&lt;br/&gt;", " ")

            bid_no = f"{item.get('bidPbancUntyNo', '')}-{item.get('bidPbancUntyOrd', '')}"
            org = item.get("dmstNm", "N/A")
            date = item.get("pbancPstgDt", "N/A")
            date = date.replace("&lt;br/&gt;", " ").replace("&#40;", "(").replace("&#41;", ")")
            status = item.get("pbancSttsNm", "")
            price = item.get("prspPrce", 0)

            price_str = f"{price/100000000:.1f}억" if price and price > 0 else "-"

            print(f"[{i}] {name}")
            print(f"    공고번호: {bid_no}")
            print(f"    발주기관: {org}")
            print(f"    공고일: {date}")
            print(f"    추정가격: {price_str}")
            print(f"    상태: {status}")
            print()

    async def _intercept_request(self, request):
        """네트워크 요청 인터셉트 - k00 캡처"""
        if "fileUpload.do" in request.url:
            if request.post_data and "k00=" in request.post_data:
                k00_match = re.search(r'k00=([^&]+)', request.post_data)
                if k00_match:
                    k00_value = unquote(k00_match.group(1))
                    # 긴 k00만 저장 (실제 파일 다운로드용)
                    if len(k00_value) > 200:
                        self.captured_k00_values.append({
                            "k00": k00_value,
                            "timestamp": datetime.now().isoformat()
                        })

    async def search_and_capture_k00(self, keyword: str) -> List[Dict]:
        """
        검색 → 상세페이지 → k00 캡처

        Args:
            keyword: 검색 키워드

        Returns:
            캡처된 k00 값 목록
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright가 설치되지 않았습니다.")

        self.captured_k00_values = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                channel="chrome",
                headless=False,
                slow_mo=200,
            )

            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                accept_downloads=True,
                locale="ko-KR",
            )

            page = await context.new_page()
            page.on("request", self._intercept_request)

            try:
                # 1. 메인 페이지 접속
                await page.goto("https://www.g2b.go.kr/")
                await page.wait_for_timeout(3000)

                # 2. 팝업 닫기 (반복적으로)
                for _ in range(5):  # 여러 팝업이 있을 수 있음
                    await page.wait_for_timeout(500)
                    closed_any = False

                    # 다양한 팝업 닫기 버튼 셀렉터
                    close_selectors = [
                        'button:has-text("닫기")',
                        'button:has-text("확인")',
                        'button:has-text("Close")',
                        '[class*="close"]',
                        'a:has-text("닫기")',
                        '.w2popup_window button',
                        '[role="dialog"] button',
                        'button.btn-close',
                    ]

                    for selector in close_selectors:
                        try:
                            btns = await page.query_selector_all(selector)
                            for btn in btns:
                                if await btn.is_visible():
                                    await btn.click(force=True)
                                    closed_any = True
                                    await page.wait_for_timeout(300)
                        except:
                            continue

                    # ESC 키로 팝업 닫기 시도
                    try:
                        await page.keyboard.press("Escape")
                        await page.wait_for_timeout(200)
                    except:
                        pass

                    if not closed_any:
                        break

                # 3. 통합검색
                search_input = await page.wait_for_selector('input[placeholder*="검색"]', timeout=5000)
                if search_input:
                    await search_input.click()
                    await page.wait_for_timeout(500)

                # 4. 검색어 입력
                search_field = await page.query_selector('input[placeholder*="검색어"]')
                if search_field:
                    await search_field.fill(keyword)
                    await search_field.press("Enter")
                    await page.wait_for_timeout(4000)

                # 5. 검색 결과에서 사업명 링크 찾기
                all_elements = await page.query_selector_all('a, button, [onclick], [class*="link"]')
                project_link = None
                for elem in all_elements:
                    text = await elem.text_content()
                    if text and keyword in text:
                        if len(text.strip()) > 15 and not any(skip in text for skip in ["수수료", "안내", "로그인"]):
                            project_link = elem
                            break

                # 6. 사업명 클릭
                if project_link:
                    await project_link.evaluate("el => el.click()")
                    await page.wait_for_timeout(5000)

                    # 7. 파일 링크 클릭 (k00 캡처)
                    all_elements = await page.query_selector_all('a, [onclick], span, td')
                    for elem in all_elements:
                        text = await elem.text_content() or ""
                        if any(ext in text.lower() for ext in ['.hwp', '.pdf', '.xlsx', '.docx', '.zip']):
                            try:
                                await elem.evaluate("el => el.click()")
                                await page.wait_for_timeout(2000)
                            except:
                                continue

                await page.wait_for_timeout(3000)

            finally:
                await browser.close()

        return self.captured_k00_values

    def download_file(self, k00: str, filename: Optional[str] = None) -> Optional[Path]:
        """
        k00 값으로 파일 다운로드

        Args:
            k00: Raonkupload k00 값
            filename: 저장할 파일명 (옵션)

        Returns:
            저장된 파일 경로 또는 None
        """
        self._init_session()

        url = "https://www.g2b.go.kr/fs/fsc/fsca/fileUpload.do?raonk=download"

        try:
            resp = self.session.post(
                url,
                data=f"k00={k00}",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://www.g2b.go.kr",
                },
                timeout=60
            )

            if resp.status_code != 200 or len(resp.content) < 1000:
                return None

            # 파일명 추출
            if not filename:
                content_disp = resp.headers.get("content-disposition", "")
                if "filename" in content_disp:
                    match = re.search(r"filename\*=UTF-8''(.+)|filename=\"(.+)\"", content_disp)
                    if match:
                        filename = unquote(match.group(1) or match.group(2))
                        # 파일명 정리
                        filename = filename.rstrip(";").strip()

            if not filename:
                ext = ".hwp" if "hwp" in resp.headers.get("content-type", "") else ".bin"
                filename = f"file_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"

            # 파일 저장
            save_path = self.output_dir / filename
            with open(save_path, "wb") as f:
                f.write(resp.content)

            return save_path

        except Exception as e:
            print(f"다운로드 실패: {e}")
            return None

    def download_all(self, k00_list: List[Dict]) -> List[Path]:
        """
        모든 k00 값으로 파일 다운로드

        Args:
            k00_list: k00 값 목록

        Returns:
            저장된 파일 경로 목록
        """
        downloaded = []

        for item in k00_list:
            k00 = item.get("k00", "")
            if len(k00) > 300:  # 긴 k00만 (파일 다운로드용)
                path = self.download_file(k00)
                if path:
                    downloaded.append(path)
                    print(f"✅ 다운로드: {path.name}")

        return downloaded


async def download_from_bid_by_name(downloader: G2BFileDownloader, bid_name: str, bid_index: int = 0) -> List[Path]:
    """
    공고명으로 상세페이지 접속하여 파일 다운로드

    Args:
        downloader: G2BFileDownloader 인스턴스
        bid_name: 공고명 (검색할 텍스트)
        bid_index: 몇 번째 매칭 결과 클릭 (0-based)

    Returns:
        다운로드된 파일 경로 목록
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("Playwright가 설치되지 않았습니다.")

    downloader.captured_k00_values = []
    downloaded_files = []

    # 공고명에서 키워드 추출 (너무 긴 경우 앞부분만)
    search_text = bid_name[:50] if len(bid_name) > 50 else bid_name
    # HTML 엔티티 제거
    search_text = search_text.replace("&#40;", "(").replace("&#41;", ")").replace("&lt;br/&gt;", " ")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="chrome",
            headless=False,
            slow_mo=200,
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            accept_downloads=True,
            locale="ko-KR",
        )

        page = await context.new_page()
        page.on("request", downloader._intercept_request)

        try:
            # 1. 메인 페이지 접속
            await page.goto("https://www.g2b.go.kr/")
            await page.wait_for_timeout(3000)

            # 2. 팝업 닫기 (반복적으로)
            for _ in range(5):  # 여러 팝업이 있을 수 있음
                await page.wait_for_timeout(500)
                closed_any = False

                # 다양한 팝업 닫기 버튼 셀렉터
                close_selectors = [
                    'button:has-text("닫기")',
                    'button:has-text("확인")',
                    'button:has-text("Close")',
                    '[class*="close"]',
                    'a:has-text("닫기")',
                    '.w2popup_window button',
                    '[role="dialog"] button',
                    'button.btn-close',
                ]

                for selector in close_selectors:
                    try:
                        btns = await page.query_selector_all(selector)
                        for btn in btns:
                            if await btn.is_visible():
                                await btn.click(force=True)
                                closed_any = True
                                await page.wait_for_timeout(300)
                    except:
                        continue

                # ESC 키로 팝업 닫기 시도
                try:
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(200)
                except:
                    pass

                if not closed_any:
                    break

            # 3. 통합검색 클릭
            search_input = await page.wait_for_selector('input[placeholder*="검색"]', timeout=5000)
            if search_input:
                await search_input.click()
                await page.wait_for_timeout(500)

            # 4. 검색어 입력
            search_field = await page.query_selector('input[placeholder*="검색어"]')
            if search_field:
                await search_field.fill(search_text)
                await search_field.press("Enter")
                await page.wait_for_timeout(4000)

            # 5. 검색 결과에서 공고명 링크 찾기
            all_elements = await page.query_selector_all('a, button, [onclick], [class*="link"]')
            matched_links = []
            for elem in all_elements:
                text = await elem.text_content()
                if text and search_text[:20] in text:  # 앞 20자로 매칭
                    if len(text.strip()) > 15 and not any(skip in text for skip in ["수수료", "안내", "로그인"]):
                        matched_links.append(elem)

            # 지정된 인덱스의 링크 클릭
            if matched_links and bid_index < len(matched_links):
                project_link = matched_links[bid_index]
                await project_link.evaluate("el => el.click()")
                await page.wait_for_timeout(5000)

                # 6. 파일 링크 클릭 (k00 캡처)
                all_elements = await page.query_selector_all('a, [onclick], span, td')
                for elem in all_elements:
                    text = await elem.text_content() or ""
                    if any(ext in text.lower() for ext in ['.hwp', '.pdf', '.xlsx', '.docx', '.zip']):
                        try:
                            await elem.evaluate("el => el.click()")
                            await page.wait_for_timeout(2000)
                        except:
                            continue

                await page.wait_for_timeout(3000)

        finally:
            await browser.close()

    # 캡처된 k00으로 파일 다운로드
    downloaded_files = downloader.download_all(downloader.captured_k00_values)
    return downloaded_files


async def main(
    keyword: str,
    output_dir: str = "/tmp/g2b_downloads",
    list_only: bool = False,
    indices: Optional[List[int]] = None
):
    """메인 함수

    Args:
        keyword: 검색 키워드
        output_dir: 출력 디렉토리
        list_only: True면 검색 결과만 출력
        indices: 다운로드할 공고 인덱스 목록 (1-based)
    """
    downloader = G2BFileDownloader(output_dir)

    print(f"\n{'='*70}")
    print(f"나라장터 입찰공고 파일 다운로드")
    print(f"검색어: {keyword}")
    print(f"{'='*70}")

    # 1. 검색
    print("\n[1] 입찰공고 검색 중...")
    bids = downloader.search_bids(keyword)

    if not bids:
        print("검색 결과가 없습니다.")
        return []

    # 2. 목록 출력
    downloader.print_bid_list()

    if list_only:
        print("(--list-only 모드: 검색 결과만 출력)")
        return bids

    # 3. 다운로드할 공고 결정
    if indices is None:
        # 전체 다운로드 (첫 번째만 기본)
        indices = [1]
        print(f"⚠️ 인덱스 미지정 - 첫 번째 공고만 다운로드합니다.")
        print(f"   여러 공고 다운로드: --indices 1,2,3")

    all_downloaded = []

    for idx in indices:
        if idx < 1 or idx > len(bids):
            print(f"⚠️ 잘못된 인덱스: {idx} (1~{len(bids)} 범위)")
            continue

        bid = bids[idx - 1]  # 0-based 변환
        bid_name = bid.get("bidPbancNm", "")
        bid_name = bid_name.replace("&#40;", "(").replace("&#41;", ")").replace("&lt;br/&gt;", " ")

        print(f"\n[{idx}] 다운로드 중: {bid_name[:40]}...")

        try:
            downloaded = await download_from_bid_by_name(downloader, bid_name, bid_index=0)
            all_downloaded.extend(downloaded)
            print(f"    ✅ {len(downloaded)}개 파일 다운로드 완료")
        except Exception as e:
            print(f"    ❌ 다운로드 실패: {e}")

    # 4. 결과 요약
    print(f"\n{'='*70}")
    print(f"총 {len(all_downloaded)}개 파일 다운로드 완료")
    print(f"저장 위치: {output_dir}")
    print(f"{'='*70}")

    for path in all_downloaded:
        print(f"  - {path.name}")

    return all_downloaded


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="나라장터 입찰공고 파일 다운로드")
    parser.add_argument("keyword", help="검색 키워드")
    parser.add_argument("--output", "-o", default="/tmp/g2b_downloads", help="출력 디렉토리")
    parser.add_argument("--list-only", "-l", action="store_true", help="검색 결과만 출력 (다운로드 안함)")
    parser.add_argument("--indices", "-i", type=str, help="다운로드할 공고 인덱스 (예: 1,2,3)")
    args = parser.parse_args()

    # 인덱스 파싱
    indices = None
    if args.indices:
        indices = [int(x.strip()) for x in args.indices.split(",")]

    asyncio.run(main(args.keyword, args.output, args.list_only, indices))
