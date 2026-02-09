"""
Policy Analyzer

정부 정책 PDF/아티클을 분석하여 핵심 정책 방향을 추출합니다.
"""

import json
import os
import re
from typing import Dict, Any, List, Optional
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트의 .env 파일 로드 (절대 경로 사용)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from anthropic import Anthropic


class PolicyAnalyzer:
    """
    정부 정책 PDF 분석기

    정부 정책 문서에서 핵심 정책 테마, 예산 배분, 타겟 산업을 추출합니다.
    """

    # 정책 분석용 키워드
    POLICY_KEYWORDS = {
        "budget": ["예산", "조원", "억원", "재정", "투자", "지원금", "R&D"],
        "timeline": ["2025년", "2026년", "2027년", "2028년", "2029년", "2030년",
                     "단계별", "로드맵", "추진일정", "목표연도"],
        "industry": ["산업", "분야", "섹터", "영역", "클러스터", "생태계"],
        "goal": ["목표", "달성", "추진", "확대", "육성", "지원", "강화", "촉진"],
        "priority": ["중점", "핵심", "전략", "우선", "집중", "선도"]
    }

    # 주요 정책 테마 키워드
    THEME_KEYWORDS = {
        "탄소중립": ["탄소중립", "넷제로", "Net Zero", "탄소감축", "온실가스", "기후변화"],
        "디지털전환": ["디지털전환", "디지털 대전환", "DX", "AI", "빅데이터", "클라우드"],
        "그린뉴딜": ["그린뉴딜", "그린 뉴딜", "녹색전환", "녹색성장"],
        "바이오헬스": ["바이오헬스", "바이오", "헬스케어", "의료기기", "제약"],
        "모빌리티": ["모빌리티", "자율주행", "전기차", "수소차", "UAM"],
        "수소경제": ["수소경제", "수소", "그린수소", "수소연료전지"],
        "반도체": ["반도체", "시스템반도체", "파운드리", "팹리스"],
        "이차전지": ["이차전지", "배터리", "ESS", "전고체배터리"],
        "로봇": ["로봇", "서비스로봇", "협동로봇", "로보틱스"],
        "우주항공": ["우주", "항공", "우주항공", "위성", "발사체"],
        "양자": ["양자", "양자컴퓨팅", "양자기술", "양자암호"],
        "메타버스": ["메타버스", "가상현실", "VR", "AR", "XR"],
        "사회적경제": ["사회적경제", "사회적기업", "소셜벤처", "사회적가치"],
        "ESG": ["ESG", "지속가능경영", "친환경", "사회적책임"],
        "스마트시티": ["스마트시티", "스마트도시", "디지털트윈"],
        "핀테크": ["핀테크", "디지털금융", "오픈뱅킹", "마이데이터"],
        "푸드테크": ["푸드테크", "대체식품", "식품기술", "스마트팜"],
        "에듀테크": ["에듀테크", "디지털교육", "이러닝", "AI튜터"],
        "K-콘텐츠": ["K-콘텐츠", "콘텐츠산업", "OTT", "게임", "웹툰"]
    }

    def __init__(self, api_key: str = None):
        """
        PolicyAnalyzer 초기화

        Args:
            api_key: Anthropic API 키 (없으면 환경변수에서 로드)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=self.api_key) if self.api_key else None

    def analyze_content(
        self,
        pdf_paths: List[str] = None,
        text_content: str = None,
        focus_keywords: List[str] = None,
        max_pages: int = 30
    ) -> Dict[str, Any]:
        """
        PDF 또는 텍스트 콘텐츠를 분석하여 정책 방향 추출

        Args:
            pdf_paths: PDF 파일 경로 리스트 (선택)
            text_content: 분석할 텍스트 (선택)
            focus_keywords: 집중 분석할 키워드
            max_pages: PDF당 최대 페이지 수

        Returns:
            정책 분석 결과
        """
        all_texts = []
        sources = []

        # PDF 분석
        if pdf_paths:
            for pdf_path in pdf_paths:
                try:
                    text = self._extract_pdf_text(pdf_path, max_pages)
                    if text:
                        all_texts.append({
                            "file": Path(pdf_path).name,
                            "text": text
                        })
                        sources.append({
                            "file": Path(pdf_path).name,
                            "path": pdf_path,
                            "type": "pdf"
                        })
                except Exception as e:
                    sources.append({
                        "file": Path(pdf_path).name,
                        "error": str(e)
                    })

        # 텍스트 콘텐츠 추가
        if text_content and text_content.strip():
            all_texts.append({
                "file": "직접 입력 텍스트",
                "text": text_content.strip()
            })
            sources.append({
                "file": "직접 입력 텍스트",
                "type": "text",
                "length": len(text_content.strip())
            })

        if not all_texts:
            return {
                "success": False,
                "error": "분석할 콘텐츠가 없습니다"
            }

        # Claude 또는 로컬 분석
        if self.client:
            analysis = self._analyze_with_claude(all_texts, focus_keywords)
            if not analysis.get("success"):
                fallback = self._analyze_local(all_texts, focus_keywords)
                fallback["warnings"] = [f"Claude 분석 실패: {analysis.get('error')}"]
                fallback["fallback_used"] = True
                analysis = fallback
        else:
            analysis = self._analyze_local(all_texts, focus_keywords)
        analysis["sources"] = sources
        analysis["source_reliability"] = self._calculate_source_reliability(sources)

        return analysis

    def analyze_multiple_pdfs(
        self,
        pdf_paths: List[str],
        focus_keywords: List[str] = None,
        max_pages: int = 30
    ) -> Dict[str, Any]:
        """
        여러 PDF를 분석하여 통합 정책 방향 추출

        Args:
            pdf_paths: PDF 파일 경로 리스트
            focus_keywords: 집중 분석할 키워드 (선택)
            max_pages: PDF당 최대 페이지 수

        Returns:
            {
                "success": bool,
                "policy_themes": ["탄소중립", "디지털전환", ...],
                "target_industries": ["신재생에너지", "AI", ...],
                "budget_info": {"탄소중립": "50조원", ...},
                "timeline": {"2025": [...], "2030": [...]},
                "key_policies": [{"name": "...", "description": "...", "source": "..."}],
                "sources": [{"file": "...", "pages_analyzed": N}]
            }
        """
        if not pdf_paths:
            return {
                "success": False,
                "error": "분석할 PDF 파일이 없습니다"
            }

        # 각 PDF 분석
        all_texts = []
        sources = []

        for pdf_path in pdf_paths:
            try:
                text = self._extract_pdf_text(pdf_path, max_pages)
                if text:
                    all_texts.append({
                        "file": Path(pdf_path).name,
                        "text": text
                    })
                    sources.append({
                        "file": Path(pdf_path).name,
                        "path": pdf_path,
                        "pages_analyzed": min(max_pages, 50)  # 예상치
                    })
            except Exception as e:
                sources.append({
                    "file": Path(pdf_path).name,
                    "path": pdf_path,
                    "error": str(e)
                })

        if not all_texts:
            return {
                "success": False,
                "error": "PDF에서 텍스트를 추출할 수 없습니다",
                "sources": sources
            }

        # Claude 또는 로컬 분석
        if self.client:
            analysis = self._analyze_with_claude(all_texts, focus_keywords)
            if not analysis.get("success"):
                fallback = self._analyze_local(all_texts, focus_keywords)
                fallback["warnings"] = [f"Claude 분석 실패: {analysis.get('error')}"]
                fallback["fallback_used"] = True
                analysis = fallback
        else:
            analysis = self._analyze_local(all_texts, focus_keywords)
        analysis["sources"] = sources
        analysis["source_reliability"] = self._calculate_source_reliability(sources)

        return analysis

    def _extract_pdf_text(self, pdf_path: str, max_pages: int) -> str:
        """
        PDF에서 텍스트 추출
        1차: PyMuPDF로 텍스트 추출
        2차: 텍스트가 부족하면 Claude Vision 사용
        """
        import fitz  # PyMuPDF

        # 1차: PyMuPDF로 텍스트 추출
        try:
            doc = fitz.open(pdf_path)
            texts = []
            total_pages = min(len(doc), max_pages)

            for page_num in range(total_pages):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    texts.append(f"[페이지 {page_num + 1}]\n{text}")

            doc.close()
            extracted_text = "\n\n".join(texts)

            # 텍스트가 충분한지 체크 (페이지당 평균 200자 이상이면 OK)
            min_chars = total_pages * 200
            if len(extracted_text) >= min_chars:
                return extracted_text

            # 텍스트가 부족하면 Claude Vision으로 폴백
            if not self.client:
                return extracted_text
            print(f"텍스트 부족 ({len(extracted_text)}자 < {min_chars}자), Claude Vision 사용")

        except Exception as e:
            if not self.client:
                return ""
            print(f"PyMuPDF 추출 실패: {e}, Claude Vision 사용")

        # 2차: Claude Vision 사용
        return self._extract_with_vision(pdf_path, max_pages)

    def _extract_with_vision(self, pdf_path: str, max_pages: int) -> str:
        """Claude Vision으로 PDF 텍스트 추출"""
        if not self.client:
            return ""
        import fitz
        import base64

        doc = fitz.open(pdf_path)
        all_text = []

        for page_num in range(min(len(doc), max_pages)):
            page = doc[page_num]

            # 페이지를 이미지로 변환
            mat = fitz.Matrix(2, 2)  # 2x 해상도
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")

            # Claude Vision API 호출
            try:
                response = self.client.messages.create(
                    model="claude-opus-4-6",
                    max_tokens=4000,
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": img_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": "이 페이지의 모든 텍스트를 추출해주세요. 표가 있으면 마크다운 표 형식으로 변환해주세요. 텍스트만 출력하세요."
                            }
                        ]
                    }]
                )
                page_text = response.content[0].text
                all_text.append(f"[페이지 {page_num + 1}]\n{page_text}")

            except Exception as e:
                all_text.append(f"[페이지 {page_num + 1}]\n(추출 실패: {str(e)})")

        doc.close()
        return "\n\n".join(all_text)

    def _calculate_source_reliability(self, sources: List[Dict[str, Any]]) -> List[float]:
        reliability = []
        for source in sources:
            if source.get("error"):
                reliability.append(0.3)
                continue
            source_type = source.get("type", "pdf")
            if source_type == "pdf":
                reliability.append(0.8)
            elif source_type == "text":
                reliability.append(0.6)
            else:
                reliability.append(0.5)
        return reliability

    def _analyze_with_claude(
        self,
        texts: List[Dict[str, str]],
        focus_keywords: List[str] = None
    ) -> Dict[str, Any]:
        """Claude로 정책 문서 분석"""

        # 텍스트 통합 (최대 토큰 제한 고려)
        combined_text = ""
        for item in texts:
            file_text = f"\n\n=== {item['file']} ===\n{item['text']}"
            # 대략 100,000자 제한 (Claude 컨텍스트 고려)
            if len(combined_text) + len(file_text) > 100000:
                combined_text += f"\n\n=== {item['file']} ===\n[텍스트가 너무 길어 생략됨]"
            else:
                combined_text += file_text

        focus_str = ""
        if focus_keywords:
            focus_str = f"\n\n특히 다음 키워드에 집중하여 분석하세요: {', '.join(focus_keywords)}"

        prompt = f"""당신은 정부 정책 분석 전문가입니다. 다음 정부 정책 문서들을 분석하여 핵심 정보를 추출하세요.
{focus_str}

