"""
Industry Recommender

정책 분석과 IRIS+ 매핑 결과를 종합하여 유망 산업을 추천합니다.
"""

import json
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트의 .env 파일 로드 (절대 경로 사용)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from anthropic import Anthropic


class IndustryRecommender:
    """
    유망 산업 추천 엔진

    정책 분석 결과와 IRIS+ 임팩트 매핑을 종합하여
    AC(액셀러레이터)가 집중해야 할 유망 산업을 추천합니다.
    """

    # 산업별 기본 가중치 (정책 우선순위 기반)
    DEFAULT_INDUSTRY_WEIGHTS = {
        "AI/인공지능": 1.2,
        "반도체": 1.2,
        "이차전지": 1.15,
        "바이오헬스": 1.15,
        "수소": 1.1,
        "탄소중립": 1.1,
        "로봇": 1.05,
        "우주항공": 1.05,
        "양자": 1.0,
        "메타버스": 0.95,
    }

    @staticmethod
    def _normalize_label(value: Any) -> Optional[str]:
        """Normalize label-like values into clean strings."""
        if value is None:
            return None
        if isinstance(value, str):
            label = value.strip()
            return label or None
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, dict):
            for key in ("name", "industry", "theme", "label", "title", "value"):
                if key in value:
                    inner = value.get(key)
                    if isinstance(inner, str):
                        label = inner.strip()
                        if label:
                            return label
                    elif isinstance(inner, (int, float)):
                        return str(inner)
            if len(value) == 1:
                inner = next(iter(value.values()))
                if isinstance(inner, str):
                    label = inner.strip()
                    if label:
                        return label
                if isinstance(inner, (int, float)):
                    return str(inner)
            return None
        return str(value).strip() or None

    @classmethod
    def _normalize_string_list(cls, values: Any) -> List[str]:
        """Normalize list-like inputs into a list of strings."""
        normalized: List[str] = []
        if values is None:
            return normalized
        if isinstance(values, list):
            for item in values:
                if isinstance(item, list):
                    for sub_item in item:
                        label = cls._normalize_label(sub_item)
                        if label:
                            normalized.append(label)
                else:
                    label = cls._normalize_label(item)
                    if label:
                        normalized.append(label)
            return normalized
        label = cls._normalize_label(values)
        if label:
            normalized.append(label)
        return normalized

    def __init__(self, api_key: str = None):
        """
        IndustryRecommender 초기화

        Args:
            api_key: Anthropic API 키 (없으면 환경변수에서 로드)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=self.api_key) if self.api_key else None

    def generate_recommendations(
        self,
        policy_analysis: Dict[str, Any],
        iris_mapping: Dict[str, Any],
        interest_areas: List[str] = None,
        top_k: int = 5,
        document_weight: float = 0.7
    ) -> Dict[str, Any]:
        """
        정책 + 임팩트 기반 유망 산업 추천 생성

        Args:
            policy_analysis: PolicyAnalyzer의 분석 결과
            iris_mapping: IRISMapper의 매핑 결과
            interest_areas: 사용자 관심 분야 (가중치 부여)
            top_k: 추천할 산업 수
            document_weight: 정책/문서 기반 가중치 (0~1)

        Returns:
            {
                "success": bool,
                "recommendations": [
                    {
                        "rank": 1,
                        "industry": "탄소포집기술",
                        "total_score": 0.92,
                        "policy_score": 0.95,
                        "impact_score": 0.88,
                        "interest_match": True,
                        "evidence": ["2024 탄소중립기본계획 p.45", ...],
                        "iris_codes": ["OI8590", "PI9374"],
                        "sdgs": [13, 7],
                        "rationale": "설명...",
                        "startup_examples": ["직접공기포집", "탄소저장", ...]
                    }
                ],
                "emerging_areas": [...],
                "caution_areas": [...]
            }
        """
        document_weight = self._sanitize_weight(document_weight, default=0.7)

        # 1. 정책 기반 산업 점수 계산
        policy_scores = self._calculate_policy_scores(policy_analysis)

        # 2. 임팩트 기반 점수 계산
        impact_scores = self._calculate_impact_scores(iris_mapping)

        # 3. 종합 점수 계산
        combined_scores = self._combine_scores(
            policy_scores,
            impact_scores,
            interest_areas,
            document_weight
        )

        # 4. 추천 근거 생성 (Claude 또는 로컬 폴백)
        if self.client:
            recommendations = self._generate_recommendations_with_claude(
                combined_scores,
                policy_analysis,
                iris_mapping,
                interest_areas,
                top_k
            )
        else:
            recommendations = self._build_fallback_result(combined_scores, top_k)

        has_interest = bool(interest_areas)
        effective_doc_weight = document_weight if has_interest else 1.0
        effective_interest_weight = (1 - document_weight) if has_interest else 0.0
        recommendations.setdefault("weighting", {})
        recommendations["weighting"].update({
            "document_weight": round(effective_doc_weight, 2),
            "interest_weight": round(effective_interest_weight, 2),
            "policy_weight": 0.6,
            "impact_weight": 0.4,
        })
        return recommendations

    def _calculate_policy_scores(
        self,
        policy_analysis: Dict[str, Any]
    ) -> Dict[str, float]:
        """정책 기반 산업 점수 계산"""
        scores = {}

        # 타겟 산업에서 점수 추출
        target_industries = self._normalize_string_list(policy_analysis.get("target_industries", []))
        for i, industry in enumerate(target_industries):
            # 순서에 따른 기본 점수 (앞에 나올수록 높음)
            base_score = 1.0 - (i * 0.05)
            scores[industry] = max(base_score, 0.5)

        # 정책 테마에서 관련 산업 추론
        policy_themes = self._normalize_string_list(policy_analysis.get("policy_themes", []))
        theme_to_industry = {
            "탄소중립": ["신재생에너지", "탄소포집", "ESS", "그린수소"],
            "디지털전환": ["AI", "클라우드", "빅데이터", "사이버보안"],
            "바이오헬스": ["신약개발", "의료기기", "디지털헬스", "진단기기"],
            "모빌리티": ["자율주행", "전기차", "UAM", "스마트물류"],
            "수소경제": ["그린수소", "수소연료전지", "수소충전소", "수소저장"],
            "반도체": ["시스템반도체", "AI반도체", "파운드리", "첨단패키징"],
            "이차전지": ["배터리소재", "전고체배터리", "배터리재활용", "BMS"],
            "ESG": ["ESG플랫폼", "탄소회계", "지속가능금융", "임팩트측정"],
        }

        for theme in policy_themes:
            if theme in theme_to_industry:
                for industry in theme_to_industry[theme]:
                    if industry not in scores:
                        scores[industry] = 0.7
                    else:
                        scores[industry] = min(scores[industry] + 0.1, 1.0)

        # 예산 정보 반영
        budget_info = policy_analysis.get("budget_info", {})
        for policy_name, budget in budget_info.items():
            # 예산 규모에 따른 가중치
            budget_weight = self._parse_budget_weight(budget)
            for industry in scores:
                if industry.lower() in policy_name.lower():
                    scores[industry] = min(scores[industry] * (1 + budget_weight), 1.0)

        return scores

    def _parse_budget_weight(self, budget_str: str) -> float:
        """예산 문자열에서 가중치 추출"""
        import re

        # "50조원" 형식 파싱
        trillion_match = re.search(r'(\d+(?:\.\d+)?)\s*조', budget_str)
        if trillion_match:
            amount = float(trillion_match.group(1))
            if amount >= 50:
                return 0.3
            elif amount >= 20:
                return 0.2
            elif amount >= 10:
                return 0.1
            else:
                return 0.05

        # "1000억원" 형식 파싱
        billion_match = re.search(r'(\d+(?:,\d+)?(?:\.\d+)?)\s*억', budget_str)
        if billion_match:
            amount_str = billion_match.group(1).replace(",", "")
            amount = float(amount_str)
            if amount >= 10000:  # 1조원 이상
                return 0.1
            elif amount >= 5000:
                return 0.05
            else:
                return 0.02

        return 0.0

    def _calculate_impact_scores(
        self,
        iris_mapping: Dict[str, Any]
    ) -> Dict[str, float]:
        """임팩트 기반 점수 계산"""
        scores = {}

        mappings = iris_mapping.get("mappings", [])
        for mapping in mappings:
            theme = self._normalize_label(mapping.get("theme", ""))
            if not theme:
                continue
            metrics = mapping.get("iris_metrics", [])
            sdgs = mapping.get("sdg_alignment", [])

            # 메트릭 수와 관련도 기반 점수
            if metrics:
                avg_relevance = sum(m.get("relevance", 0.5) for m in metrics) / len(metrics)
                metric_count_bonus = min(len(metrics) * 0.05, 0.2)
                sdg_bonus = min(len(sdgs) * 0.03, 0.15)

                scores[theme] = min(avg_relevance + metric_count_bonus + sdg_bonus, 1.0)

        return scores

    def _combine_scores(
        self,
        policy_scores: Dict[str, float],
        impact_scores: Dict[str, float],
        interest_areas: List[str] = None,
        document_weight: float = 0.7
    ) -> List[Dict[str, Any]]:
        """종합 점수 계산"""
        all_industries = set(policy_scores.keys()) | set(impact_scores.keys())
        combined = []
        document_weight = self._sanitize_weight(document_weight, default=0.7)
        has_interest = bool(interest_areas)
        interest_weight = (1 - document_weight) if has_interest else 0.0
        effective_doc_weight = document_weight if has_interest else 1.0

        for industry in all_industries:
            policy_score = policy_scores.get(industry, 0.0)
            impact_score = impact_scores.get(industry, 0.0)

            # 가중 평균 (정책 60%, 임팩트 40%)
            document_score = policy_score * 0.6 + impact_score * 0.4

            # 관심 분야 매칭 보너스
            interest_match = False
            interest_score = 0.0
            if interest_areas:
                for area in interest_areas:
                    if area.lower() in industry.lower() or industry.lower() in area.lower():
                        interest_score = 1.0
                        interest_match = True
                        break

            base_score = (document_score * effective_doc_weight) + (interest_score * interest_weight)

            # 기본 산업 가중치 적용
            for key, weight in self.DEFAULT_INDUSTRY_WEIGHTS.items():
                if key.lower() in industry.lower():
                    base_score = min(base_score * weight, 1.0)
                    break

            combined.append({
                "industry": industry,
                "total_score": round(base_score, 3),
                "policy_score": round(policy_score, 3),
                "impact_score": round(impact_score, 3),
                "interest_match": interest_match
            })

        # 점수순 정렬
        combined.sort(key=lambda x: x["total_score"], reverse=True)

        return combined

    @staticmethod
    def _sanitize_weight(value: Optional[float], default: float = 0.7) -> float:
        if value is None:
            return default
        try:
            weight = float(value)
        except (TypeError, ValueError):
            return default
        return max(min(weight, 1.0), 0.0)

    def _generate_recommendations_with_claude(
        self,
        combined_scores: List[Dict[str, Any]],
        policy_analysis: Dict[str, Any],
        iris_mapping: Dict[str, Any],
        interest_areas: List[str],
        top_k: int
    ) -> Dict[str, Any]:
        """Claude로 추천 근거 생성"""

        top_industries = combined_scores[:top_k]
        normalized_themes = self._normalize_string_list(policy_analysis.get("policy_themes", []))
        normalized_industries = self._normalize_string_list(policy_analysis.get("target_industries", []))

        prompt = f"""당신은 VC/AC 투자 전문가입니다. 다음 분석 결과를 바탕으로 유망 스타트업 산업 추천을 완성해주세요.
