"""
Financial calculation tools.

Valuation, dilution, IRR, and exit projection generation.
"""

import re
import subprocess
import sys
from typing import Any, Dict, List

from ._common import PROJECT_ROOT, _sanitize_filename, logger

TOOLS = [
    {
        "name": "calculate_valuation",
        "description": "다양한 방법론으로 기업가치를 계산합니다 (PER, EV/Revenue, EV/EBITDA 등)",
        "input_schema": {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["per", "ev_revenue", "ev_ebitda"],
                    "description": "밸류에이션 방법론",
                },
                "base_value": {
                    "type": "number",
                    "description": "기준 값 (순이익, 매출, EBITDA 등)",
                },
                "multiple": {
                    "type": "number",
                    "description": "적용할 배수",
                },
            },
            "required": ["method", "base_value", "multiple"],
        },
    },
    {
        "name": "calculate_dilution",
        "description": "SAFE 전환, 신규 투자 라운드 등으로 인한 지분 희석 효과를 계산합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_type": {
                    "type": "string",
                    "enum": ["safe", "new_round", "call_option"],
                    "description": "희석 이벤트 종류",
                },
                "current_shares": {
                    "type": "number",
                    "description": "현재 총 발행주식수",
                },
                "event_details": {
                    "type": "object",
                    "description": "이벤트 상세 정보 (investment_amount, valuation_cap 등)",
                },
            },
            "required": ["event_type", "current_shares", "event_details"],
        },
    },
    {
        "name": "calculate_irr",
        "description": "현금흐름 기반으로 IRR(내부수익률)과 멀티플을 계산합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cash_flows": {
                    "type": "array",
                    "description": "현금흐름 리스트 [{year: 2025, amount: -300000000}, {year: 2029, amount: 3150000000}]",
                    "items": {
                        "type": "object",
                        "properties": {
                            "year": {"type": "number"},
                            "amount": {"type": "number"},
                        },
                    },
                }
            },
            "required": ["cash_flows"],
        },
    },
    {
        "name": "generate_exit_projection",
        "description": "Exit 프로젝션 엑셀 파일을 생성합니다 (basic/advanced/complete 중 선택)",
        "input_schema": {
            "type": "object",
            "properties": {
                "projection_type": {
                    "type": "string",
                    "enum": ["basic", "advanced", "complete"],
                    "description": "프로젝션 타입 (basic: 기본, advanced: 부분매각+NPV, complete: SAFE+콜옵션)",
                },
                "parameters": {
                    "type": "object",
                    "description": "생성에 필요한 파라미터 (investment_amount, company_name, per_multiples 등)",
                },
            },
            "required": ["projection_type", "parameters"],
        },
    },
]


def execute_calculate_valuation(
    method: str, base_value: float, multiple: float
) -> Dict[str, Any]:
    """기업가치 계산 실행"""
    enterprise_value = float(base_value) * float(multiple)

    return {
        "success": True,
        "method": method,
        "base_value": base_value,
        "multiple": multiple,
        "enterprise_value": enterprise_value,
        "formatted": f"{enterprise_value:,.0f}",
    }


def execute_calculate_dilution(
    event_type: str, current_shares: float, event_details: Dict[str, Any]
) -> Dict[str, Any]:
    """지분 희석 계산 실행"""
    if event_type == "safe":
        safe_amount = event_details.get("safe_amount")
        valuation_cap = event_details.get("valuation_cap")
        new_shares = (safe_amount / valuation_cap) * current_shares

    elif event_type == "new_round":
        investment = event_details.get("investment_amount")
        pre_money = event_details.get("pre_money_valuation")
        new_shares = (investment / pre_money) * current_shares

    elif event_type == "call_option":
        new_shares = 0  # 콜옵션은 희석 없음 (주식 매입)

    else:
        return {"success": False, "error": f"Unknown event type: {event_type}"}

    total_shares = current_shares + new_shares
    dilution_ratio = new_shares / total_shares if total_shares > 0 else 0

    return {
        "success": True,
        "event_type": event_type,
        "current_shares": current_shares,
        "new_shares": new_shares,
        "total_shares": total_shares,
        "dilution_ratio": dilution_ratio,
        "dilution_percentage": f"{dilution_ratio * 100:.2f}%",
    }


