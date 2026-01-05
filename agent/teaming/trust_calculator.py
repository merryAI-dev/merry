"""
신뢰도 점수 계산
도구별 기본 신뢰도 + 출력 품질 기반 동적 조정
"""

from typing import Any, Dict, Optional


# 도구별 기본 신뢰도 (0.0 ~ 1.0)
TOOL_BASE_RELIABILITY: Dict[str, float] = {
    # 계산 도구 (높은 신뢰도)
    "calculate_valuation": 0.95,
    "calculate_dilution": 0.95,
    "calculate_irr": 0.95,

    # 읽기 도구 (높은 신뢰도)
    "read_excel_as_text": 0.90,
    "read_pdf_as_text": 0.85,
    "parse_pdf_dolphin": 0.85,
    "extract_pdf_tables": 0.80,
    "get_stock_financials": 0.85,

    # 분석 도구 (중간 신뢰도)
    "analyze_excel": 0.75,
    "analyze_peer_per": 0.70,
    "analyze_company_diagnosis_sheet": 0.70,

    # 검색 도구 (중간 신뢰도)
    "search_underwriter_opinion": 0.65,
    "search_underwriter_opinion_similar": 0.65,
    "extract_pdf_market_evidence": 0.65,
    "fetch_underwriter_opinion_data": 0.70,

    # 생성 도구 (낮은 신뢰도 - 검토 필요)
    "generate_exit_projection": 0.60,
    "analyze_and_generate_projection": 0.55,
    "create_company_diagnosis_draft": 0.55,
    "update_company_diagnosis_draft": 0.60,
    "generate_company_diagnosis_sheet_from_draft": 0.55,
    "write_company_diagnosis_report": 0.50,
}


def calculate_trust_score(
    tool_name: str,
    tool_output: Optional[Dict[str, Any]] = None,
    feedback_history: Optional[Dict[str, Any]] = None
) -> float:
    """
    신뢰도 점수 계산

    Args:
        tool_name: 도구 이름
        tool_output: 도구 실행 결과 (선택)
        feedback_history: 피드백 이력 (선택)

    Returns:
        float: 신뢰도 점수 (0.0 ~ 1.0)
    """
    # 기본 신뢰도
    base = TOOL_BASE_RELIABILITY.get(tool_name, 0.5)

    # 출력이 없으면 20% 감소
    if tool_output is None:
        return round(base * 0.8, 2)

    score = base

    # ========================================
    # 출력 품질 기반 조정
    # ========================================

    # 실패 시 50% 감소
    if tool_output.get("success") is False:
        score *= 0.5

    # 데이터 풍부도 보너스
    if isinstance(tool_output.get("data"), dict):
        data_keys = len(tool_output["data"])
        if data_keys > 5:
            score = min(score + 0.15, 1.0)
        elif data_keys > 3:
            score = min(score + 0.10, 1.0)

    # 에러 없음 보너스
    if not tool_output.get("error"):
        score = min(score + 0.05, 1.0)

    # 경고 있으면 감점
    warnings = tool_output.get("warnings", [])
    if warnings:
        score = max(score - 0.05 * len(warnings), 0.3)

    # ========================================
    # 피드백 이력 기반 조정
    # ========================================
    if feedback_history:
        positive = feedback_history.get("positive", 0)
        negative = feedback_history.get("negative", 0)
        total = positive + negative

        if total > 0:
            feedback_ratio = positive / total
            # 피드백 비율에 따라 ±10% 조정
            adjustment = (feedback_ratio - 0.5) * 0.2
            score = min(max(score + adjustment, 0.3), 1.0)

    return round(score, 2)


def get_auto_approval_threshold(tool_name: str) -> float:
    """
    자동 승인 임계값 조회

    신뢰도가 이 값 이상이면 Level 3에서 자동 승인
    """
    # 생성 도구는 더 높은 임계값 필요
    if "generate" in tool_name or "write" in tool_name or "create" in tool_name:
        return 0.90
    # 분석 도구
    if "analyze" in tool_name:
        return 0.85
    # 그 외
    return 0.80


def should_auto_approve(tool_name: str, trust_score: float) -> bool:
    """자동 승인 여부 판단"""
    threshold = get_auto_approval_threshold(tool_name)
    return trust_score >= threshold
