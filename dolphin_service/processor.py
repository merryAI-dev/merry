"""
Claude Vision PDF Processor

Claude Opus를 사용하여 PDF를 구조화된 데이터로 추출합니다.
Dolphin 대신 Claude Vision API를 기본으로 사용합니다.
"""

import base64
import hashlib
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from dotenv import load_dotenv

# 프로젝트 루트의 .env 파일 로드 (절대 경로 사용)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from .config import DOLPHIN_CONFIG

logger = logging.getLogger(__name__)

# 캐시 디렉토리
CACHE_DIR = Path(os.getenv("PDF_CACHE_DIR", "/tmp/claude_pdf_cache"))


def _get_cache_path(pdf_path: str, max_pages: int, output_mode: str) -> Path:
    """캐시 파일 경로 생성"""
    # 파일 해시 생성
    file_stat = Path(pdf_path).stat()
    cache_key = f"{pdf_path}:{file_stat.st_size}:{file_stat.st_mtime}:{max_pages}:{output_mode}"
    hash_key = hashlib.md5(cache_key.encode()).hexdigest()
    return CACHE_DIR / f"{hash_key}.json"


def _get_cached_result(cache_path: Path) -> Optional[Dict[str, Any]]:
    """캐시된 결과 조회"""
    if not DOLPHIN_CONFIG.get("cache_enabled", True):
        return None

    if not cache_path.exists():
        return None

    try:
        # TTL 체크
        ttl_days = DOLPHIN_CONFIG.get("cache_ttl_days", 7)
        file_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
        if file_age > timedelta(days=ttl_days):
            cache_path.unlink()  # 만료된 캐시 삭제
            return None

        with open(cache_path, "r", encoding="utf-8") as f:
            result = json.load(f)
            result["cache_hit"] = True
            return result
    except Exception as e:
        logger.warning(f"캐시 읽기 실패: {e}")
        return None


def _save_to_cache(cache_path: Path, result: Dict[str, Any]) -> None:
    """결과를 캐시에 저장"""
    if not DOLPHIN_CONFIG.get("cache_enabled", True):
        return

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"캐시 저장 실패: {e}")


class ClaudeVisionProcessor:
    """Claude Vision 기반 PDF 처리기

    - PDF → 이미지 변환
    - Claude Opus Vision으로 구조화된 데이터 추출
    - 테이블, 재무제표 자동 인식
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key

    def process_pdf(
        self,
        pdf_path: str,
        max_pages: int = None,
        output_mode: str = "structured",
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        parallel: bool = True,
        max_workers: int = 10,
    ) -> Dict[str, Any]:
        """PDF 파일을 Claude Vision으로 처리

        Args:
            pdf_path: PDF 파일 경로
            max_pages: 최대 처리 페이지 수
            output_mode: 출력 모드 (text_only, structured, tables_only)
            progress_callback: 진행 상황 콜백 함수
            parallel: True면 페이지를 병렬로 처리 (기본값: True)
            max_workers: 병렬 처리 시 최대 워커 수 (기본값: 10)

        Returns:
            처리 결과 딕셔너리
        """
        start_time = time.time()
        max_pages = max_pages or DOLPHIN_CONFIG["default_max_pages"]

        # 캐시 확인
        cache_path = _get_cache_path(pdf_path, max_pages, output_mode)
        cached = _get_cached_result(cache_path)
        if cached:
            self._emit_progress(progress_callback, "complete", "캐시에서 로드됨")
            return cached

        self._emit_progress(progress_callback, "loading", "PDF 로딩 중...")

        try:
            # 1. PDF를 이미지로 변환
            self._emit_progress(progress_callback, "converting", "PDF를 이미지로 변환 중...")
            images_base64, total_pages = self._pdf_to_base64_images(pdf_path, max_pages)

            if not images_base64:
                return {
                    "success": False,
                    "error": "PDF에서 이미지를 추출할 수 없습니다",
                }

            # 이미지 크기 체크 (총 50MB 제한)
            total_size = sum(len(img) for img in images_base64)
            if total_size > 50_000_000:  # 50MB
                logger.warning(f"이미지 크기 초과: {total_size / 1_000_000:.1f}MB")
                # 페이지 수 줄이기
                reduced_pages = max(5, len(images_base64) // 2)
                images_base64 = images_base64[:reduced_pages]
                logger.info(f"페이지 수를 {reduced_pages}개로 줄임")

            # 2. Claude API로 처리
            num_pages = len(images_base64)

            if parallel and num_pages > 1:
                # 병렬 처리: 페이지별로 동시 처리
                self._emit_progress(
                    progress_callback,
                    "processing",
                    f"Claude Opus로 {num_pages}페이지 병렬 분석 중 (최대 {min(max_workers, num_pages)} 워커)...",
                )
                result = self._process_parallel(
                    images_base64, output_mode, max_workers, progress_callback
                )
            else:
                # 단일 처리: 기존 방식
                self._emit_progress(
                    progress_callback,
                    "processing",
                    f"Claude Opus로 {num_pages}페이지 분석 중...",
                )
                result = self._process_with_claude(
                    images_base64, output_mode, progress_callback
                )

            # 3. 결과 조합
            processing_time = time.time() - start_time

            final_result = {
                "success": True,
                "file_path": pdf_path,
                "total_pages": total_pages,
                "pages_read": len(images_base64),
                "content": result.get("content", ""),
                "char_count": len(result.get("content", "")),
                "structured_content": result.get("structured_content", {}),
                "financial_tables": result.get("financial_tables", {}),
                "processing_method": "claude_opus_parallel" if parallel and num_pages > 1 else "claude_opus",
                "processing_time_seconds": processing_time,
                "parallel_info": result.get("parallel_processing") if parallel and num_pages > 1 else None,
                "cache_hit": False,
                "cached_at": datetime.utcnow().isoformat(),
            }

            # 캐시에 저장
            _save_to_cache(cache_path, final_result)

            self._emit_progress(
                progress_callback,
                "complete",
                f"완료 ({processing_time:.1f}초)",
                {"duration": processing_time},
            )

            return final_result

        except Exception as e:
            logger.error(f"Claude Vision 처리 실패: {e}", exc_info=True)
            return self._fallback_to_pymupdf(pdf_path, max_pages, str(e))

    def _pdf_to_base64_images(
        self, pdf_path: str, max_pages: int
    ) -> tuple:
        """PDF를 base64 인코딩된 이미지 리스트로 변환

        Returns:
            (images_base64: List[str], total_pages: int)
        """
        try:
            import fitz  # PyMuPDF
        except ImportError as e:
            raise ImportError(f"PDF 변환에 PyMuPDF가 필요합니다: {e}")

        doc = None
        images_base64 = []

        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            pages_to_read = min(total_pages, max_pages)

            dpi = DOLPHIN_CONFIG.get("image_dpi", 150)
            zoom = dpi / 72

            for i in range(pages_to_read):
                page = doc[i]
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)

                # PNG로 변환 후 base64 인코딩
                img_bytes = pix.tobytes("png")
                img_base64 = base64.standard_b64encode(img_bytes).decode("utf-8")
                images_base64.append(img_base64)

            return images_base64, total_pages

        finally:
            if doc:
                doc.close()

    def _get_system_prompt(self) -> str:
        """VC 투자 분석 전문가 시스템 프롬프트"""
        return """당신은 10년 이상 경력의 VC(벤처캐피탈) 투자심사역입니다. 수백 건의 스타트업 투자를 검토한 경험이 있습니다.

