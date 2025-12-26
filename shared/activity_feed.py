"""
Team activity feed helper.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from shared.logging_config import get_logger

logger = get_logger("activity_feed")

try:
    from agent.supabase_storage import get_supabase_client
    SUPABASE_AVAILABLE = True
except Exception:
    SUPABASE_AVAILABLE = False


def _safe_json_loads(value, default=None):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def get_recent_activity(team_id: str, limit: int = 30) -> List[Dict[str, str]]:
    if not team_id:
        return []

    if SUPABASE_AVAILABLE:
        client = get_supabase_client()
        if client:
            try:
                response = (
                    client.table("chat_messages")
                    .select("session_id, role, content, metadata, created_at")
                    .eq("user_id", team_id)
                    .order("created_at", desc=True)
                    .limit(limit)
                    .execute()
                )
                activities = []
                for row in response.data or []:
                    meta = _safe_json_loads(row.get("metadata"), {}) or {}
                    activities.append({
                        "session_id": row.get("session_id", ""),
                        "role": row.get("role", ""),
                        "content": row.get("content", ""),
                        "created_at": row.get("created_at", ""),
                        "member": meta.get("member") or meta.get("created_by") or "",
                    })
                return activities
            except Exception as exc:
                logger.warning(f"Supabase activity feed failed: {exc}")

    # Local fallback: read chat_history/<team_id>/session_*.json
    activities: List[Dict[str, str]] = []
    storage_dir = Path("chat_history") / team_id
    if not storage_dir.exists():
        return []

    for path in storage_dir.glob("session_*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        session_id = data.get("session_id") or path.stem.replace("session_", "")
        for msg in data.get("messages", []) or []:
            activities.append({
                "session_id": session_id,
                "role": msg.get("role", ""),
                "content": msg.get("content", ""),
                "created_at": msg.get("timestamp", ""),
                "member": (msg.get("metadata") or {}).get("member", ""),
            })

    activities.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return activities[:limit]
