"""
Session utilities for loading shared sessions into UI state.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List

import streamlit as st


def _build_ui_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    ui_messages = []
    for msg in messages:
        if msg.get("role") not in ["user", "assistant"]:
            continue
        ui_messages.append(
            {
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            }
        )
    return ui_messages


def load_session_by_id(agent, session_id: str) -> bool:
    if not agent or not session_id:
        return False

    memory = agent.memory
    session_data = memory.load_session(session_id)
    if not session_data:
        return False

    messages = session_data.get("messages", []) or []
    ui_messages = _build_ui_messages(messages)

    st.session_state.exit_messages = list(ui_messages)
    st.session_state.peer_messages = list(ui_messages)
    st.session_state.diagnosis_messages = list(ui_messages)
    st.session_state.report_messages = list(ui_messages)

    st.session_state.projection_data = None
    st.session_state.peer_analysis_result = None
    st.session_state.diagnosis_analysis_result = None
    st.session_state.diagnosis_draft_path = None
    st.session_state.diagnosis_draft_progress = None
    st.session_state.report_evidence = None
    st.session_state.report_deep_analysis = None
    st.session_state.report_deep_error = None
    st.session_state.report_deep_step = 0

    memory.session_id = session_data.get("session_id", session_id)
    memory.session_metadata = dict(session_data)
    memory.session_metadata["session_id"] = memory.session_id
    memory.session_metadata["user_id"] = memory.user_id
    memory.current_session_file = memory.storage_dir / f"session_{memory.session_id}.json"

    if hasattr(agent, "context"):
        agent.context["analyzed_files"] = memory.session_metadata.get("analyzed_files", [])
        agent.context["cached_results"] = memory.cached_results

    agent.conversation_history = []
    for msg in ui_messages:
        agent.conversation_history.append(
            {
                "role": msg.get("role"),
                "content": msg.get("content", ""),
            }
        )

    user_info = session_data.get("user_info", {})
    if user_info.get("nickname") and user_info.get("company"):
        st.session_state.exit_user_info_collected = True
    else:
        st.session_state.exit_user_info_collected = False
    st.session_state.exit_show_welcome = not st.session_state.exit_user_info_collected

    analyzed_files = session_data.get("analyzed_files", []) or []
    project_root = Path(__file__).resolve().parent.parent
    temp_root = (project_root / "temp").resolve()
    last_pdf = None
    last_excel = None
    for path_str in reversed(analyzed_files):
        path = Path(path_str)
        try:
            resolved = path.resolve()
            resolved.relative_to(temp_root)
            if not resolved.is_file():
                continue
        except Exception:
            continue

        if resolved.suffix.lower() == ".pdf" and not last_pdf:
            last_pdf = resolved
        if resolved.suffix.lower() in [".xlsx", ".xls"] and not last_excel:
            last_excel = resolved
        if last_pdf and last_excel:
            break

    if last_pdf:
        st.session_state.peer_pdf_path = str(last_pdf)
        st.session_state.peer_pdf_name = last_pdf.name
        st.session_state.report_file_path = str(last_pdf)
        st.session_state.report_file_name = last_pdf.name
    elif last_excel:
        st.session_state.report_file_path = str(last_excel)
        st.session_state.report_file_name = last_excel.name
    if last_excel:
        st.session_state.uploaded_file_path = str(last_excel)
        st.session_state.uploaded_file_name = last_excel.name
        st.session_state.diagnosis_excel_path = str(last_excel)
        st.session_state.diagnosis_excel_name = last_excel.name

    return True