## 핵심 역량

### 1. 재무제표 분석 전문가
- 손익계산서(P&L, IS): 매출액, 매출원가, 매출총이익, 판관비, 영업이익, EBITDA, 당기순이익
- 재무상태표(BS): 유동자산, 비유동자산, 총자산, 유동부채, 비유동부채, 총부채, 자본총계
- 현금흐름표(CF): 영업활동CF, 투자활동CF, 재무활동CF, 기말현금

### 2. 투자조건 분석
- Pre-money/Post-money 밸류에이션
- 투자금액, 투자단가(주당가격), 취득주식수
- 투자유형: 보통주, 우선주(RCPS), 전환사채(CB), SAFE
- 투자조건: 청산우선권, 희석방지, 동반매각권, 이사선임권

### 3. Cap Table 분석
- 주주명, 보유주식수, 지분율
- 총발행주식수, 주식종류별 구분
- 투자 라운드별 변동사항

### 4. 밸류에이션 지표
- PER (Price to Earnings Ratio)
- PSR (Price to Sales Ratio)
- EV/EBITDA, EV/Revenue
- PBR (Price to Book Ratio)

## 추출 규칙

### 숫자 처리
1. 단위를 반드시 확인하고 원화 기준으로 변환
   - "100억" → 10000000000
   - "50백만원" → 50000000
   - "1.5조" → 1500000000000
2. 천단위 콤마 제거: "1,234,567" → 1234567
3. 음수는 괄호 또는 마이너스로 표시된 것 모두 인식: (100) = -100
4. 비율/퍼센트는 소수로 변환: "15%" → 0.15 (단, metrics에서는 숫자 그대로)

### 연도 처리
1. 추정치 구분: 2024E, 2025E, 2025(E), 2025예상 → 연도에 "E" 표시
2. 실적과 추정치가 혼재된 테이블은 구분하여 표시
3. 반기/분기 데이터도 인식: 1H24, 2Q24 등

### 테이블 처리
1. 병합된 셀은 논리적으로 분리
2. 소계/합계 행은 별도 표시
3. 헤더가 여러 줄인 경우 통합하여 인식

### 특수 케이스
1. "흑자전환", "적자지속" 등 텍스트 주석도 함께 추출
2. YoY 성장률이 있으면 함께 추출
3. 컨센서스 vs 회사제시 구분이 있으면 표시

