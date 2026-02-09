"""
Interactive analysis session tools.

Session lifecycle management for progressive investment analysis.
"""

from typing import Any, Dict

from ._common import logger

TOOLS = [
    {
        "name": "start_analysis_session",
        "description": "대화형 투자 분석 세션을 시작합니다. 여러 파일과 텍스트 입력을 받아서 점진적으로 분석을 완성합니다. 세션 ID를 반환하며, 이후 add_supplementary_data와 함께 사용합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "initial_pdf_path": {
                    "type": "string",
                    "description": "초기 분석할 PDF 파일 경로 (선택)",
                },
                "max_pages": {
                    "type": "integer",
                    "description": "PDF 분석할 최대 페이지 수 (기본값: 30)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "add_supplementary_data",
        "description": "기존 분석 세션에 추가 데이터를 입력합니다. PDF 파일 또는 텍스트(재무 데이터, Cap Table, 투자 조건 등)를 추가할 수 있습니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "분석 세션 ID (start_analysis_session에서 반환)",
                },
                "pdf_path": {
                    "type": "string",
                    "description": "추가할 PDF 파일 경로 (선택)",
                },
                "text_input": {
                    "type": "string",
                    "description": "추가할 텍스트 데이터 (선택). 예: '2024년 매출 100억, 순이익 15억'",
                },
                "data_type": {
                    "type": "string",
                    "enum": ["financial", "cap_table", "investment_terms", "general"],
                    "description": "텍스트 데이터 유형 (기본값: general)",
                },
                "max_pages": {
                    "type": "integer",
                    "description": "PDF 분석할 최대 페이지 수 (기본값: 30)",
                },
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "get_analysis_status",
        "description": "분석 세션의 현재 상태를 확인합니다. 어떤 데이터가 수집되었고, 어떤 데이터가 부족한지 알려줍니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "분석 세션 ID",
                }
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "complete_analysis",
        "description": "분석 세션을 완료하고 최종 분석 결과를 반환합니다. 필수 데이터가 부족하면 부족한 항목을 안내합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "분석 세션 ID",
                }
            },
            "required": ["session_id"],
        },
    },
]


def execute_start_analysis_session(
    initial_pdf_path: str = None, max_pages: int = 30
) -> Dict[str, Any]:
    """대화형 투자 분석 세션 시작"""
    try:
        from dolphin_service.processor import get_or_create_session

        session = get_or_create_session()

        result = {
            "success": True,
            "session_id": session.session_id,
            "message": "새 분석 세션이 시작되었습니다.",
        }

        if initial_pdf_path:
            status = session.add_pdf(initial_pdf_path, max_pages)
            all_missing = status.get("critical_missing", []) + status.get("optional_missing", [])
            result.update(
                {
                    "initial_file_analyzed": True,
                    "status": status.get("status"),
                    "message": status.get("message"),
                    "collected_data": status.get("accumulated_data", {}),
                    "missing_data": all_missing,
                }
            )

            if all_missing:
                result["next_steps"] = [
                    f"- {item['name']}: {item['suggestion']}" for item in all_missing
                ]
        else:
            result["next_steps"] = [
                "PDF 파일을 업로드하거나 add_supplementary_data 도구로 데이터를 추가하세요.",
                "예: 재무 데이터, Cap Table, 투자 조건 등",
            ]

        return result

    except Exception as e:
        logger.exception("Analysis session start failed")
        return {"success": False, "error": f"세션 시작 실패: {str(e)}"}


def execute_add_supplementary_data(
    session_id: str,
    pdf_path: str = None,
    text_input: str = None,
    data_type: str = "general",
    max_pages: int = 30,
) -> Dict[str, Any]:
    """분석 세션에 추가 데이터 입력"""
    try:
        from dolphin_service.processor import get_or_create_session

        session = get_or_create_session(session_id)

        if session.session_id != session_id:
            return {
                "success": False,
                "error": f"세션 '{session_id}'를 찾을 수 없습니다. start_analysis_session으로 새 세션을 시작하세요.",
            }

        if not pdf_path and not text_input:
            return {"success": False, "error": "pdf_path 또는 text_input 중 하나는 필수입니다."}

        result = {"success": True, "session_id": session_id}

        if pdf_path:
            status = session.add_pdf(pdf_path, max_pages)
            result.update(
                {
                    "file_added": pdf_path,
                    "status": status.get("status"),
                    "message": status.get("message"),
                }
            )

        if text_input:
            status = session.add_text_input(text_input, data_type)
            result.update(
                {
                    "text_added": True,
                    "data_type": data_type,
                    "status": status.get("status"),
                    "message": status.get("message"),
                }
            )

        current_status = session._get_status()
        all_missing = current_status.get("critical_missing", []) + current_status.get(
            "optional_missing", []
        )
        result.update(
            {
                "collected_data": current_status.get("accumulated_data", {}),
                "missing_data": all_missing,
            }
        )

        if all_missing:
            result["next_steps"] = [
                f"- {item['name']}: {item['suggestion']}" for item in all_missing
            ]
        else:
            result["next_steps"] = [
                "모든 필수 데이터가 수집되었습니다. complete_analysis를 호출하세요."
            ]

        return result

    except Exception as e:
        logger.exception("Supplementary data add failed")
        return {"success": False, "error": f"데이터 추가 실패: {str(e)}"}


def execute_get_analysis_status(session_id: str) -> Dict[str, Any]:
    """분석 세션 상태 확인"""
    try:
        from dolphin_service.processor import get_or_create_session

        session = get_or_create_session(session_id)

        if session.session_id != session_id:
            return {"success": False, "error": f"세션 '{session_id}'를 찾을 수 없습니다."}

        status = session._get_status()

        return {
            "success": True,
            "session_id": session_id,
            "status": status.get("status"),
            "message": status.get("message"),
            "collected_data": status.get("accumulated_data", {}),
            "source_files": session.accumulated_data.get("source_files", []),
            "text_inputs_count": len(session.accumulated_data.get("text_inputs", [])),
            "critical_missing": status.get("critical_missing", []),
            "optional_missing": status.get("optional_missing", []),
        }

    except Exception as e:
        logger.exception("Analysis status check failed")
        return {"success": False, "error": f"상태 확인 실패: {str(e)}"}


def execute_complete_analysis(session_id: str) -> Dict[str, Any]:
    """분석 세션 완료 및 최종 결과 반환"""
    try:
        from dolphin_service.processor import get_or_create_session

        session = get_or_create_session(session_id)

        if session.session_id != session_id:
            return {"success": False, "error": f"세션 '{session_id}'를 찾을 수 없습니다."}

        return session.get_final_analysis()

    except Exception as e:
        logger.exception("Analysis completion failed")
        return {"success": False, "error": f"분석 완료 실패: {str(e)}"}


EXECUTORS = {
    "start_analysis_session": execute_start_analysis_session,
    "add_supplementary_data": execute_add_supplementary_data,
    "get_analysis_status": execute_get_analysis_status,
    "complete_analysis": execute_complete_analysis,
}
