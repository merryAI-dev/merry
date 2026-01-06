"""
나라장터 Playwright 자동화 - 사업명 클릭 → 상세페이지 → 파일 다운로드
k00 파라미터 캡처를 위한 네트워크 인터셉션
"""

import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, Page, Request, Response
from urllib.parse import parse_qs, unquote


# 다운로드 저장 경로
DOWNLOAD_DIR = Path("/tmp/g2b_downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 캡처된 k00 값 저장
captured_k00_values = []


async def intercept_request(request: Request):
    """네트워크 요청 인터셉트 - k00 캡처"""
    if "fileUpload.do" in request.url or "kupload" in request.url.lower():
        print(f"\n📡 [INTERCEPT] File request: {request.url}")
        print(f"    Method: {request.method}")

        # POST body에서 k00 추출
        if request.post_data:
            post_data = request.post_data
            print(f"    Post Data (first 500): {post_data[:500]}")

            # k00 파라미터 찾기
            if "k00=" in post_data:
                k00_match = re.search(r'k00=([^&]+)', post_data)
                if k00_match:
                    k00_value = unquote(k00_match.group(1))
                    print(f"    ✅ k00 captured: {k00_value[:100]}...")
                    captured_k00_values.append({
                        "url": request.url,
                        "k00": k00_value,
                        "timestamp": datetime.now().isoformat()
                    })


async def intercept_response(response: Response):
    """네트워크 응답 인터셉트"""
    if "fileUpload.do" in response.url or "atch" in response.url.lower():
        print(f"\n📥 [RESPONSE] {response.url}")
        print(f"    Status: {response.status}")
        content_type = response.headers.get("content-type", "")
        print(f"    Content-Type: {content_type}")

        # 파일 다운로드 응답인 경우
        if "application" in content_type or "octet-stream" in content_type:
            content_disp = response.headers.get("content-disposition", "")
            print(f"    Content-Disposition: {content_disp}")


async def click_project_name_and_download(page: Page, keyword: str = "액셀러레이팅"):
    """통합검색 → 사업명 클릭 → 상세페이지에서 파일 다운로드"""

    print("\n" + "=" * 60)
    print(f"🔍 나라장터 통합검색: {keyword}")
    print("=" * 60)

    # 1. 메인 페이지 접속
    print("\n[1] 나라장터 메인 페이지 접속...")
    await page.goto("https://www.g2b.go.kr/")
    await page.wait_for_timeout(3000)

    # 2. 팝업 닫기
    print("\n[2] 팝업 닫기...")
    popup_close_selectors = [
        'button:has-text("닫기")',
        'button:has-text("확인")',
        '.popup-close',
        '.modal-close',
        '[class*="close"]',
        'a:has-text("닫기")',
        '.btn-close',
        'button[aria-label="Close"]',
    ]

    for selector in popup_close_selectors:
        try:
            popups = await page.query_selector_all(selector)
            for popup in popups:
                if await popup.is_visible():
                    await popup.click(force=True)
                    print(f"    팝업 닫음: {selector}")
                    await page.wait_for_timeout(500)
        except:
            continue

    await page.wait_for_timeout(1000)

    # 스크린샷 (팝업 닫은 후)
    await page.screenshot(path=str(DOWNLOAD_DIR / "after_popup_close.png"))

    # 3. 통합검색 클릭
    print("\n[3] 통합검색 클릭...")
    unified_search_selectors = [
        'a:has-text("통합검색")',
        'button:has-text("통합검색")',
        '[class*="search"] a',
        'input[placeholder*="검색"]',
        '#searchKeyword',
        '.search-box input',
    ]

    for selector in unified_search_selectors:
        try:
            elem = await page.wait_for_selector(selector, timeout=3000)
            if elem:
                await elem.click()
                print(f"    클릭: {selector}")
                await page.wait_for_timeout(1000)
                break
        except:
            continue

    # 4. 검색어 입력
    print(f"\n[4] 검색어 입력: {keyword}")

    # 통합검색 입력창 찾기
    search_input_selectors = [
        'input[placeholder*="검색어"]',
        'input[placeholder*="검색"]',
        '#searchKeyword',
        '.search-input',
        'input[type="search"]',
        'input[type="text"]',
    ]

    search_input = None
    for selector in search_input_selectors:
        try:
            inputs = await page.query_selector_all(selector)
            for inp in inputs:
                if await inp.is_visible():
                    search_input = inp
                    print(f"    입력창 발견: {selector}")
                    break
            if search_input:
                break
        except:
            continue

    if search_input:
        await search_input.fill(keyword)
        await page.wait_for_timeout(500)
        # Enter 키 눌러서 검색
        await search_input.press("Enter")
        print("    Enter 키로 검색 실행")
    else:
        print("    ⚠️ 검색 입력창을 찾지 못함")

    await page.wait_for_timeout(4000)

    # 스크린샷 저장 (검색 결과)
    await page.screenshot(path=str(DOWNLOAD_DIR / "search_result.png"))
    print(f"    검색 결과 스크린샷: {DOWNLOAD_DIR / 'search_result.png'}")

    # 5. 검색 결과에서 사업명 링크 찾기
    print("\n[5] 검색 결과에서 사업명 링크 찾기...")

    # 통합검색 결과에서 사업명 링크 찾기
    project_link = None

    # 방법 1: WebSquare 그리드에서 링크 찾기
    try:
        # w2anchor2 클래스가 실제 클릭 가능한 링크
        links = await page.query_selector_all('.w2anchor2, [class*="anchor"], a[onclick]')
        for link in links:
            text = await link.text_content()
            # 액셀러레이팅 키워드가 포함된 실제 사업명 찾기
            if text and keyword in text:
                if len(text.strip()) > 15 and "수수료" not in text:
                    print(f"    Found project: {text[:60]}...")
                    project_link = link
                    break
    except Exception as e:
        print(f"    WebSquare 그리드 탐색 실패: {e}")

    # 방법 2: 테이블 행에서 찾기
    if not project_link:
        try:
            rows = await page.query_selector_all('[class*="w2tb_td"], [class*="grid"] [class*="row"], tr')
            for row in rows:
                links = await row.query_selector_all('a, [class*="anchor"]')
                for link in links:
                    text = await link.text_content()
                    if text and keyword in text:
                        if len(text.strip()) > 15 and "수수료" not in text:
                            print(f"    Found project in row: {text[:60]}...")
                            project_link = link
                            break
                if project_link:
                    break
        except Exception as e:
            print(f"    테이블 탐색 실패: {e}")

    # 방법 3: 페이지 내 모든 클릭 가능한 요소에서 검색
    if not project_link:
        print("    대안 방법: 전체 페이지 탐색...")
        all_elements = await page.query_selector_all('a, button, [onclick], [class*="link"]')
        for elem in all_elements:
            text = await elem.text_content()
            if text and keyword in text:
                if len(text.strip()) > 15 and not any(skip in text for skip in ["수수료", "안내", "로그인", "검색"]):
                    print(f"    Found candidate: {text[:60]}...")
                    project_link = elem
                    break

    if project_link:
        print("\n[6] 사업명 링크 클릭...")
        # 스크린샷 저장 (디버깅용)
        await page.screenshot(path=str(DOWNLOAD_DIR / "before_click.png"))
        print(f"    스크린샷 저장: {DOWNLOAD_DIR / 'before_click.png'}")

        # JavaScript로 직접 클릭 (가장 안정적)
        try:
            await project_link.evaluate("el => el.click()")
            print("    JavaScript 클릭 성공")
        except Exception as e:
            print(f"    JavaScript 클릭 실패: {e}")
            # force click 시도
            try:
                await project_link.click(force=True, timeout=5000)
                print("    Force 클릭 성공")
            except Exception as e2:
                print(f"    Force 클릭도 실패: {e2}")

        await page.wait_for_timeout(3000)

        # 새 탭이 열렸는지 확인
        pages = page.context.pages
        if len(pages) > 1:
            detail_page = pages[-1]
            print(f"    새 탭 열림: {detail_page.url}")
        else:
            detail_page = page

        # 상세 페이지 스크린샷
        await page.wait_for_timeout(2000)
        await detail_page.screenshot(path=str(DOWNLOAD_DIR / "detail_page.png"))
        print(f"    상세 페이지 스크린샷: {DOWNLOAD_DIR / 'detail_page.png'}")

        # 모달 내 스크롤 다운 (첨부파일 섹션 찾기)
        print("\n[7] 첨부파일 섹션 찾기...")

        # 첨부파일 관련 아코디언/섹션 클릭하여 펼치기
        attachment_section_selectors = [
            'button:has-text("첨부")',
            'a:has-text("첨부")',
            '[class*="accordion"]:has-text("첨부")',
            'div:has-text("첨부파일")',
            '.w2group:has-text("첨부")',
        ]

        for selector in attachment_section_selectors:
            try:
                section = await detail_page.query_selector(selector)
                if section:
                    await section.click()
                    print(f"    첨부파일 섹션 클릭: {selector}")
                    await page.wait_for_timeout(1000)
                    break
            except:
                continue

        # 모달/다이얼로그 내에서 스크롤 다운
        try:
            modal = await detail_page.query_selector('.modal, [class*="dialog"], [class*="popup"], [class*="layer"]')
            if modal:
                await modal.evaluate('el => el.scrollTop = el.scrollHeight')
                print("    모달 스크롤 다운")
            else:
                # 페이지 전체 스크롤
                await detail_page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                print("    페이지 스크롤 다운")
        except:
            pass

        await page.wait_for_timeout(1000)
        await detail_page.screenshot(path=str(DOWNLOAD_DIR / "detail_page_scrolled.png"))
        print(f"    스크롤 후 스크린샷: {DOWNLOAD_DIR / 'detail_page_scrolled.png'}")

        # 8. 첨부파일 다운로드 링크 탐색
        print("\n[8] 첨부파일 다운로드 링크 탐색...")

        # HWP, PDF 등 파일 확장자가 포함된 링크 찾기
        file_links = []

        # 방법 1: kupload 그리드 내 파일명 셀 찾기
        try:
            # kupload 파일 목록에서 파일명 클릭 요소 찾기
            kupload_cells = await detail_page.query_selector_all('[class*="kupload"] td, [class*="raon"] td, [class*="w2grid"] td')
            for cell in kupload_cells:
                text = await cell.text_content() or ""
                if any(ext in text.lower() for ext in ['.hwp', '.pdf', '.xlsx', '.docx', '.zip']):
                    # 셀 내 클릭 가능한 요소 찾기
                    clickable = await cell.query_selector('a, span, div')
                    if clickable:
                        print(f"    📎 kupload 파일 발견: {text[:50]}")
                        file_links.append(clickable)
                    else:
                        file_links.append(cell)
        except Exception as e:
            print(f"    kupload 탐색 실패: {e}")

        # 방법 2: 일반 링크/요소에서 찾기
        if not file_links:
            all_elements = await detail_page.query_selector_all('a, [onclick], [class*="file"], [class*="down"], span, td')
            for elem in all_elements:
                text = await elem.text_content() or ""
                onclick = await elem.get_attribute('onclick') or ""
                # 파일 확장자 포함 여부 확인
                if any(ext in text.lower() for ext in ['.hwp', '.pdf', '.xlsx', '.docx', '.zip']):
                    print(f"    📎 파일 발견: {text[:50]}")
                    file_links.append(elem)
                elif 'download' in onclick.lower() or 'filedown' in onclick.lower():
                    print(f"    📎 다운로드 링크: {text[:50] if text else onclick[:50]}")
                    file_links.append(elem)

        # 9. 파일 다운로드 클릭 (k00 캡처를 위해)
        print("\n[9] 파일 다운로드 클릭 (k00 캡처)...")

        if file_links:
            for i, file_link in enumerate(file_links[:3]):  # 최대 3개 파일 시도
                try:
                    text = await file_link.text_content() or f"파일 {i+1}"
                    print(f"    다운로드 시도: {text[:50]}")

                    # JavaScript 클릭으로 다운로드 트리거
                    await file_link.evaluate("el => el.click()")
                    await page.wait_for_timeout(3000)  # 다운로드 요청 대기

                except Exception as e:
                    print(f"    다운로드 실패: {e}")
        else:
            print("    파일 링크를 찾지 못함. 페이지 내 모든 클릭 가능 요소 탐색...")
            # 대안: kupload 관련 요소 찾기
            kupload_elements = await detail_page.query_selector_all('[class*="kupload"], [id*="kupload"], [class*="raon"]')
            for elem in kupload_elements:
                text = await elem.text_content()
                if text:
                    print(f"    kupload 요소: {text[:50]}")
    else:
        print("    ❌ 사업명 링크를 찾지 못함")

        # 디버깅: 현재 페이지 HTML 저장
        html = await page.content()
        debug_path = DOWNLOAD_DIR / "debug_page.html"
        debug_path.write_text(html, encoding="utf-8")
        print(f"    디버그 HTML 저장: {debug_path}")

    return captured_k00_values


async def run_automation(keyword: str = "액셀러레이팅"):
    """메인 자동화 실행"""

    async with async_playwright() as p:
        # 실제 Chrome 브라우저 사용 (나라장터가 Chromium 차단함)
        browser = await p.chromium.launch(
            channel="chrome",  # 실제 설치된 Chrome 사용
            headless=False,  # True로 변경하면 백그라운드 실행
            slow_mo=300,  # 디버깅용 딜레이
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},  # 풀HD 사이즈로 변경
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            accept_downloads=True,
            locale="ko-KR",
        )

        # 다운로드 경로 설정
        page = await context.new_page()

        # 네트워크 인터셉션 설정
        page.on("request", intercept_request)
        page.on("response", intercept_response)

        try:
            # 자동화 실행
            k00_list = await click_project_name_and_download(page, keyword)

            # 결과 저장
            if k00_list:
                result_path = DOWNLOAD_DIR / "captured_k00.json"
                result_path.write_text(
                    json.dumps(k00_list, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                print(f"\n✅ k00 값 저장됨: {result_path}")

            # 디버깅을 위해 잠시 대기
            print("\n⏳ 브라우저 확인 중... (30초 후 자동 종료)")
            await page.wait_for_timeout(30000)

        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()

    return captured_k00_values


if __name__ == "__main__":
    print("=" * 60)
    print("나라장터 Playwright 자동화")
    print("=" * 60)

    results = asyncio.run(run_automation("액셀러레이팅"))

    print("\n" + "=" * 60)
    print("📊 캡처된 k00 값:")
    print("=" * 60)
    for item in results:
        print(json.dumps(item, ensure_ascii=False, indent=2))
