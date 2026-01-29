"""
시멘틱 포트폴리오 검색 모듈
- 쿼리 확장 (query expansion)
- 멀티쿼리 생성
- 의미 기반 검색 조건 추출
"""

from typing import Dict, List, Any, Optional, Tuple
from anthropic import Anthropic
import logging

logger = logging.getLogger(__name__)


def expand_portfolio_query(
    user_query: str,
    api_key: str,
    available_columns: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    사용자 쿼리를 분석하여 구조화된 검색 조건으로 확장

    Args:
        user_query: 사용자의 자연어 쿼리
        api_key: Claude API 키
        available_columns: 사용 가능한 컬럼 목록 (옵션)

    Returns:
        {
            "intent": "쿼리 의도 설명",
            "search_strategy": "검색 전략 설명",
            "subqueries": [
                {
                    "description": "서브쿼리 설명",
                    "filters": {"컬럼": "값"},
                    "sort_by": "정렬 컬럼",
                    "sort_order": "asc/desc"
                }
            ],
            "final_limit": 5
        }
    """

    if not available_columns:
        available_columns = [
            "기업명", "제품/서비스", "카테고리1", "카테고리2", "SDGs",
            "투자금액", "투자단계", "본점 소재지", "키워드\n(Business)",
            "키워드\n(Social Impact)", "투자포인트", "Exit방안"
        ]

    try:
        client = Anthropic(api_key=api_key)

        prompt = f"""당신은 VC 투자 포트폴리오 검색 전문가입니다.
사용자의 자연어 쿼리를 분석하여 효과적인 검색 전략을 제시해주세요.

## 사용 가능한 컬럼
{', '.join(available_columns)}

## 주요 매핑 규칙
- "사회적 기업" / "임팩트" / "사회적 가치" → SDGs 컬럼 또는 "키워드\\n(Social Impact)" 검색
- "투자금액 높은" / "큰 투자" → "투자금액" 컬럼으로 정렬 (desc)
- "AI" / "인공지능" → "카테고리1" = "AI" 필터
- "헬스케어" / "의료" → "카테고리1" = "헬스케어" 필터
- "지역" 언급 → "본점 소재지" 필터
- SDGs 3 = 건강/복지, SDGs 8 = 일자리, SDGs 13 = 기후변화 등

## 사용자 쿼리
"{user_query}"

## 출력 형식 (JSON만 출력, 다른 텍스트 없이)
{{
    "intent": "사용자가 원하는 것을 한 문장으로",
    "search_strategy": "어떻게 검색할지 전략 설명",
    "subqueries": [
        {{
            "description": "서브쿼리 설명 (사용자에게 보여질 텍스트)",
            "filters": {{"컬럼명": "값"}},
            "sort_by": "정렬 컬럼 (없으면 null)",
            "sort_order": "asc 또는 desc"
        }}
    ],
    "final_limit": 5
}}

중요:
- subqueries는 1-3개가 적당합니다.
- 각 서브쿼리는 독립적으로 실행 가능해야 합니다.
- description은 "① 투자금액 상위 기업", "② SDGs 보유 기업" 같은 형식으로.
- filters의 키는 반드시 위 컬럼 목록에 있는 정확한 이름이어야 합니다.
"""

        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        result_text = response.content[0].text.strip()

        # JSON 파싱
        import json
        # ```json ... ``` 제거
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        result = json.loads(result_text)

        logger.info(f"쿼리 확장 완료: {user_query} → {len(result.get('subqueries', []))}개 서브쿼리")
        return result

    except Exception as e:
        logger.warning(f"쿼리 확장 실패: {e}")
        # 실패 시 기본 검색
        return {
            "intent": user_query,
            "search_strategy": "단순 텍스트 검색",
            "subqueries": [{
                "description": "기본 검색",
                "filters": {},
                "sort_by": None,
                "sort_order": "desc"
            }],
            "final_limit": 5
        }


def format_search_plan(expanded_query: Dict[str, Any]) -> str:
    """
    확장된 쿼리를 사용자에게 보여줄 검색 계획으로 포맷

    Returns:
        사용자에게 보여줄 마크다운 텍스트
    """

    intent = expanded_query.get("intent", "포트폴리오 검색")
    strategy = expanded_query.get("search_strategy", "")
    subqueries = expanded_query.get("subqueries", [])
    limit = expanded_query.get("final_limit", 5)

    lines = [
        "## 🔍 검색 계획",
        "",
        f"**목표**: {intent}",
        f"**전략**: {strategy}",
        "",
        "**검색 방법**:"
    ]

    for i, sq in enumerate(subqueries, 1):
        desc = sq.get("description", f"검색 {i}")
        lines.append(f"{i}. {desc}")

        # 필터 상세 (옵션)
        filters = sq.get("filters", {})
        if filters:
            filter_str = ", ".join([f"{k}={v}" for k, v in filters.items()])
            lines.append(f"   - 조건: {filter_str}")

        # 정렬
        sort_by = sq.get("sort_by")
        if sort_by:
            sort_order = sq.get("sort_order", "desc")
            sort_label = "높은 순" if sort_order == "desc" else "낮은 순"
            lines.append(f"   - 정렬: {sort_by} {sort_label}")

    lines.append("")
    lines.append(f"**최종 결과**: 상위 {limit}개 기업")
    lines.append("")
    lines.append("이렇게 검색하시겠습니까?")

    return "\n".join(lines)


def merge_subquery_results(
    subquery_results: List[List[Dict[str, str]]],
    final_limit: int = 5
) -> List[Dict[str, str]]:
    """
    여러 서브쿼리 결과를 병합하고 중복 제거

    Args:
        subquery_results: 각 서브쿼리의 결과 리스트
        final_limit: 최종 반환할 최대 개수

    Returns:
        병합된 기업 리스트 (중복 제거, 우선순위 반영)
    """

    seen_companies = {}  # 기업명 → (레코드, 점수)

    for priority, results in enumerate(subquery_results):
        for record in results:
            company_name = record.get("기업명", "")
            if not company_name:
                continue

            # 이미 있는 기업이면 점수만 업데이트
            if company_name in seen_companies:
                existing_score = seen_companies[company_name][1]
                # 더 앞의 서브쿼리에서 나온 것이 우선순위 높음
                new_score = existing_score + (10 - priority)
                seen_companies[company_name] = (record, new_score)
            else:
                # 첫 등장, 초기 점수는 (10 - priority)
                seen_companies[company_name] = (record, 10 - priority)

    # 점수 순으로 정렬
    sorted_companies = sorted(
        seen_companies.values(),
        key=lambda x: x[1],
        reverse=True
    )

    # 상위 N개만 반환
    return [record for record, score in sorted_companies[:final_limit]]
