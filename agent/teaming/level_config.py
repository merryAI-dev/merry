"""
도구별 자동화 레벨 설정
Human-AI Teaming 4-Level Framework
"""

from enum import Enum
from typing import Dict


class AutomationLevel(Enum):
    """자동화 레벨 정의 (ICU 연구 기반)"""
    LEVEL_1_HUMAN_ONLY = 1      # 인간 직접 수행
    LEVEL_2_AI_ASSISTS = 2      # 인간 주도, AI 보조 (사전 승인)
    LEVEL_3_HUMAN_VERIFIES = 3  # AI 주도, 인간 검증 (사후 검토)
    LEVEL_4_FULL_AUTO = 4       # 완전 자동화


LEVEL_DESCRIPTIONS = {
    AutomationLevel.LEVEL_1_HUMAN_ONLY: "인간이 직접 수행해야 합니다",
    AutomationLevel.LEVEL_2_AI_ASSISTS: "AI가 준비하고 인간이 승인 후 실행합니다",
    AutomationLevel.LEVEL_3_HUMAN_VERIFIES: "AI가 실행하고 인간이 결과를 검토합니다",
    AutomationLevel.LEVEL_4_FULL_AUTO: "AI가 자동으로 실행합니다",
}


LEVEL_NAMES_KO = {
    AutomationLevel.LEVEL_1_HUMAN_ONLY: "인간 전용",
    AutomationLevel.LEVEL_2_AI_ASSISTS: "AI 보조",
    AutomationLevel.LEVEL_3_HUMAN_VERIFIES: "인간 검증",
    AutomationLevel.LEVEL_4_FULL_AUTO: "완전 자동",
}


# 도구별 기본 자동화 레벨
TOOL_LEVELS: Dict[str, AutomationLevel] = {
    # ========================================
    # Level 4: 완전 자동화 (읽기, 계산)
    # ========================================
    "read_excel_as_text": AutomationLevel.LEVEL_4_FULL_AUTO,
    "read_pdf_as_text": AutomationLevel.LEVEL_4_FULL_AUTO,
    "parse_pdf_dolphin": AutomationLevel.LEVEL_4_FULL_AUTO,
    "extract_pdf_tables": AutomationLevel.LEVEL_4_FULL_AUTO,
    "calculate_valuation": AutomationLevel.LEVEL_4_FULL_AUTO,
    "calculate_dilution": AutomationLevel.LEVEL_4_FULL_AUTO,
    "calculate_irr": AutomationLevel.LEVEL_4_FULL_AUTO,
    "get_stock_financials": AutomationLevel.LEVEL_4_FULL_AUTO,

    # ========================================
    # Level 3: AI 주도, 인간 검증 (분석, 검색)
    # ========================================
    "analyze_excel": AutomationLevel.LEVEL_3_HUMAN_VERIFIES,
    "analyze_peer_per": AutomationLevel.LEVEL_3_HUMAN_VERIFIES,
    "analyze_company_diagnosis_sheet": AutomationLevel.LEVEL_3_HUMAN_VERIFIES,
    "search_underwriter_opinion": AutomationLevel.LEVEL_3_HUMAN_VERIFIES,
    "search_underwriter_opinion_similar": AutomationLevel.LEVEL_3_HUMAN_VERIFIES,
    "extract_pdf_market_evidence": AutomationLevel.LEVEL_3_HUMAN_VERIFIES,
    "fetch_underwriter_opinion_data": AutomationLevel.LEVEL_3_HUMAN_VERIFIES,

    # ========================================
    # Level 3: AI 주도, 인간 검증 (문서 생성도 자동 실행 후 검토)
    # ========================================
    "generate_exit_projection": AutomationLevel.LEVEL_3_HUMAN_VERIFIES,
    "analyze_and_generate_projection": AutomationLevel.LEVEL_3_HUMAN_VERIFIES,
    "create_company_diagnosis_draft": AutomationLevel.LEVEL_3_HUMAN_VERIFIES,
    "update_company_diagnosis_draft": AutomationLevel.LEVEL_3_HUMAN_VERIFIES,
    "generate_company_diagnosis_sheet_from_draft": AutomationLevel.LEVEL_3_HUMAN_VERIFIES,
    "write_company_diagnosis_report": AutomationLevel.LEVEL_3_HUMAN_VERIFIES,
}


def get_tool_level(tool_name: str) -> AutomationLevel:
    """
    도구 자동화 레벨 조회

    Args:
        tool_name: 도구 이름

    Returns:
        AutomationLevel: 해당 도구의 자동화 레벨
        (등록되지 않은 도구는 Level 3 기본값)
    """
    return TOOL_LEVELS.get(tool_name, AutomationLevel.LEVEL_3_HUMAN_VERIFIES)


def get_level_description(level: AutomationLevel) -> str:
    """레벨 설명 조회"""
    return LEVEL_DESCRIPTIONS.get(level, "알 수 없는 레벨")


def get_level_name_ko(level: AutomationLevel) -> str:
    """레벨 한글 이름 조회"""
    return LEVEL_NAMES_KO.get(level, "알 수 없음")