## 분석 대상 문서:
{combined_text}

## 분석 요청 사항:

1. **정책 테마 (policy_themes)**: 문서에서 확인되는 주요 정책 테마를 추출하세요.
   예: 탄소중립, 디지털전환, 바이오헬스, 모빌리티 등

2. **타겟 산업 (target_industries)**: 정책에서 육성/지원 대상으로 명시된 산업들을 추출하세요.
   예: 신재생에너지, AI/빅데이터, 2차전지, 바이오의약품 등

3. **예산 정보 (budget_info)**: 각 정책/산업별 예산 배분 정보를 추출하세요.
   예: {{"탄소중립": "2030년까지 50조원", "디지털뉴딜": "2025년까지 10조원"}}

4. **추진 일정 (timeline)**: 연도별 주요 목표와 계획을 추출하세요.
   예: {{"2025": ["탄소중립 기반구축", "디지털 전환 가속"], "2030": ["탄소배출 40% 감축"]}}

5. **핵심 정책 (key_policies)**: 구체적인 정책명과 설명을 추출하세요.
   각 정책에 대해 name, description, source(출처 문서명), budget(있으면) 포함

6. **정책 방향 요약 (summary)**: 전체 정책 방향을 2-3문장으로 요약하세요.

## 출력 형식 (JSON):
```json
{{
  "success": true,
  "policy_themes": ["테마1", "테마2"],
  "target_industries": ["산업1", "산업2"],
  "budget_info": {{"정책/산업": "예산규모"}},
  "timeline": {{"연도": ["목표1", "목표2"]}},
  "key_policies": [
    {{
      "name": "정책명",
      "description": "설명",
      "source": "출처문서",
      "budget": "예산규모 (있으면)"
    }}
  ],
  "summary": "전체 정책 방향 요약"
}}
```

