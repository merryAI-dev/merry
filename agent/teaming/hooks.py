"""
Human-AI Teaming Hooks
Claude Agent SDK 패턴의 PreToolUse/PostToolUse 후크
"""

from typing import Any, Dict, Optional
import uuid
from datetime import datetime

from .level_config import (
    AutomationLevel,
    get_tool_level,
    LEVEL_DESCRIPTIONS,
    LEVEL_NAMES_KO,
)
from .mcp_server import (
    Checkpoint,
    CheckpointStatus,
    get_store,
)
from .trust_calculator import calculate_trust_score, should_auto_approve


# ========================================
# PreToolUse Hook
# ========================================

async def teaming_pre_tool_use_hook(
    tool_name: str,
    tool_input: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    도구 실행 전 후크 (Level 2 처리)

    Returns:
        Dict with keys:
        - decision: "allow" | "ask" | "deny"
        - checkpoint_id: 생성된 checkpoint ID (ask인 경우)
        - message: 사용자 메시지
        - metadata: 추가 메타데이터
    """
    session_id = context.get("session_id", "default")

    # 자동화 레벨 결정
    level = get_tool_level(tool_name)

    # 동적 레벨 조정
    level = _adjust_level_by_context(level, tool_input, context)

    # ========================================
    # Level 4: 즉시 실행
    # ========================================
    if level == AutomationLevel.LEVEL_4_FULL_AUTO:
        return {
            "decision": "allow",
            "checkpoint_id": None,
            "message": None,
            "metadata": {
                "automation_level": level.value,
                "level_name": level.name,
                "level_name_ko": LEVEL_NAMES_KO.get(level),
            }
        }

    # ========================================
    # Level 3: 즉시 실행 (PostToolUse에서 검토)
    # ========================================
    if level == AutomationLevel.LEVEL_3_HUMAN_VERIFIES:
        return {
            "decision": "allow",
            "checkpoint_id": None,
            "message": None,
            "metadata": {
                "automation_level": level.value,
                "level_name": level.name,
                "level_name_ko": LEVEL_NAMES_KO.get(level),
                "requires_post_review": True,
            }
        }

    # ========================================
    # Level 2: Checkpoint 생성 후 승인 대기
    # ========================================
    if level == AutomationLevel.LEVEL_2_AI_ASSISTS:
        store = get_store(session_id)

        checkpoint = Checkpoint(
            checkpoint_id=f"cp_{uuid.uuid4().hex[:12]}",
            tool_name=tool_name,
            automation_level=level.value,
            checkpoint_type="pre_execution",
            input_data=tool_input,
            ai_rationale=_generate_rationale(tool_name, tool_input, None),
            confidence_score=calculate_trust_score(tool_name, None),
            risk_indicators=_identify_input_risks(tool_input),
        )
        store.create(checkpoint)

        message = f"""## 승인 필요: {tool_name}

**자동화 레벨**: Level {level.value} ({LEVEL_NAMES_KO.get(level)})
**설명**: {LEVEL_DESCRIPTIONS.get(level)}
**신뢰도**: {checkpoint.confidence_score:.0%}

**Checkpoint ID**: `{checkpoint.checkpoint_id}`

{_format_input_summary(tool_input)}

{_format_risk_indicators(checkpoint.risk_indicators)}
"""

        return {
            "decision": "ask",
            "checkpoint_id": checkpoint.checkpoint_id,
            "message": message,
            "metadata": {
                "automation_level": level.value,
                "level_name": level.name,
                "level_name_ko": LEVEL_NAMES_KO.get(level),
                "checkpoint_id": checkpoint.checkpoint_id,
                "requires_approval": True,
                "confidence_score": checkpoint.confidence_score,
            }
        }

    # ========================================
    # Level 1: 거부
    # ========================================
    return {
        "decision": "deny",
        "checkpoint_id": None,
        "message": f"이 작업({tool_name})은 직접 수행해야 합니다.",
        "metadata": {
            "automation_level": level.value,
            "level_name": level.name,
            "level_name_ko": LEVEL_NAMES_KO.get(level),
        }
    }


# ========================================
# PostToolUse Hook
# ========================================

async def teaming_post_tool_use_hook(
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_result: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    도구 실행 후 후크 (Level 3 검토 + 감사 로깅)

    Returns:
        Dict with keys:
        - requires_review: 검토 필요 여부
        - auto_approved: 자동 승인 여부
        - checkpoint_id: 생성된 checkpoint ID
        - message: 사용자 메시지
        - metadata: 추가 메타데이터
    """
    session_id = context.get("session_id", "default")

    # 자동화 레벨 확인
    level = get_tool_level(tool_name)
    level = _adjust_level_by_context(level, tool_input, context)

    store = get_store(session_id)

    # ========================================
    # Level 3: 검토 필요 여부 확인
    # ========================================
    if level == AutomationLevel.LEVEL_3_HUMAN_VERIFIES:
        trust_score = calculate_trust_score(tool_name, tool_result)

        # 자동 승인 조건 충족
        if should_auto_approve(tool_name, trust_score):
            checkpoint = Checkpoint(
                checkpoint_id=f"cp_{uuid.uuid4().hex[:12]}",
                tool_name=tool_name,
                automation_level=level.value,
                checkpoint_type="post_execution",
                input_data=tool_input,
                output_data=tool_result,
                confidence_score=trust_score,
                status=CheckpointStatus.AUTO_APPROVED,
                ai_rationale=f"신뢰도 {trust_score:.0%}로 자동 승인됨",
            )
            store.create(checkpoint)
            store.resolve(checkpoint.checkpoint_id, CheckpointStatus.AUTO_APPROVED)

            return {
                "requires_review": False,
                "auto_approved": True,
                "checkpoint_id": checkpoint.checkpoint_id,
                "message": f"[Level 3] 신뢰도 {trust_score:.0%}로 자동 승인됨",
                "metadata": {
                    "automation_level": level.value,
                    "auto_approved": True,
                    "trust_score": trust_score,
                }
            }

        # 검토 필요
        checkpoint = Checkpoint(
            checkpoint_id=f"cp_{uuid.uuid4().hex[:12]}",
            tool_name=tool_name,
            automation_level=level.value,
            checkpoint_type="post_execution",
            input_data=tool_input,
            output_data=tool_result,
            ai_rationale=_generate_rationale(tool_name, tool_input, tool_result),
            confidence_score=trust_score,
            risk_indicators=_identify_output_risks(tool_result),
        )
        store.create(checkpoint)

        message = f"""## 결과 검토 필요: {tool_name}

**자동화 레벨**: Level {level.value} ({LEVEL_NAMES_KO.get(level)})
**신뢰도**: {trust_score:.0%}

**Checkpoint ID**: `{checkpoint.checkpoint_id}`

{_format_output_summary(tool_result)}

{_format_risk_indicators(checkpoint.risk_indicators)}
"""

        return {
            "requires_review": True,
            "auto_approved": False,
            "checkpoint_id": checkpoint.checkpoint_id,
            "message": message,
            "metadata": {
                "automation_level": level.value,
                "checkpoint_id": checkpoint.checkpoint_id,
                "requires_review": True,
                "trust_score": trust_score,
            }
        }

    # ========================================
    # Level 4: 로깅만 (감사 목적)
    # ========================================
    return {
        "requires_review": False,
        "auto_approved": True,
        "checkpoint_id": None,
        "message": None,
        "metadata": {
            "automation_level": level.value,
            "logged": True,
        }
    }


# ========================================
# 헬퍼 함수
# ========================================

def _adjust_level_by_context(
    level: AutomationLevel,
    tool_input: Dict[str, Any],
    context: Dict[str, Any]
) -> AutomationLevel:
    """
    컨텍스트 기반 동적 레벨 조정

    - 투자금액 10억 이상: 레벨 하향
    - 부정적 피드백 다수: 레벨 하향
    """
    # 투자금액 체크
    investment_amount = tool_input.get("investment_amount")
    if investment_amount:
        try:
            amount_억 = float(investment_amount) / 100_000_000
            if amount_억 >= 10:
                if level == AutomationLevel.LEVEL_4_FULL_AUTO:
                    return AutomationLevel.LEVEL_3_HUMAN_VERIFIES
                elif level == AutomationLevel.LEVEL_3_HUMAN_VERIFIES:
                    return AutomationLevel.LEVEL_2_AI_ASSISTS
        except (ValueError, TypeError):
            pass

    # 부정적 피드백 체크
    negative_feedback_count = context.get("negative_feedback_count", 0)
    if negative_feedback_count >= 3:
        if level == AutomationLevel.LEVEL_4_FULL_AUTO:
            return AutomationLevel.LEVEL_3_HUMAN_VERIFIES

    return level


def _generate_rationale(
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_result: Optional[Dict[str, Any]]
) -> str:
    """AI 근거 생성"""
    rationales = {
        "analyze_excel": "투자검토 엑셀 파일을 분석하여 핵심 데이터를 추출했습니다.",
        "analyze_peer_per": "유사 기업의 PER 데이터를 수집하여 비교 분석했습니다.",
        "analyze_company_diagnosis_sheet": "기업현황 진단시트를 분석하여 주요 지표를 추출했습니다.",
        "generate_exit_projection": "Exit 프로젝션 문서를 생성합니다. 입력값을 검토해주세요.",
        "analyze_and_generate_projection": "분석 및 프로젝션 생성을 수행합니다.",
        "write_company_diagnosis_report": "기업현황 진단 리포트를 생성합니다.",
        "create_company_diagnosis_draft": "기업현황 진단 초안을 작성합니다.",
        "update_company_diagnosis_draft": "기업현황 진단 초안을 업데이트합니다.",
        "generate_company_diagnosis_sheet_from_draft": "초안을 기반으로 진단시트를 생성합니다.",
    }

    if tool_name in rationales:
        return rationales[tool_name]
    elif "search" in tool_name:
        return "관련 정보를 검색하여 결과를 반환했습니다."
    elif "read" in tool_name or "extract" in tool_name:
        return "파일에서 데이터를 추출했습니다."
    elif "calculate" in tool_name:
        return "요청한 계산을 수행했습니다."
    else:
        return "도구 실행이 완료되었습니다." if tool_result else "도구 실행을 준비 중입니다."


def _identify_input_risks(tool_input: Dict[str, Any]) -> list:
    """입력 위험 요소 식별"""
    risks = []

    # 투자금액 체크
    if "investment_amount" in tool_input:
        try:
            amount = float(tool_input["investment_amount"])
            if amount >= 1_000_000_000:
                risks.append(f"투자금액이 큽니다: {amount/100_000_000:.1f}억원")
        except (ValueError, TypeError):
            pass

    # 필수 입력 누락 체크
    required_fields = ["company_name", "investment_amount", "target_year"]
    for field in required_fields:
        if field in tool_input and not tool_input[field]:
            risks.append(f"필수 입력 누락: {field}")

    # PER 멀티플 체크
    if "per_multiples" in tool_input:
        multiples = tool_input["per_multiples"]
        if isinstance(multiples, str):
            multiples = [float(x) for x in multiples.split(",")]
        if any(m > 30 for m in multiples):
            risks.append("높은 PER 멀티플 사용")

    return risks


def _identify_output_risks(tool_result: Dict[str, Any]) -> list:
    """출력 위험 요소 식별"""
    risks = []

    if not tool_result:
        risks.append("결과가 비어있습니다")
        return risks

    # 실행 실패
    if tool_result.get("success") is False:
        risks.append(f"실행 실패: {tool_result.get('error', 'Unknown')}")

    # 경고 메시지
    if tool_result.get("warnings"):
        for warning in tool_result["warnings"]:
            risks.append(f"경고: {warning}")

    # 데이터 누락
    if tool_result.get("data") and isinstance(tool_result["data"], dict):
        if len(tool_result["data"]) < 2:
            risks.append("반환된 데이터가 적습니다")

    # 수익률 관련 체크
    irr = tool_result.get("data", {}).get("irr") or tool_result.get("irr")
    if irr:
        try:
            irr_value = float(irr)
            if irr_value > 0.5:  # 50% 이상
                risks.append(f"높은 IRR: {irr_value:.1%}")
            elif irr_value < 0:
                risks.append(f"음수 IRR: {irr_value:.1%}")
        except (ValueError, TypeError):
            pass

    return risks


def _format_input_summary(tool_input: Dict[str, Any]) -> str:
    """입력 요약 포맷팅"""
    if not tool_input:
        return ""

    lines = ["### 입력 파라미터"]
    for key, value in tool_input.items():
        # 긴 값은 축약
        if isinstance(value, str) and len(value) > 100:
            value = value[:100] + "..."
        lines.append(f"- **{key}**: {value}")

    return "\n".join(lines)


def _format_output_summary(tool_result: Dict[str, Any]) -> str:
    """출력 요약 포맷팅"""
    if not tool_result:
        return "결과 없음"

    lines = ["### 실행 결과"]

    if tool_result.get("success") is not None:
        status = "성공" if tool_result["success"] else "실패"
        lines.append(f"- **상태**: {status}")

    if tool_result.get("error"):
        lines.append(f"- **에러**: {tool_result['error']}")

    if tool_result.get("data") and isinstance(tool_result["data"], dict):
        lines.append("- **데이터 필드**: " + ", ".join(tool_result["data"].keys()))

    return "\n".join(lines)


def _format_risk_indicators(risks: list) -> str:
    """위험 지표 포맷팅"""
    if not risks:
        return ""

    lines = ["### 주의 사항"]
    for risk in risks:
        lines.append(f"- {risk}")

    return "\n".join(lines)
