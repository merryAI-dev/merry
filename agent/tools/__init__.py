"""
Agent tools package.

Aggregates all domain-specific tool modules and provides backward-compatible
entry points: register_tools(), execute_tool(), and selected re-exports.
"""

from typing import Any, Dict, List

from ._common import logger

from . import (
    diagnosis_tools,
    discovery_tools,
    extraction_tools,
    financial_tools,
    pdf_tools,
    session_tools,
    stock_tools,
    underwriter_tools,
)

_ALL_MODULES = [
    extraction_tools,
    financial_tools,
    diagnosis_tools,
    underwriter_tools,
    pdf_tools,
    session_tools,
    stock_tools,
    discovery_tools,
]

# Aggregate all executors from domain modules
TOOL_EXECUTORS: Dict[str, Any] = {}
for _mod in _ALL_MODULES:
    TOOL_EXECUTORS.update(_mod.EXECUTORS)


def register_tools(mode: str = None) -> List[Dict[str, Any]]:
    """Register all available tools, optionally filtered by mode.

    Args:
        mode: Optional mode filter (exit, peer, diagnosis, report, discovery, voice).
              If None, returns all tools.
    """
    tools = []
    for mod in _ALL_MODULES:
        tools.extend(mod.TOOLS)

    if mode and mode in TOOL_MODE_MAP:
        allowed = set(TOOL_MODE_MAP[mode])
        return [t for t in tools if t["name"] in allowed]

    return tools


def execute_tool(tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """Tool execution dispatcher."""
    executor = TOOL_EXECUTORS.get(tool_name)

    if not executor:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}

    try:
        return executor(**tool_input)
    except Exception as e:
        return {"success": False, "error": f"Tool execution error: {str(e)}"}


# ========================================
# Mode-based tool filtering (token savings)
# ========================================

TOOL_MODE_MAP = {
    "exit": [
        "read_excel_as_text",
        "analyze_excel",
        "analyze_and_generate_projection",
        "calculate_valuation",
        "calculate_dilution",
        "calculate_irr",
        "generate_exit_projection",
        "read_pdf_as_text",
        "parse_pdf_dolphin",
        "extract_pdf_tables",
        "start_analysis_session",
        "add_supplementary_data",
        "get_analysis_status",
        "complete_analysis",
    ],
    "peer": [
        "get_stock_financials",
        "analyze_peer_per",
        "read_pdf_as_text",
        "search_underwriter_opinion",
        "search_underwriter_opinion_similar",
        "extract_pdf_market_evidence",
        "fetch_underwriter_opinion_data",
    ],
    "diagnosis": [
        "create_company_diagnosis_draft",
        "update_company_diagnosis_draft",
        "generate_company_diagnosis_sheet_from_draft",
        "analyze_company_diagnosis_sheet",
        "write_company_diagnosis_report",
        "read_pdf_as_text",
    ],
    "report": [
        "read_excel_as_text",
        "analyze_excel",
        "read_pdf_as_text",
        "search_underwriter_opinion",
        "search_underwriter_opinion_similar",
        "extract_pdf_market_evidence",
        "fetch_underwriter_opinion_data",
        "get_stock_financials",
        "analyze_peer_per",
        "start_analysis_session",
        "add_supplementary_data",
        "get_analysis_status",
        "complete_analysis",
    ],
    "discovery": [
        "analyze_government_policy",
        "search_iris_plus_metrics",
        "map_policy_to_iris",
        "generate_industry_recommendation",
        "read_pdf_as_text",
    ],
}

# ========================================
# Backward-compatible re-exports
# ========================================

from .underwriter_tools import (
    _resolve_underwriter_data_path,
    execute_fetch_underwriter_opinion_data,
    execute_search_underwriter_opinion_similar,
)

__all__ = [
    "register_tools",
    "execute_tool",
    "TOOL_EXECUTORS",
    "_resolve_underwriter_data_path",
    "execute_search_underwriter_opinion_similar",
    "execute_fetch_underwriter_opinion_data",
]