## 품질 기준
- 숫자 하나라도 틀리면 투자 의사결정에 치명적
- 불확실한 경우 해당 필드를 null로 두고 warnings에 기록
- 테이블이 잘려있거나 불완전하면 명시적으로 경고"""

    def _process_with_claude(
        self,
        images_base64: List[str],
        output_mode: str,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Claude Vision API로 이미지 처리"""
        import httpx
        import anthropic

        # 타임아웃 설정 (5분)
        timeout_config = httpx.Timeout(
            timeout=DOLPHIN_CONFIG.get("timeout_seconds", 300),
            connect=30.0,
        )
        client = anthropic.Anthropic(timeout=timeout_config)

        # 프롬프트 구성
        if output_mode == "tables_only":
            prompt = self._get_tables_only_prompt()
        elif output_mode == "structured":
            prompt = self._get_structured_prompt()
        else:  # text_only
            prompt = self._get_text_only_prompt()

        # 이미지 콘텐츠 구성
        content = []
        for i, img_b64 in enumerate(images_base64):
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_b64,
                },
            })
            content.append({
                "type": "text",
                "text": f"[페이지 {i + 1}]"
            })

        content.append({
            "type": "text",
            "text": prompt
        })

        # Claude API 호출 (Opus + 시스템 프롬프트)
        response = client.messages.create(
            model="claude-opus-4-20250514",  # 최고 성능 Opus 사용
            max_tokens=16384,  # 긴 재무제표도 처리 가능
            system=self._get_system_prompt(),
            messages=[
                {
                    "role": "user",
                    "content": content
                }
            ]
        )

        # 응답 파싱
        response_text = response.content[0].text if response.content else ""
        return self._parse_claude_response(response_text, output_mode)

    def _process_parallel(
        self,
        images_base64: List[str],
        output_mode: str,
        max_workers: int,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """페이지별 병렬 처리로 속도 향상

        각 페이지를 개별 API 콜로 동시에 처리한 후 결과를 병합합니다.
        """
        import httpx
        import anthropic

        num_pages = len(images_base64)
        actual_workers = min(max_workers, num_pages)

        # 페이지별 결과 저장 (순서 유지용)
        page_results: Dict[int, Dict[str, Any]] = {}
        errors: List[str] = []

        def process_single_page(page_idx: int, img_b64: str) -> tuple:
            """단일 페이지 처리"""
            try:
                timeout_config = httpx.Timeout(
                    timeout=DOLPHIN_CONFIG.get("timeout_seconds", 300),
                    connect=30.0,
                )
                client = anthropic.Anthropic(timeout=timeout_config)

                # 단일 페이지용 간소화된 프롬프트
                prompt = self._get_single_page_prompt(output_mode, page_idx + 1)

                content = [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    }
                ]

                response = client.messages.create(
                    model="claude-opus-4-20250514",
                    max_tokens=8192,
                    system=self._get_system_prompt(),
                    messages=[{"role": "user", "content": content}]
                )

                response_text = response.content[0].text if response.content else ""
                return (page_idx, {"success": True, "content": response_text})

            except Exception as e:
                logger.warning(f"페이지 {page_idx + 1} 처리 실패: {e}")
                return (page_idx, {"success": False, "error": str(e)})

        # ThreadPoolExecutor로 병렬 실행
        with ThreadPoolExecutor(max_workers=actual_workers) as executor:
            futures = {
                executor.submit(process_single_page, idx, img): idx
                for idx, img in enumerate(images_base64)
            }

            completed = 0
            for future in as_completed(futures):
                page_idx, result = future.result()
                page_results[page_idx] = result
                completed += 1

                if progress_callback:
                    self._emit_progress(
                        progress_callback,
                        "processing",
                        f"페이지 처리 중... ({completed}/{num_pages})",
                    )

                if not result.get("success"):
                    errors.append(f"페이지 {page_idx + 1}: {result.get('error', 'Unknown error')}")

        # 결과 병합 (페이지 순서대로)
        return self._merge_parallel_results(page_results, output_mode, errors)

    def _get_single_page_prompt(self, output_mode: str, page_num: int) -> str:
        """단일 페이지 처리용 프롬프트"""
        if output_mode == "text_only":
            return f"""이 페이지 (페이지 {page_num})의 내용을 텍스트로 추출해주세요.

규칙:
1. 테이블은 마크다운 테이블 형식으로 변환
2. 원본 레이아웃을 최대한 보존
3. 숫자와 단위를 정확하게 추출

텍스트만 출력하세요."""

        elif output_mode == "tables_only":
            return f"""이 페이지 (페이지 {page_num})에서 테이블만 추출하여 JSON으로 출력하세요:

```json
{{
  "page": {page_num},
  "tables": [
    {{
      "title": "테이블 제목",
      "markdown": "| 열1 | 열2 |\\n|---|---|\\n| 값1 | 값2 |"
    }}
  ],
  "has_financial_data": true/false,
  "financial_type": "income_statement/balance_sheet/cash_flow/cap_table/none"
}}
```
JSON만 출력하세요."""

        else:  # structured
            return f"""이 페이지 (페이지 {page_num})를 투자심사 관점에서 분석하여 JSON으로 출력하세요:

```json
{{
  "page": {page_num},
  "content": "페이지 전체 텍스트",
  "has_financial_data": true/false,
  "financial_type": "income_statement/balance_sheet/cash_flow/cap_table/none",
  "financial_data": {{
    "unit": "억원/백만원/천원",
    "years": ["2023", "2024E"],
    "metrics": {{}}
  }},
  "has_investment_terms": true/false,
  "investment_terms": {{}},
  "has_cap_table": true/false,
  "cap_table": {{}},
  "visual_elements": ["차트", "이미지", "다이어그램 등"],
  "key_info": "이 페이지의 핵심 정보 요약"
}}
```
JSON만 출력하세요."""

    def _merge_parallel_results(
        self,
        page_results: Dict[int, Dict[str, Any]],
        output_mode: str,
        errors: List[str],
    ) -> Dict[str, Any]:
        """병렬 처리 결과를 하나로 병합"""
        import json
        import re

        # 페이지 순서대로 정렬
        sorted_pages = sorted(page_results.items(), key=lambda x: x[0])

        # 텍스트 콘텐츠 합치기
        all_content = []
        financial_tables = {
            "income_statement": {"found": False},
            "balance_sheet": {"found": False},
            "cash_flow": {"found": False},
            "cap_table": {"found": False},
        }
        investment_terms = {"found": False}
        company_info = {}
        visual_elements = []

        for page_idx, result in sorted_pages:
            if not result.get("success"):
                all_content.append(f"\n============ 페이지 {page_idx + 1} (처리 실패) ============\n")
                continue

            raw_content = result.get("content", "")

            if output_mode == "text_only":
                all_content.append(f"\n============ 페이지 {page_idx + 1} ============\n{raw_content}")
            else:
                # JSON 파싱 시도
                try:
                    json_match = re.search(r"```json\s*(.*?)\s*```", raw_content, re.DOTALL)
                    if json_match:
                        parsed = json.loads(json_match.group(1))
                    else:
                        parsed = json.loads(raw_content.strip())

                    # 콘텐츠 추가
                    page_content = parsed.get("content", raw_content)
                    all_content.append(f"\n============ 페이지 {page_idx + 1} ============\n{page_content}")

                    # 재무 데이터 병합
                    if parsed.get("has_financial_data"):
                        fin_type = parsed.get("financial_type", "")
                        if fin_type in financial_tables and parsed.get("financial_data"):
                            financial_tables[fin_type] = {
                                "found": True,
                                "page": page_idx + 1,
                                **parsed.get("financial_data", {}),
                            }

                    # 투자조건 병합
                    if parsed.get("has_investment_terms") and parsed.get("investment_terms"):
                        investment_terms = {
                            "found": True,
                            "page": page_idx + 1,
                            **parsed.get("investment_terms", {}),
                        }

                    # Cap Table 병합
                    if parsed.get("has_cap_table") and parsed.get("cap_table"):
                        financial_tables["cap_table"] = {
                            "found": True,
                            "page": page_idx + 1,
                            **parsed.get("cap_table", {}),
                        }

                    # 시각 요소 수집
                    if parsed.get("visual_elements"):
                        for elem in parsed["visual_elements"]:
                            visual_elements.append(f"p{page_idx + 1}: {elem}")

                except json.JSONDecodeError:
                    all_content.append(f"\n============ 페이지 {page_idx + 1} ============\n{raw_content}")

        merged_content = "".join(all_content)

        result = {
            "content": merged_content,
            "structured_content": {
                "company_info": company_info,
                "visual_elements": visual_elements,
            },
            "financial_tables": financial_tables,
            "investment_terms": investment_terms,
            "parallel_processing": {
                "total_pages": len(page_results),
                "successful_pages": len([r for r in page_results.values() if r.get("success")]),
                "failed_pages": len([r for r in page_results.values() if not r.get("success")]),
                "errors": errors,
            },
        }

        return result

    def _get_text_only_prompt(self) -> str:
        return """위 PDF 페이지들의 내용을 텍스트로 추출해주세요.

규칙:
1. 각 페이지를 "============ 페이지 N ============" 형식으로 구분
2. 테이블은 마크다운 테이블 형식으로 변환
3. 원본 레이아웃과 순서를 최대한 보존
4. 숫자와 단위를 정확하게 추출 (억원, 백만원 등)

텍스트만 출력하고 다른 설명은 하지 마세요."""

    def _get_structured_prompt(self) -> str:
        return """위 PDF 페이지들을 투자심사 관점에서 철저히 분석하여 다음 JSON 형식으로 추출해주세요.

```json
{
  "content": "전체 텍스트 (페이지별 ===페이지 N=== 구분)",

  "company_info": {
    "name": "회사명",
    "industry": "산업/업종",
    "founded": "설립연도",
    "employees": 직원수,
    "business_model": "비즈니스 모델 요약"
  },

  "investment_terms": {
    "found": true/false,
    "page": 페이지번호,
    "investment_amount": 투자금액(원),
    "pre_money_valuation": Pre-money(원),
    "post_money_valuation": Post-money(원),
    "price_per_share": 주당가격(원),
    "shares_acquired": 취득주식수,
    "ownership_percentage": 취득지분율,
    "investment_type": "보통주/우선주/CB/SAFE",
    "investment_round": "시드/프리A/시리즈A/B/C",
    "special_terms": ["청산우선권", "희석방지", "동반매각권"]
  },

  "financial_tables": {
    "income_statement": {
      "found": true/false,
      "page": 페이지번호,
      "unit": "억원/백만원/천원",
      "source": "회사제시/심사역추정/컨센서스",
      "years": ["2023", "2024E", "2025E", "2026E"],
      "metrics": {
        "revenue": [매출액들],
        "revenue_growth_yoy": [YoY성장률들],
        "gross_profit": [매출총이익들],
        "gross_margin": [매출총이익률들],
        "operating_income": [영업이익들],
        "operating_margin": [영업이익률들],
        "ebitda": [EBITDA들],
        "net_income": [당기순이익들]
      }
    },
    "balance_sheet": {
      "found": true/false,
      "page": 페이지번호,
      "unit": "억원/백만원/천원",
      "years": ["2023", "2024E"],
      "metrics": {
        "total_assets": [총자산들],
        "current_assets": [유동자산들],
        "total_liabilities": [총부채들],
        "total_equity": [자본총계들],
        "cash_and_equivalents": [현금및현금성자산들],
        "debt": [차입금들]
      }
    },
    "cash_flow": {
      "found": true/false,
      "page": 페이지번호,
      "metrics": {
        "operating_cf": [영업활동CF들],
        "investing_cf": [투자활동CF들],
        "financing_cf": [재무활동CF들],
        "free_cash_flow": [FCF들]
      }
    },
    "cap_table": {
      "found": true/false,
      "page": 페이지번호,
      "total_shares_issued": 총발행주식수,
      "shareholders": [
        {
          "name": "주주명",
          "shares": 보유주식수,
          "percentage": 지분율,
          "share_type": "보통주/우선주"
        }
      ],
      "option_pool": {
        "allocated": 부여된스톡옵션수,
        "remaining": 잔여풀
      }
    }
  },

  "valuation_metrics": {
    "per": PER배수,
    "psr": PSR배수,
    "ev_ebitda": EV/EBITDA배수,
    "ev_revenue": EV/Revenue배수
  },

  "data_validation": {
    "yoy_growth_check": [
      {
        "metric": "revenue",
        "year_from": "2023",
        "year_to": "2024E",
        "value_from": 이전값,
        "value_to": 이후값,
        "calculated_growth": 계산된성장률,
        "stated_growth": IR자료에명시된성장률_또는_null,
        "match": true/false,
        "discrepancy": "차이가 있으면 설명"
      }
    ],
    "margin_consistency": [
      {
        "metric": "operating_margin",
        "year": "2024E",
        "calculated": 영업이익/매출*100,
        "stated": IR자료에명시된값,
        "match": true/false
      }
    ],
    "cap_table_check": {
      "sum_of_shares": 주주별보유주식합계,
      "total_shares_stated": 총발행주식수,
      "match": true/false
    },
    "valuation_check": {
      "pre_money_stated": Pre-money(IR자료),
      "calculated_from_per": 당기순이익*PER,
      "calculated_from_psr": 매출*PSR,
      "reasonable": true/false,
      "notes": "밸류에이션 정합성 코멘트"
    }
  },

  "key_risks": ["리스크1", "리스크2"],

  "warnings": ["불완전하거나 불확실한 데이터에 대한 경고"],

  "data_source_labels": {
    "financial_data": "회사제시/심사역추정/외부자료",
    "valuation": "회사제시/시장가격",
    "cap_table": "회사제시/등기부등본"
  },

  "missing_data": {
    "has_missing": true/false,
    "critical_missing": [
      {
        "field": "income_statement",
        "reason": "손익계산서를 찾을 수 없습니다",
        "suggestion": "재무제표가 포함된 페이지를 업로드해주세요",
        "priority": "high"
      },
      {
        "field": "cap_table",
        "reason": "주주현황 정보가 없습니다",
        "suggestion": "Cap Table 또는 주주명부를 업로드해주세요",
        "priority": "high"
      },
      {
        "field": "investment_terms",
        "reason": "투자조건이 명시되어 있지 않습니다",
        "suggestion": "텀싯(Term Sheet) 또는 투자계약서를 업로드해주세요",
        "priority": "medium"
      }
    ],
    "optional_missing": [
      {
        "field": "cash_flow",
        "reason": "현금흐름표가 없습니다 (선택사항)",
        "priority": "low"
      }
    ],
    "request_message": "투자 분석을 위해 다음 자료가 추가로 필요합니다:\n1. [필수] 재무제표 (손익계산서)\n2. [필수] Cap Table\n\n파일을 업로드하거나 텍스트로 입력해주세요."
  }
}
```

## 추출 규칙

1. **숫자 변환**: 모든 금액은 원화 기준 정수로 변환
   - "100억" → 10000000000
   - "5천만원" → 50000000
   - 표에 단위가 명시되어 있으면 (단위: 백만원) 해당 단위 적용

2. **연도 표기**: 추정치는 "E" 붙여서 표시 (2024E, 2025E)

3. **비율**: 퍼센트는 숫자 그대로 (15.5% → 15.5)

4. **누락 데이터**: 찾을 수 없는 필드는 null, 테이블 자체가 없으면 found: false

5. **다중 시나리오**: 회사제시/심사역추정이 다르면 source 필드로 구분

6. **정합성 검증 (매우 중요)**:
   - YoY 성장률: 직접 계산한 값과 IR자료에 명시된 값 비교
   - 마진율: 영업이익÷매출 계산값과 명시된 값 비교
   - Cap Table: 주주별 지분 합계 = 100% 확인
   - 밸류에이션: PER/PSR 역산값과 제시 밸류에이션 비교

7. **데이터 출처 명시**: 각 데이터가 회사제시/심사역추정/외부자료 중 어디서 왔는지 표시

8. **JSON만 출력**: 다른 설명 없이 순수 JSON만 반환"""

    def _get_tables_only_prompt(self) -> str:
        return """위 PDF 페이지들에서 테이블만 추출하여 다음 JSON 형식으로 출력해주세요:

```json
{
  "tables": [
    {
      "page": 페이지번호,
      "title": "테이블 제목 (있으면)",
      "markdown": "| 열1 | 열2 |\\n|---|---|\\n| 값1 | 값2 |",
      "rows": [["헤더1", "헤더2"], ["값1", "값2"]]
    }
  ],
  "financial_tables": {
    "income_statement": {...},
    "balance_sheet": {...},
    "cash_flow": {...},
    "cap_table": {...}
  }
}
```

규칙:
1. 모든 테이블을 빠짐없이 추출
2. 재무제표는 financial_tables에 별도 구조화
3. 숫자와 단위를 정확하게 추출
4. JSON만 출력"""

    def _parse_claude_response(
        self, response_text: str, output_mode: str
    ) -> Dict[str, Any]:
        """Claude 응답 파싱"""
        import json
        import re

        if output_mode == "text_only":
            return {"content": response_text}

        # JSON 추출 시도
        try:
            # ```json ... ``` 블록 추출
            json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 전체가 JSON인 경우
                json_str = response_text.strip()

            parsed = json.loads(json_str)

            return {
                "content": parsed.get("content", response_text),
                "structured_content": parsed.get("structured_content", {}),
                "financial_tables": parsed.get("financial_tables", {}),
            }

        except json.JSONDecodeError:
            logger.warning("JSON 파싱 실패, 텍스트로 반환")
            return {"content": response_text}

    def _fallback_to_pymupdf(
        self, pdf_path: str, max_pages: int, reason: str
    ) -> Dict[str, Any]:
        """PyMuPDF로 폴백"""
        logger.info(f"PyMuPDF로 폴백: {reason}")

        try:
            import fitz

            doc = None
            try:
                doc = fitz.open(pdf_path)
                total_pages = len(doc)
                pages_to_read = min(total_pages, max_pages)

                text_content = []
                for i in range(pages_to_read):
                    page = doc[i]
                    text = page.get_text()
                    text_content.append(
                        f"\n{'='*60}\n페이지 {i+1}\n{'='*60}\n{text}"
                    )

                content = "".join(text_content)

                return {
                    "success": True,
                    "file_path": pdf_path,
                    "total_pages": total_pages,
                    "pages_read": pages_to_read,
                    "content": content,
                    "char_count": len(content),
                    "processing_method": "pymupdf_fallback",
                    "fallback_used": True,
                    "fallback_reason": reason,
                    "cache_hit": False,
                    "cached_at": datetime.utcnow().isoformat(),
                }

            finally:
                if doc:
                    doc.close()

        except Exception as e:
            logger.error(f"폴백 처리도 실패: {e}")
            return {
                "success": False,
                "error": f"PDF 처리 실패: {str(e)}",
                "fallback_attempted": True,
                "original_error": reason,
            }

    def _emit_progress(
        self,
        callback: Optional[Callable],
        stage: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """진행 상황 이벤트 발생"""
        if callback:
            event = {
                "type": "info",
                "content": message,
                "data": {"stage": stage, **(data or {})},
            }
            try:
                callback(event)
            except Exception as e:
                logger.warning(f"진행 콜백 실패: {e}")


# 기존 DolphinProcessor를 ClaudeVisionProcessor로 대체
DolphinProcessor = ClaudeVisionProcessor


def process_pdf_with_claude(
    pdf_path: str,
    max_pages: int = None,
    output_mode: str = "structured",
    progress_callback: Optional[Callable] = None,
    parallel: bool = True,
    max_workers: int = 10,
) -> Dict[str, Any]:
    """PDF를 Claude Vision으로 처리하는 편의 함수

    Args:
        pdf_path: PDF 파일 경로
        max_pages: 최대 처리 페이지 수
        output_mode: 출력 모드 (text_only, structured, tables_only)
        progress_callback: 진행 상황 콜백 함수
        parallel: True면 페이지를 병렬로 처리 (기본값: True, 최대 3배 빠름)
        max_workers: 병렬 처리 시 최대 워커 수 (기본값: 10)
    """
    processor = ClaudeVisionProcessor()
    return processor.process_pdf(
        pdf_path=pdf_path,
        max_pages=max_pages,
        output_mode=output_mode,
        progress_callback=progress_callback,
        parallel=parallel,
        max_workers=max_workers,
    )


# 하위 호환성을 위한 별칭
process_pdf_with_dolphin = process_pdf_with_claude


def process_documents_batch(
    pdf_paths: List[str],
    max_pages_per_pdf: int = 15,
    max_total_images: int = 20,
    output_mode: str = "structured",
    progress_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
    """여러 PDF를 한 번에 합쳐서 단일 API 호출로 처리

    모든 PDF의 이미지를 한 번에 보내고, 단일 쿼리로 전체를 분석합니다.
    페이지별 병렬 처리보다 효율적입니다 (API 호출 1회, 전체 문맥 파악 가능).

    Args:
        pdf_paths: PDF 파일 경로 리스트
        max_pages_per_pdf: PDF당 최대 페이지 수 (기본: 15)
        max_total_images: 전체 최대 이미지 수 (Claude 제한: 20)
        output_mode: 출력 모드 (text_only, structured, tables_only)
        progress_callback: 진행 상황 콜백 함수

    Returns:
        통합된 처리 결과 딕셔너리
    """
    import fitz
    import httpx
    import anthropic

    start_time = time.time()
    processor = ClaudeVisionProcessor()

    def emit_progress(stage: str, message: str):
        if progress_callback:
            processor._emit_progress(progress_callback, stage, message)

    # 1. 모든 PDF를 이미지로 변환하고 합침
    emit_progress("converting", f"{len(pdf_paths)}개 PDF 이미지 변환 중...")

    all_images = []  # (source_file, page_num, base64_image)
    file_page_map = {}  # {source_file: [page_indices in all_images]}

    for pdf_path in pdf_paths:
        filename = Path(pdf_path).name
        file_page_map[filename] = []

        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            pages_to_read = min(total_pages, max_pages_per_pdf)

            for page_idx in range(pages_to_read):
                if len(all_images) >= max_total_images:
                    logger.warning(f"최대 이미지 수 도달 ({max_total_images}), 나머지 페이지 스킵")
                    break

                page = doc[page_idx]
                mat = fitz.Matrix(DOLPHIN_CONFIG.get("image_dpi", 150) / 72, DOLPHIN_CONFIG.get("image_dpi", 150) / 72)
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes("png")
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")

                all_images.append((filename, page_idx + 1, img_b64))
                file_page_map[filename].append(len(all_images) - 1)

            doc.close()

        except Exception as e:
            logger.error(f"PDF 변환 실패 ({pdf_path}): {e}")
            continue

        if len(all_images) >= max_total_images:
            break

    if not all_images:
        return {
            "success": False,
            "error": "이미지 변환에 실패했습니다.",
        }

    # 2. 단일 API 호출로 모든 이미지 처리
    emit_progress("processing", f"Claude Opus로 {len(all_images)}개 이미지 일괄 분석 중...")

    # 이미지 소스 정보를 포함한 프롬프트
    source_info = []
    for idx, (filename, page_num, _) in enumerate(all_images):
        source_info.append(f"이미지 {idx + 1}: {filename} 페이지 {page_num}")
    source_info_text = "\n".join(source_info)

    extraction_prompt = f"""다음은 투자 검토를 위해 업로드된 여러 문서의 페이지들입니다.

[문서-페이지 매핑]
{source_info_text}

위 모든 페이지를 종합 분석하여 투자심사에 필요한 정보를 추출해주세요.
페이지 순서나 문서 구분에 관계없이, 전체를 하나의 투자 대상 기업 자료로 보고 분석합니다.

다음 JSON 형식으로 출력하세요:

```json
{{
  "company_info": {{
    "name": "회사명",
    "industry": "업종",
    "founded_year": 설립연도,
    "business_model": "비즈니스 모델 요약"
  }},
  "content": "전체 문서 텍스트 (테이블은 마크다운으로)",
  "investment_terms": {{
    "found": true/false,
    "source": "파일명 p.X",
    "amount": "투자금액",
    "pre_money": "Pre-money 밸류",
    "post_money": "Post-money 밸류",
    "price_per_share": "주당가격",
    "shares_acquired": "취득주식수",
    "ownership_pct": "취득지분율",
    "investment_type": "투자구조 (보통주/전환사채/SAFE 등)"
  }},
  "financial_tables": {{
    "income_statement": {{
      "found": true/false,
      "source": "파일명 p.X",
      "unit": "억원/백만원",
      "years": ["2023", "2024E", "2025E"],
      "metrics": {{
        "revenue": [매출액들],
        "gross_profit": [매출총이익들],
        "operating_income": [영업이익들],
        "net_income": [당기순이익들]
      }}
    }},
    "balance_sheet": {{
      "found": true/false,
      "source": "파일명 p.X",
      "unit": "억원/백만원",
      "years": ["2023", "2024E"],
      "metrics": {{
        "total_assets": [총자산들],
        "total_liabilities": [총부채들],
        "total_equity": [총자본들],
        "cash": [현금성자산들]
      }}
    }},
    "cash_flow": {{
      "found": true/false,
      "source": "파일명 p.X"
    }},
    "cap_table": {{
      "found": true/false,
      "source": "파일명 p.X",
      "total_shares": 총발행주식수,
      "shareholders": [
        {{"name": "주주명", "ownership_pct": "지분율", "shares": 주식수}}
      ]
    }}
  }},
  "key_highlights": ["핵심 포인트 1", "핵심 포인트 2"],
  "risks": ["리스크 1", "리스크 2"],
  "missing_data": ["누락된 중요 정보"]
}}
```

규칙:
1. 여러 문서에서 같은 정보가 있으면 가장 최신/상세한 것을 사용
2. 모든 수치에는 source (파일명 p.페이지) 명시
3. 추정값은 [추정]으로 표기
4. JSON만 출력"""

    # API 호출을 위한 content 구성
    content = []
    for filename, page_num, img_b64 in all_images:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": img_b64,
            },
        })

    content.append({
        "type": "text",
        "text": extraction_prompt,
    })

    try:
        timeout_config = httpx.Timeout(
            timeout=DOLPHIN_CONFIG.get("timeout_seconds", 300),
            connect=30.0,
        )
        client = anthropic.Anthropic(timeout=timeout_config)

        response = client.messages.create(
            model="claude-opus-4-20250514",
            max_tokens=16384,
            system=processor._get_system_prompt(),
            messages=[{"role": "user", "content": content}]
        )

        response_text = response.content[0].text if response.content else ""

    except Exception as e:
        logger.error(f"Claude API 호출 실패: {e}")
        return {
            "success": False,
            "error": f"API 호출 실패: {str(e)}",
        }

    # 3. 응답 파싱
    emit_progress("parsing", "결과 파싱 중...")

    parsed = processor._parse_claude_response(response_text, output_mode)

    processing_time = time.time() - start_time

    result = {
        "success": True,
        "source_files": [Path(p).name for p in pdf_paths],
        "total_images": len(all_images),
        "file_page_map": {k: len(v) for k, v in file_page_map.items()},
        "content": parsed.get("content", response_text),
        "char_count": len(parsed.get("content", "")),
        "structured_content": parsed.get("structured_content", {}),
        "financial_tables": parsed.get("financial_tables", {}),
        "investment_terms": parsed.get("investment_terms", {}),
        "company_info": parsed.get("company_info", {}),
        "processing_method": "claude_opus_batch",
        "processing_time_seconds": processing_time,
    }

    emit_progress("complete", f"완료 ({processing_time:.1f}초, {len(all_images)}개 이미지)")

    return result