def execute_calculate_irr(cash_flows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """IRR 계산 실행"""
    if len(cash_flows) < 2:
        return {
            "success": False,
            "error": "최소 2개의 현금흐름이 필요합니다 (투자 + 회수)",
        }

    # 간단한 IRR 계산 (Newton's method)
    def npv(rate, cfs):
        return sum(
            [
                cf["amount"] / ((1 + rate) ** (cf["year"] - cfs[0]["year"]))
                for cf in cfs
            ]
        )

    rate = 0.1
    for _ in range(100):
        npv_value = npv(rate, cash_flows)

        if abs(npv_value) < 1:
            break

        delta = 0.0001
        npv_delta = npv(rate + delta, cash_flows)
        derivative = (npv_delta - npv_value) / delta

        if abs(derivative) < 1e-10:
            break

        rate = rate - npv_value / derivative

    initial_investment = abs(cash_flows[0]["amount"])
    total_return = sum([cf["amount"] for cf in cash_flows[1:]])
    multiple = total_return / initial_investment if initial_investment > 0 else 0

    holding_period = cash_flows[-1]["year"] - cash_flows[0]["year"]

    return {
        "success": True,
        "irr": rate,
        "irr_percentage": f"{rate * 100:.1f}%",
        "multiple": multiple,
        "multiple_formatted": f"{multiple:.2f}x",
        "holding_period": holding_period,
        "cash_flows": cash_flows,
    }


def execute_generate_exit_projection(
    projection_type: str, parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """Exit 프로젝션 엑셀 생성 실행"""
    script_map = {
        "basic": "generate_exit_projection.py",
        "advanced": "generate_advanced_exit_projection.py",
        "complete": "generate_complete_exit_projection.py",
    }

    script_name = script_map.get(projection_type)
    if not script_name:
        return {
            "success": False,
            "error": f"Unknown projection type: {projection_type}. 허용: basic, advanced, complete",
        }

    script_path = PROJECT_ROOT / "scripts" / script_name

    allowed_params = {
        "investment_amount", "price_per_share", "shares", "total_shares",
        "net_income_company", "net_income_reviewer", "target_year",
        "company_name", "per_multiples", "output",
        "net_income_2029", "net_income_2030", "partial_exit_ratio", "discount_rate",
        "total_shares_before_safe", "safe_amount", "safe_valuation_cap",
        "call_option_price_multiplier",
    }

    cmd = [sys.executable, str(script_path)]

    for key, value in parameters.items():
        if key not in allowed_params:
            logger.warning(f"Rejected unknown parameter: {key}")
            continue

        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key):
            logger.warning(f"Invalid parameter key format: {key}")
            continue

        if key == "company_name":
            value = _sanitize_filename(str(value))
        elif key == "output":
            value = _sanitize_filename(str(value))
            if not value.endswith(".xlsx"):
                value += ".xlsx"

        cmd.append(f"--{key}")
        cmd.append(str(value))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        output_file = None
        for line in result.stdout.split("\n"):
            if "생성 완료" in line or "xlsx" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    output_file = parts[-1].strip()

        return {
            "success": True,
            "projection_type": projection_type,
            "output_file": output_file,
            "message": result.stdout,
        }

    except subprocess.CalledProcessError as e:
        return {"success": False, "error": e.stderr}


EXECUTORS = {
    "calculate_valuation": execute_calculate_valuation,
    "calculate_dilution": execute_calculate_dilution,
    "calculate_irr": execute_calculate_irr,
    "generate_exit_projection": execute_generate_exit_projection,
}