내부 추론은 사용하되 체인오브쏘트는 노출하지 마세요.

## 산업 점수 (상위 {top_k}개)
{json.dumps(top_industries, ensure_ascii=False, indent=2)}

## 정책 분석 결과
- 정책 테마: {normalized_themes}
- 타겟 산업: {normalized_industries}
- 예산 정보: {policy_analysis.get('budget_info', {})}
- 핵심 정책: {json.dumps(policy_analysis.get('key_policies', [])[:5], ensure_ascii=False)}

## IRIS+ 임팩트 매핑
- 연계 SDG: {iris_mapping.get('aggregate_sdgs', [])}
- 주요 메트릭: {iris_mapping.get('aggregate_metrics', [])[:10]}

## 사용자 관심 분야
{interest_areas if interest_areas else "없음"}

## 요청 사항
각 산업에 대해 다음을 작성해주세요:

1. **rationale**: 왜 이 산업이 유망한지 2-3문장으로 설명 (정책 근거 + 임팩트 관점)
2. **evidence**: 정책 문서에서의 구체적 근거 리스트 (최대 3개)
3. **sources**: 근거 출처 (문서명/페이지 등) 리스트
4. **assumptions**: 가정 리스트
5. **uncertainties**: 불확실성 리스트
6. **evidence_markers**: [FINDING]/[ASSUMPTION]/[UNCERTAINTY] 마커 포함
7. **iris_codes**: 관련 IRIS+ 메트릭 코드 리스트
8. **sdgs**: 연계 SDG 번호 리스트
9. **startup_examples**: 해당 산업의 구체적 스타트업 아이디어 3-5개
10. **cautions**: 해당 산업 유의점 2-3개