class InteractiveAnalysisSession:
    """대화형 투자 분석 세션

    여러 파일과 텍스트 입력을 받아서 점진적으로 분석을 완성합니다.
    """

    def __init__(self, session_id: str = None):
        self.session_id = session_id or datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self.processor = ClaudeVisionProcessor()
        self.accumulated_data = {
            "company_info": {},
            "investment_terms": {"found": False},
            "financial_tables": {
                "income_statement": {"found": False},
                "balance_sheet": {"found": False},
                "cash_flow": {"found": False},
                "cap_table": {"found": False},
            },
            "valuation_metrics": {},
            "source_files": [],
            "text_inputs": [],
        }
        self.missing_data = []

    def add_pdf(self, pdf_path: str, max_pages: int = 30) -> Dict[str, Any]:
        """PDF 파일 추가 및 분석"""
        result = self.processor.process_pdf(
            pdf_path=pdf_path,
            max_pages=max_pages,
            output_mode="structured",
        )

        if result.get("success"):
            self._merge_data(result)
            self.accumulated_data["source_files"].append(pdf_path)

        return self._get_status()

    def add_text_input(self, text: str, data_type: str = "general") -> Dict[str, Any]:
        """텍스트 입력 추가 (재무 데이터, Cap Table 등)

        Args:
            text: 사용자가 입력한 텍스트
            data_type: "financial", "cap_table", "investment_terms", "general"
        """
        import json
        import re
        import anthropic

        try:
            client = anthropic.Anthropic()
            prompt = self._get_text_parsing_prompt(text, data_type)

            response = client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=4096,
                system=self.processor._get_system_prompt(),
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text
            json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(1))
            else:
                parsed = json.loads(response_text.strip())

            self._merge_parsed_text(parsed, data_type)
            self.accumulated_data["text_inputs"].append({
                "type": data_type,
                "content": text[:500],  # 요약 저장
            })

        except anthropic.APIConnectionError as e:
            logger.error(f"API 연결 실패: {e}")
            return {
                "success": False,
                "error": "API 연결에 실패했습니다. 네트워크를 확인해주세요.",
            }
        except anthropic.RateLimitError as e:
            logger.error(f"Rate limit: {e}")
            return {
                "success": False,
                "error": "API 호출 한도에 도달했습니다. 잠시 후 다시 시도해주세요.",
            }
        except anthropic.APIStatusError as e:
            logger.error(f"API 오류: {e}")
            return {
                "success": False,
                "error": f"API 오류: {e.message}",
            }
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 파싱 실패: {e}")
            return {
                "success": False,
                "error": "응답 파싱에 실패했습니다. 다시 시도해주세요.",
            }
        except Exception as e:
            logger.exception("텍스트 입력 처리 실패")
            return {
                "success": False,
                "error": f"처리 실패: {str(e)}",
            }

        return self._get_status()

    def _get_text_parsing_prompt(self, text: str, data_type: str) -> str:
        """텍스트 파싱용 프롬프트 생성"""
        base_prompt = f"""다음 텍스트에서 투자 분석에 필요한 정보를 추출해주세요.

텍스트:
{text}

"""
        if data_type == "financial":
            base_prompt += """
재무 정보를 다음 JSON 형식으로 추출:
```json
{
  "income_statement": {
    "found": true,
    "years": ["2023", "2024E"],
    "metrics": {
      "revenue": [값들],
      "operating_income": [값들],
      "net_income": [값들]
    }
  }
}
```"""
        elif data_type == "cap_table":
            base_prompt += """
Cap Table을 다음 JSON 형식으로 추출:
```json
{
  "cap_table": {
    "found": true,
    "total_shares_issued": 총주식수,
    "shareholders": [
      {"name": "주주명", "shares": 주식수, "percentage": 지분율}
    ]
  }
}
```"""
        elif data_type == "investment_terms":
            base_prompt += """
투자 조건을 다음 JSON 형식으로 추출:
```json
{
  "investment_terms": {
    "found": true,
    "investment_amount": 투자금액,
    "pre_money_valuation": Pre-money,
    "price_per_share": 주당가격,
    "investment_type": "보통주/우선주/CB"
  }
}
```"""
        else:
            base_prompt += """
관련 정보를 JSON 형식으로 추출해주세요.
```json
{
  "extracted_info": {...}
}
```"""

        return base_prompt

    def _merge_data(self, new_data: Dict[str, Any]) -> None:
        """새로운 데이터를 기존 데이터와 병합"""
        # 회사 정보
        if new_data.get("company_info"):
            self.accumulated_data["company_info"].update(new_data["company_info"])

        # 투자 조건
        if new_data.get("investment_terms", {}).get("found"):
            self.accumulated_data["investment_terms"] = new_data["investment_terms"]

        # 재무 테이블
        financial = new_data.get("financial_tables", {})
        for table_type in ["income_statement", "balance_sheet", "cash_flow", "cap_table"]:
            if financial.get(table_type, {}).get("found"):
                self.accumulated_data["financial_tables"][table_type] = financial[table_type]

        # 밸류에이션 지표
        if new_data.get("valuation_metrics"):
            self.accumulated_data["valuation_metrics"].update(new_data["valuation_metrics"])

    def _merge_parsed_text(self, parsed: Dict[str, Any], data_type: str) -> None:
        """파싱된 텍스트 데이터 병합"""
        if data_type == "financial" and parsed.get("income_statement"):
            self.accumulated_data["financial_tables"]["income_statement"] = parsed["income_statement"]
        elif data_type == "cap_table" and parsed.get("cap_table"):
            self.accumulated_data["financial_tables"]["cap_table"] = parsed["cap_table"]
        elif data_type == "investment_terms" and parsed.get("investment_terms"):
            self.accumulated_data["investment_terms"] = parsed["investment_terms"]

    def _get_status(self) -> Dict[str, Any]:
        """현재 분석 상태 반환"""
        missing = []
        critical_missing = []

        # 필수 데이터 체크
        if not self.accumulated_data["financial_tables"]["income_statement"].get("found"):
            critical_missing.append({
                "field": "income_statement",
                "name": "손익계산서",
                "suggestion": "재무제표 PDF를 업로드하거나, 매출/영업이익/순이익을 텍스트로 입력해주세요.\n예: '2024년 매출 100억, 영업이익 20억, 순이익 15억'",
            })

        if not self.accumulated_data["financial_tables"]["cap_table"].get("found"):
            critical_missing.append({
                "field": "cap_table",
                "name": "Cap Table (주주현황)",
                "suggestion": "Cap Table을 업로드하거나, 주주현황을 텍스트로 입력해주세요.\n예: '대표이사 60%, 투자자A 20%, 스톡옵션풀 20%'",
            })

        if not self.accumulated_data["investment_terms"].get("found"):
            missing.append({
                "field": "investment_terms",
                "name": "투자 조건",
                "suggestion": "투자금액, 밸류에이션, 주당가격 등을 입력해주세요.\n예: '투자금액 30억, Pre-money 100억, 주당가격 10,000원'",
            })

        # 상태 메시지 생성
        if critical_missing:
            status = "incomplete"
            message = "🔴 필수 데이터가 부족합니다:\n"
            for item in critical_missing:
                message += f"\n**{item['name']}**\n{item['suggestion']}\n"
        elif missing:
            status = "partial"
            message = "🟡 추가 데이터가 있으면 더 정확한 분석이 가능합니다:\n"
            for item in missing:
                message += f"\n**{item['name']}**\n{item['suggestion']}\n"
        else:
            status = "complete"
            message = "🟢 모든 필수 데이터가 수집되었습니다. 분석 가능합니다."

        return {
            "success": True,
            "session_id": self.session_id,
            "status": status,
            "message": message,
            "critical_missing": critical_missing,
            "optional_missing": missing,
            "accumulated_data": self.accumulated_data,
            "source_count": {
                "files": len(self.accumulated_data["source_files"]),
                "text_inputs": len(self.accumulated_data["text_inputs"]),
            },
        }

    def get_final_analysis(self) -> Dict[str, Any]:
        """최종 분석 결과 반환"""
        status = self._get_status()

        if status["status"] == "incomplete":
            return {
                "success": False,
                "error": "필수 데이터가 부족합니다",
                "missing": status["critical_missing"],
                "message": status["message"],
            }

        return {
            "success": True,
            "session_id": self.session_id,
            "analysis": self.accumulated_data,
            "data_quality": "complete" if status["status"] == "complete" else "partial",
            "warnings": status.get("optional_missing", []),
        }


