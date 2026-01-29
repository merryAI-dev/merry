"""
포트폴리오 검색 쿼리 최적화 모듈

에이전트가 사용자 쿼리를 자동으로 최적화하여
Airtable 검색 성공률을 높입니다.
"""

from typing import Dict, List, Optional, Any
import re


# 카테고리 동의어 매핑 (실제 데이터 기반)
CATEGORY_SYNONYMS = {
    "ai": ["AI", "인공지능", "머신러닝", "딥러닝", "ai기업", "인공지능기업"],
    "healthcare": ["헬스케어", "의료", "건강", "health", "medical"],
    "environment": ["환경", "친환경", "그린", "green", "eco", "지속가능"],
    "food": ["푸드", "농업", "식품", "food", "농식품", "에그테크"],
    "energy": ["에너지", "에너지", "신재생", "재생에너지", "태양광", "풍력"],
    "fintech": ["핀테크", "금융", "finance", "fintech"],
    "edu": ["교육", "에듀테크", "education", "edtech"],
    "platform": ["플랫폼", "마켓플레이스", "중개", "platform"],
    "blockchain": ["블록체인", "블록체인", "crypto"],
    "content": ["콘텐츠", "미디어", "content"],
}

# 지역 동의어 매핑
LOCATION_SYNONYMS = {
    "서울": ["서울", "강남", "강북", "서초", "마포", "성동", "종로", "영등포", "서울시"],
    "경기": ["경기", "경기도", "성남", "수원", "용인", "고양", "부천", "안산", "양주", "이천", "하남"],
    "강원": ["강원", "강원도", "춘천", "원주", "강릉", "양양"],
    "제주": ["제주", "제주도", "서귀포"],
    "대전": ["대전", "유성"],
    "전북": ["전북", "전주", "익산"],
    "경남": ["경남", "김해", "양산", "진주"],
    "경북": ["경북", "포항"],
    "부산": ["부산", "기장", "해운대"],
    "인천": ["인천", "남동", "연수"],
    "충남": ["충남", "천안"],
}

# SDGs 키워드 매핑
SDGS_KEYWORDS = {
    "SDGs 3": ["건강", "의료", "헬스케어", "보건"],
    "SDGs 7": ["에너지", "청정에너지", "재생에너지"],
    "SDGs 8": ["일자리", "경제성장", "고용", "장애인고용"],
    "SDGs 9": ["혁신", "인프라", "산업화"],
    "SDGs 11": ["지속가능도시", "주거", "교통"],
    "SDGs 12": ["지속가능소비", "생산", "재활용", "업사이클"],
    "SDGs 13": ["기후", "기후변화", "탄소중립"],
}


def optimize_query(user_query: str) -> Dict[str, Any]:
    """
    사용자 쿼리를 분석하여 최적화된 검색 파라미터 생성

    Args:
        user_query: 사용자 자연어 쿼리

    Returns:
        최적화된 검색 파라미터
        {
            "strategy": "direct_filter" | "semantic_search" | "hybrid",
            "filters": {...},
            "sort_by": str,
            "sort_order": str,
            "fallback_query": str,
            "confidence": float
        }
    """
    query_lower = user_query.lower().strip()

    result = {
        "strategy": "semantic_search",  # 기본값
        "filters": {},
        "sort_by": None,
        "sort_order": None,
        "fallback_query": None,
        "confidence": 0.5,
    }

    # 1. 카테고리 감지
    detected_category = None
    for canonical, synonyms in CATEGORY_SYNONYMS.items():
        for syn in synonyms:
            if syn.lower() in query_lower:
                detected_category = _get_category_value(canonical)
                result["filters"]["카테고리1"] = detected_category
                result["strategy"] = "direct_filter"
                result["confidence"] = 0.9
                break
        if detected_category:
            break

    # 2. 지역 감지 (본점 소재지 filter로 변환)
    detected_location = None
    for canonical, synonyms in LOCATION_SYNONYMS.items():
        for syn in synonyms:
            if syn in query_lower:
                detected_location = canonical
                # 지역 검색은 본점 소재지 필터로 처리
                result["filters"]["본점 소재지_contains"] = canonical
                result["confidence"] = max(result["confidence"], 0.9)
                # query에서 지역명 제거 (나머지 키워드만 검색)
                query_without_location = query_lower.replace(syn, "").strip()
                result["fallback_query"] = query_without_location if query_without_location else None
                break
        if detected_location:
            break

    # 3. 정렬 조건 감지
    if any(kw in query_lower for kw in ["높은", "많은", "큰", "top", "상위"]):
        if "투자" in query_lower or "금액" in query_lower:
            result["sort_by"] = "투자금액"
            result["sort_order"] = "desc"
            result["confidence"] = max(result["confidence"], 0.9)
    elif any(kw in query_lower for kw in ["낮은", "적은", "작은"]):
        if "투자" in query_lower or "금액" in query_lower:
            result["sort_by"] = "투자금액"
            result["sort_order"] = "asc"
            result["confidence"] = max(result["confidence"], 0.9)

    # 4. SDGs 감지
    for sdg, keywords in SDGS_KEYWORDS.items():
        if any(kw in query_lower for kw in keywords):
            result["filters"]["SDGs"] = sdg
            result["confidence"] = max(result["confidence"], 0.7)
            break

    # 5. 전략 결정
    if result["filters"] and result["confidence"] >= 0.8:
        result["strategy"] = "direct_filter"
    elif result["fallback_query"] and not result["filters"]:
        result["strategy"] = "hybrid"  # query + semantic fallback
    else:
        result["strategy"] = "semantic_search"

    return result