중요: 문서에 명시적으로 언급된 내용만 추출하세요. 추측하지 마세요.
JSON만 출력하세요.
"""

        try:
            response = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.content[0].text

            # JSON 추출
            json_match = re.search(r'```json\s*(.*?)\s*```', result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group(1)

            result = json.loads(result_text)
            result["success"] = True

            return result

        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON 파싱 오류: {str(e)}",
                "raw_response": result_text[:500] if 'result_text' in locals() else None
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"분석 오류: {str(e)}"
            }

    def _analyze_local(
        self,
        texts: List[Dict[str, str]],
        focus_keywords: List[str] = None
    ) -> Dict[str, Any]:
        combined_text = " ".join(item.get("text", "") for item in texts)
        themes = self.extract_themes(combined_text)
        if focus_keywords:
            for keyword in focus_keywords:
                if keyword not in themes and keyword in combined_text:
                    themes.append(keyword)

        theme_to_industry = {
            "탄소중립": ["신재생에너지", "탄소포집", "ESS", "그린수소"],
            "디지털전환": ["AI", "클라우드", "빅데이터", "사이버보안"],
            "바이오헬스": ["신약개발", "의료기기", "디지털헬스", "진단기기"],
            "모빌리티": ["자율주행", "전기차", "UAM", "스마트물류"],
            "수소경제": ["그린수소", "수소연료전지", "수소충전소", "수소저장"],
            "반도체": ["시스템반도체", "AI반도체", "파운드리", "첨단패키징"],
            "이차전지": ["배터리소재", "전고체배터리", "배터리재활용", "BMS"],
            "ESG": ["ESG플랫폼", "탄소회계", "지속가능금융", "임팩트측정"],
            "푸드테크": ["스마트팜", "대체식품", "푸드AI", "식품물류"],
        }

        target_industries = []
        for theme in themes:
            for industry in theme_to_industry.get(theme, []):
                if industry not in target_industries:
                    target_industries.append(industry)

        budget_mentions = self.extract_budget_mentions(combined_text)
        budget_info = {}
        if budget_mentions:
            for idx, mention in enumerate(budget_mentions[:5], 1):
                budget_info[f"예산추정{idx}"] = f"{mention['amount']}{mention['unit']}"

        timeline = {}
        for year in re.findall(r"(20\d{2})년", combined_text):
            timeline.setdefault(year, [])

        return {
            "success": True,
            "policy_themes": themes,
            "target_industries": target_industries,
            "budget_info": budget_info,
            "timeline": timeline,
            "key_policies": [],
            "summary": "키워드 기반 로컬 분석 결과입니다. 추가 근거가 필요합니다.",
            "warnings": ["API 사용 불가로 로컬 분석으로 대체됨"],
            "fallback_used": True,
        }

    def extract_themes(self, text: str) -> List[str]:
        """텍스트에서 정책 테마 추출 (키워드 기반)"""
        found_themes = []

        for theme, keywords in self.THEME_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text.lower():
                    if theme not in found_themes:
                        found_themes.append(theme)
                    break

        return found_themes

    def extract_budget_mentions(self, text: str) -> List[Dict[str, str]]:
        """텍스트에서 예산 관련 언급 추출"""
        patterns = [
            r'(\d+(?:,\d+)?(?:\.\d+)?)\s*(조원|억원)',
            r'(약\s*\d+(?:,\d+)?(?:\.\d+)?)\s*(조원|억원)',
            r'(\d+(?:,\d+)?(?:\.\d+)?)\s*(trillion|billion)\s*(?:원|won)?',
        ]

        mentions = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                mentions.append({
                    "amount": match[0],
                    "unit": match[1]
                })

        return mentions
