"""
Startup discovery support tools.

Government policy analysis, IRIS+ metrics, and industry recommendations.
"""

from typing import Any, Dict, List

from ._common import _validate_file_path, logger

TOOLS = [
    {
        "name": "analyze_government_policy",
        "description": "정부 정책 PDF/아티클을 분석하여 핵심 정책 방향, 예산 배분, 타겟 산업을 추출합니다. 여러 PDF를 한번에 분석할 수 있습니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pdf_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "분석할 PDF 파일 경로 리스트",
                },
                "focus_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "집중 분석할 키워드 (선택)",
                },
                "max_pages_per_pdf": {
                    "type": "integer",
                    "description": "PDF당 최대 페이지 수 (기본: 30)",
                },
            },
            "required": ["pdf_paths"],
        },
    },
    {
        "name": "search_iris_plus_metrics",
        "description": "IRIS+ 임팩트 메트릭 카탈로그에서 키워드/카테고리로 관련 지표를 검색합니다. SDG(지속가능발전목표) 연계 정보도 반환합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색 키워드 (예: clean energy, 탄소중립)",
                },
                "category": {
                    "type": "string",
                    "enum": ["environmental", "social", "governance"],
                    "description": "카테고리 필터 (선택)",
                },
                "sdg_filter": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "SDG 번호 필터 (예: [7, 13])",
                },
                "top_k": {
                    "type": "integer",
                    "description": "상위 결과 수 (기본: 10)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "map_policy_to_iris",
        "description": "정책 분석 결과를 IRIS+ 메트릭에 자동 매핑합니다. 정책-임팩트 연관도 점수를 계산합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "policy_themes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "정책 테마 리스트 (예: ['탄소중립', '디지털전환'])",
                },
                "target_industries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "타겟 산업 리스트 (선택)",
                },
                "min_relevance_score": {
                    "type": "number",
                    "description": "최소 연관도 점수 (기본: 0.3)",
                },
            },
            "required": ["policy_themes"],
        },
    },
    {
        "name": "generate_industry_recommendation",
        "description": "정책 분석 + IRIS+ 매핑 결과를 종합하여 유망 산업/스타트업 영역을 추천합니다. 근거와 함께 순위를 제공합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "policy_analysis": {
                    "type": "object",
                    "description": "analyze_government_policy 결과",
                },
                "iris_mapping": {
                    "type": "object",
                    "description": "map_policy_to_iris 결과",
                },
                "interest_areas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "사용자 관심 분야 (선택)",
                },
                "recommendation_count": {
                    "type": "integer",
                    "description": "추천 개수 (기본: 5)",
                },
                "document_weight": {
                    "type": "number",
                    "description": "문서 기반 가중치 (0~1, 기본: 0.7)",
                },
            },
            "required": ["policy_analysis", "iris_mapping"],
        },
    },
]