주의:
- 명시적 근거가 없으면 evidence에 "[ASSUMPTION] ..." 형태로 가정 기반 근거만 작성
- sources는 "미제공(가정)"처럼 실제 출처가 없음을 명확히 표시
- 허구의 출처를 만들지 마세요

또한 다음을 추가로 제공해주세요:
- **emerging_areas**: 아직 점수는 낮지만 주목할 신흥 분야 2-3개
- **caution_areas**: 과열 우려가 있거나 주의가 필요한 분야 1-2개

## 출력 형식 (JSON)
```json
{{
  "success": true,
  "recommendations": [
    {{
      "rank": 1,
      "industry": "산업명",
      "total_score": 0.92,
      "policy_score": 0.95,
      "impact_score": 0.88,
      "interest_match": true/false,
      "rationale": "추천 근거 설명",
      "evidence": ["근거1", "근거2"],
      "sources": ["문서명 p.12", "보도자료"],
      "assumptions": ["가정1"],
      "uncertainties": ["불확실성1"],
      "evidence_markers": [
        {{"marker": "[FINDING]", "statement": "근거 요약", "source": "문서명 p.12", "effect_size": "연 12% 성장"}}
      ],
      "iris_codes": ["코드1", "코드2"],
      "sdgs": [7, 13],
      "startup_examples": ["아이디어1", "아이디어2", "아이디어3"],
      "cautions": ["유의점1", "유의점2"]
    }}
  ],
  "emerging_areas": [
    {{
      "industry": "신흥 분야명",
      "reason": "주목 이유",
      "timeline": "2-3년 후 본격화 예상"
    }}
  ],
  "caution_areas": [
    {{
      "industry": "주의 분야명",
      "reason": "주의 필요 이유"
    }}
  ],
  "summary": "전체 추천 요약 (2-3문장)"
}}
```