def _get_category_value(canonical: str) -> str:
    """카테고리 canonical name을 실제 DB 값으로 매핑"""
    mapping = {
        "ai": "AI",
        "healthcare": "헬스케어",
        "environment": "환경",
        "food": "푸드",
        "energy": "에너지",
        "fintech": "핀테크",
        "edu": "교육",
        "platform": "플랫폼",
        "blockchain": "블록체인",
        "content": "콘텐츠",
    }
    return mapping.get(canonical, canonical)


def generate_fallback_filters(user_query: str) -> List[Dict[str, Any]]:
    """
    텍스트 검색 실패 시 사용할 대안 필터 생성

    Args:
        user_query: 원본 사용자 쿼리

    Returns:
        대안 필터 리스트 (우선순위순)
    """
    fallbacks = []

    optimization = optimize_query(user_query)

    # Fallback 1: 감지된 필터로 검색
    if optimization["filters"]:
        fallbacks.append({
            "description": "감지된 카테고리/조건으로 검색",
            "filters": optimization["filters"],
            "sort_by": optimization.get("sort_by"),
            "sort_order": optimization.get("sort_order"),
        })

    # Fallback 2: 유사 카테고리 확장
    if "카테고리1" in optimization["filters"]:
        cat = optimization["filters"]["카테고리1"]
        related = _get_related_categories(cat)
        if related:
            fallbacks.append({
                "description": f"관련 카테고리 포함 ({', '.join(related[:3])})",
                "filters": {"카테고리1": related},
            })

    # Fallback 3: 지역만으로 검색
    if optimization["fallback_query"]:
        # 지역은 query 대신 filters로 시도
        for loc in LOCATION_SYNONYMS.keys():
            if loc in user_query:
                fallbacks.append({
                    "description": f"{loc} 지역 기업 검색",
                    "filters": {},  # CSV에서는 query로 검색하므로 비워둠
                    "query": loc,  # 이것은 힌트로만 사용
                })
                break

    return fallbacks


def _get_related_categories(category: str) -> List[str]:
    """관련 카테고리 찾기"""
    related_groups = {
        "AI": ["빅데이터", "딥테크"],
        "헬스케어": ["바이오", "의료"],
        "환경": ["에너지", "농업"],
        "푸드": ["농업"],
        "플랫폼": ["커머스", "비즈니스"],
    }
    return related_groups.get(category, [])


def explain_optimization(user_query: str, optimization: Dict[str, Any]) -> str:
    """최적화 결과를 사용자에게 설명"""
    lines = [f"🔍 쿼리 분석: '{user_query}'"]

    if optimization["filters"]:
        lines.append(f"✅ 감지된 필터: {optimization['filters']}")

    if optimization["sort_by"]:
        lines.append(f"✅ 정렬: {optimization['sort_by']} ({optimization['sort_order']})")

    if optimization["fallback_query"]:
        lines.append(f"⚠️ 텍스트 검색어: {optimization['fallback_query']} (fallback 사용)")

    lines.append(f"📊 전략: {optimization['strategy']}")
    lines.append(f"🎯 신뢰도: {optimization['confidence']:.0%}")

    return "\n".join(lines)