# 세션 관리 (폴백용 - Streamlit 외부에서 사용)
_active_sessions: Dict[str, InteractiveAnalysisSession] = {}


def _get_streamlit_session_storage() -> Dict[str, InteractiveAnalysisSession]:
    """Streamlit session_state 기반 세션 저장소 반환 (가능한 경우)"""
    try:
        import streamlit as st
        if "analysis_sessions" not in st.session_state:
            st.session_state.analysis_sessions = {}
        return st.session_state.analysis_sessions
    except (ImportError, RuntimeError):
        # Streamlit 외부에서 실행 중이거나 context 없음
        return _active_sessions


def get_or_create_session(session_id: str = None) -> InteractiveAnalysisSession:
    """분석 세션 가져오기 또는 생성

    Streamlit 환경에서는 st.session_state를 사용하여 유저별 세션 분리.
    그 외 환경에서는 모듈 레벨 딕셔너리 사용.
    """
    storage = _get_streamlit_session_storage()

    if session_id and session_id in storage:
        return storage[session_id]

    session = InteractiveAnalysisSession(session_id)
    storage[session.session_id] = session
    return session


def clear_session(session_id: str) -> None:
    """세션 삭제"""
    storage = _get_streamlit_session_storage()
    if session_id in storage:
        del storage[session_id]