JSON만 출력하세요.
"""

        try:
            response = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.content[0].text

            # JSON 추출
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group(1)

            result = json.loads(result_text)
            result["success"] = True

            # 점수 정보 보존
            for i, rec in enumerate(result.get("recommendations", [])):
                if i < len(top_industries):
                    rec["total_score"] = top_industries[i]["total_score"]
                    rec["policy_score"] = top_industries[i]["policy_score"]
                    rec["impact_score"] = top_industries[i]["impact_score"]
                    rec["interest_match"] = top_industries[i]["interest_match"]
                rec.setdefault("sources", [])
                rec.setdefault("assumptions", [])
                rec.setdefault("uncertainties", [])
                rec.setdefault("evidence_markers", [])
                rec.setdefault("cautions", [])
                if not rec.get("evidence"):
                    rec["evidence"] = self._build_placeholder_evidence(rec.get("industry", ""))
                if not rec.get("sources"):
                    rec["sources"] = ["미제공(가정)"]
                if not rec.get("assumptions"):
                    rec["assumptions"] = ["정책/시장 근거가 제한됨"]
                if not rec.get("uncertainties"):
                    rec["uncertainties"] = ["근거 데이터 부족"]
                if not rec.get("evidence_markers"):
                    rec["evidence_markers"] = self._build_placeholder_markers(rec.get("industry", ""))

            return result

        except json.JSONDecodeError as e:
            # JSON 파싱 실패 시 기본 결과 반환
            return {
                "success": True,
                "recommendations": [
                    {
                        "rank": i + 1,
                        **score,
                        "rationale": "분석 결과 기반 추천",
                        "evidence": self._build_placeholder_evidence(score.get("industry")),
                        "sources": ["미제공(가정)"],
                        "assumptions": ["정책/시장 근거가 제한됨"],
                        "uncertainties": ["근거 데이터 부족"],
                        "evidence_markers": self._build_placeholder_markers(score.get("industry")),
                        "iris_codes": [],
                        "sdgs": [],
                        "startup_examples": [],
                        "cautions": []
                    }
                    for i, score in enumerate(top_industries)
                ],
                "emerging_areas": [],
                "caution_areas": [],
                "summary": "정책 및 임팩트 분석 기반 산업 추천",
                "fallback_used": True
            }

        except Exception as e:
            fallback = self._build_fallback_result(combined_scores, top_k)
            fallback["error"] = str(e)
            fallback["fallback_used"] = True
            return fallback

    def _build_fallback_result(
        self,
        combined_scores: List[Dict[str, Any]],
        top_k: int
    ) -> Dict[str, Any]:
        top_industries = combined_scores[:top_k]
        return {
            "success": True,
            "recommendations": [
                {
                    "rank": i + 1,
                    **score,
                    "rationale": "로컬 점수 기반 추천 (추가 근거 필요)",
                    "evidence": self._build_placeholder_evidence(score.get("industry")),
                    "sources": ["미제공(가정)"],
                    "assumptions": ["근거 데이터 제한"],
                    "uncertainties": ["정책 원문 근거 부족"],
                    "evidence_markers": self._build_placeholder_markers(score.get("industry")),
                    "iris_codes": [],
                    "sdgs": [],
                    "startup_examples": [],
                    "cautions": ["근거 확보 전에는 투자 결정 보류"]
                }
                for i, score in enumerate(top_industries)
            ],
            "emerging_areas": [],
            "caution_areas": [],
            "summary": "API 사용 불가로 로컬 점수 기반 추천",
            "fallback_used": True
        }

    @staticmethod
    def _build_placeholder_evidence(industry: str) -> List[str]:
        label = industry or "해당 산업"
        return [
            f"[ASSUMPTION] {label} 산업은 정책 우선순위가 될 가능성이 있음",
            f"[ASSUMPTION] {label} 수요가 중기적으로 증가할 가능성이 있음",
        ]

    @staticmethod
    def _build_placeholder_markers(industry: str) -> List[Dict[str, str]]:
        label = industry or "해당 산업"
        return [
            {
                "marker": "[ASSUMPTION]",
                "statement": f"{label} 수요 확대 가정",
                "source": "미제공(가정)",
                "effect_size": "",
            },
            {
                "marker": "[UNCERTAINTY]",
                "statement": f"{label} 정책 예산/일정 불확실",
                "source": "미제공(가정)",
                "effect_size": "",
            },
        ]

    def quick_recommend(
        self,
        themes: List[str],
        industries: List[str] = None,
        interest_areas: List[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        빠른 추천 (Claude API 호출 없이)

        간단한 점수 계산만으로 빠르게 추천을 반환합니다.
        """
        scores = {}

        # 테마 기반 점수
        for i, theme in enumerate(themes):
            base_score = 1.0 - (i * 0.1)
            scores[theme] = max(base_score, 0.5)

        # 산업 기반 점수
        if industries:
            for i, industry in enumerate(industries):
                if industry not in scores:
                    scores[industry] = 0.8 - (i * 0.05)
                else:
                    scores[industry] = min(scores[industry] + 0.1, 1.0)

        # 관심 분야 보너스
        if interest_areas:
            for area in interest_areas:
                if area in scores:
                    scores[area] = min(scores[area] * 1.2, 1.0)

        # 정렬 및 반환
        sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        return [
            {
                "rank": i + 1,
                "industry": item[0],
                "score": round(item[1], 3)
            }
            for i, item in enumerate(sorted_items[:top_k])
        ]