def execute_analyze_government_policy(
    pdf_paths: List[str] = None,
    text_content: str = None,
    focus_keywords: List[str] = None,
    max_pages_per_pdf: int = 30,
    api_key: str = None,
) -> Dict[str, Any]:
    """정부 정책 PDF/텍스트 분석 실행"""
    try:
        from discovery_service import PolicyAnalyzer

        validated_paths = []
        if pdf_paths:
            for pdf_path in pdf_paths:
                is_valid, error = _validate_file_path(pdf_path, require_temp_dir=True)
                if not is_valid:
                    return {"success": False, "error": f"경로 검증 실패: {pdf_path} - {error}"}
                validated_paths.append(pdf_path)

        if not validated_paths and not text_content:
            return {"success": False, "error": "PDF 파일 또는 텍스트 콘텐츠가 필요합니다"}

        analyzer = PolicyAnalyzer(api_key=api_key)
        result = analyzer.analyze_content(
            pdf_paths=validated_paths if validated_paths else None,
            text_content=text_content,
            focus_keywords=focus_keywords,
            max_pages=max_pages_per_pdf,
        )

        return result

    except ImportError as e:
        return {"success": False, "error": f"discovery_service 모듈을 찾을 수 없습니다: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"정책 분석 실패: {str(e)}"}


def execute_search_iris_plus_metrics(
    query: str,
    category: str = None,
    sdg_filter: List[int] = None,
    top_k: int = 10,
) -> Dict[str, Any]:
    """IRIS+ 메트릭 검색 실행"""
    try:
        from discovery_service import IRISMapper

        mapper = IRISMapper()
        result = mapper.search_metrics(
            query=query, category=category, sdg_filter=sdg_filter, top_k=top_k
        )

        return result

    except FileNotFoundError as e:
        return {"success": False, "error": f"IRIS+ 카탈로그를 찾을 수 없습니다: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"IRIS+ 검색 실패: {str(e)}"}


def execute_map_policy_to_iris(
    policy_themes: List[str],
    target_industries: List[str] = None,
    min_relevance_score: float = 0.3,
) -> Dict[str, Any]:
    """정책 테마를 IRIS+ 메트릭에 매핑"""
    try:
        from discovery_service import IRISMapper

        mapper = IRISMapper()
        result = mapper.map_themes_to_iris(
            themes=policy_themes, industries=target_industries, min_score=min_relevance_score
        )

        return result

    except Exception as e:
        return {"success": False, "error": f"IRIS+ 매핑 실패: {str(e)}"}


def execute_generate_industry_recommendation(
    policy_analysis: Dict[str, Any],
    iris_mapping: Dict[str, Any],
    interest_areas: List[str] = None,
    recommendation_count: int = 5,
    api_key: str = None,
    document_weight: float = None,
) -> Dict[str, Any]:
    """유망 산업 추천 생성"""
    try:
        from discovery_service import IndustryRecommender

        recommender = IndustryRecommender(api_key=api_key)
        result = recommender.generate_recommendations(
            policy_analysis=policy_analysis,
            iris_mapping=iris_mapping,
            interest_areas=interest_areas,
            top_k=recommendation_count,
            document_weight=document_weight if document_weight is not None else 0.7,
        )

        return result

    except Exception as e:
        try:
            from discovery_service import IndustryRecommender

            recommender = IndustryRecommender(api_key=None)
            fallback = recommender.quick_recommend(
                themes=policy_analysis.get("policy_themes", []),
                industries=policy_analysis.get("target_industries", []),
                interest_areas=interest_areas,
                top_k=recommendation_count,
            )

            def _placeholder_evidence(industry: str) -> List[str]:
                label = industry or "해당 산업"
                return [
                    f"[ASSUMPTION] {label} 산업은 정책 우선순위가 될 가능성이 있음",
                    f"[ASSUMPTION] {label} 수요가 중기적으로 증가할 가능성이 있음",
                ]

            doc_weight_value = float(document_weight if document_weight is not None else 0.7)
            if not interest_areas:
                doc_weight_value = 1.0
            interest_weight_value = (1 - doc_weight_value) if interest_areas else 0.0
            return {
                "success": True,
                "recommendations": [
                    {
                        "rank": item.get("rank"),
                        "industry": item.get("industry"),
                        "total_score": item.get("score", 0),
                        "policy_score": item.get("score", 0),
                        "impact_score": 0.0,
                        "interest_match": False,
                        "rationale": "로컬 폴백 추천",
                        "evidence": _placeholder_evidence(item.get("industry")),
                        "sources": ["미제공(가정)"],
                        "assumptions": ["근거 데이터 제한"],
                        "uncertainties": ["정책 원문 근거 부족"],
                        "evidence_markers": [
                            {
                                "marker": "[ASSUMPTION]",
                                "statement": f"{item.get('industry', '해당 산업')} 수요 확대 가정",
                                "source": "미제공(가정)",
                                "effect_size": "",
                            }
                        ],
                        "iris_codes": [],
                        "sdgs": [],
                        "startup_examples": [],
                        "cautions": ["근거 확보 전에는 투자 결정 보류"],
                    }
                    for item in fallback
                ],
                "emerging_areas": [],
                "caution_areas": [],
                "summary": "API 오류로 로컬 폴백 추천",
                "weighting": {
                    "document_weight": round(doc_weight_value, 2),
                    "interest_weight": round(interest_weight_value, 2),
                    "policy_weight": 0.6,
                    "impact_weight": 0.4,
                },
                "fallback_used": True,
                "error": str(e),
            }
        except Exception:
            pass
        return {"success": False, "error": f"산업 추천 생성 실패: {str(e)}"}


EXECUTORS = {
    "analyze_government_policy": execute_analyze_government_policy,
    "search_iris_plus_metrics": execute_search_iris_plus_metrics,
    "map_policy_to_iris": execute_map_policy_to_iris,
    "generate_industry_recommendation": execute_generate_industry_recommendation,
}
