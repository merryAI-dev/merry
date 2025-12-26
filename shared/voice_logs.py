"""
Voice agent logging helpers (daily check-ins / 1:1)
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from shared.logging_config import get_logger

logger = get_logger("voice_logs")

try:
    from agent.supabase_storage import get_supabase_client
    SUPABASE_AVAILABLE = True
except Exception as exc:
    SUPABASE_AVAILABLE = False
    logger.warning(f"Supabase storage import failed: {exc}")


VOICE_LOG_ROOT = Path("chat_history") / "voice"
VOICE_LOG_TABLE = "voice_logs"
VOICE_CHECKIN_TABLE = "voice_checkins"


def _safe_user_id(user_id: str) -> str:
    if not user_id:
        return "anonymous"
    return user_id.replace("/", "_").replace("\\", "_").replace("..", "_")


def _get_user_dir(user_id: str) -> Path:
    user_dir = VOICE_LOG_ROOT / _safe_user_id(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def _append_voice_log_supabase(user_id: str, entry: Dict[str, str]) -> bool:
    if not SUPABASE_AVAILABLE:
        return False

    client = get_supabase_client()
    if not client:
        return False

    payload = {
        "user_id": user_id,
        "mode": entry.get("mode"),
        "user_text": entry.get("user_text"),
        "assistant_text": entry.get("assistant_text"),
        "transcript": entry.get("transcript"),
        "session_id": entry.get("session_id"),
        "created_at": datetime.now().isoformat(),
    }

    try:
        client.table(VOICE_LOG_TABLE).insert(payload).execute()
        return True
    except Exception as exc:
        logger.warning(f"Supabase voice log insert failed: {exc}")
        return False


def _append_checkin_summary_supabase(user_id: str, entry: Dict[str, Any]) -> bool:
    if not SUPABASE_AVAILABLE:
        return False

    client = get_supabase_client()
    if not client:
        return False

    payload = {
        "user_id": user_id,
        "mode": entry.get("mode"),
        "session_id": entry.get("session_id"),
        "summary_date": entry.get("summary_date"),
        "summary_json": entry.get("summary_json"),
        "created_at": datetime.now().isoformat(),
    }

    try:
        client.table(VOICE_CHECKIN_TABLE).insert(payload).execute()
        return True
    except Exception as exc:
        logger.warning(f"Supabase checkin summary insert failed: {exc}")
        return False


def append_voice_log(user_id: str, entry: Dict[str, str]) -> Path:
    """Append a voice log entry as JSONL and attempt Supabase insert."""
    user_dir = _get_user_dir(user_id)
    path = user_dir / "voice_log.jsonl"
    payload = {
        "timestamp": datetime.now().isoformat(),
        **entry,
    }

    _append_voice_log_supabase(user_id, payload)

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return path


def append_checkin_summary(user_id: str, entry: Dict[str, Any]) -> Path:
    """Append a check-in summary entry and attempt Supabase insert."""
    user_dir = _get_user_dir(user_id)
    path = user_dir / "checkin_summary.jsonl"
    payload = {
        "timestamp": datetime.now().isoformat(),
        **entry,
    }

    _append_checkin_summary_supabase(user_id, payload)

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return path


def _read_log_lines(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    entries: List[Dict[str, str]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _get_day_range(day_offset: int = 1) -> tuple[datetime, datetime]:
    target_date = date.today() - timedelta(days=day_offset)
    start = datetime.combine(target_date, datetime.min.time())
    end = start + timedelta(days=1)
    return start, end


def _fetch_supabase_rows(
    table: str,
    select: str,
    user_id: str,
    order_column: str = "created_at",
    desc: bool = True,
    page_size: int = 500,
    max_rows: Optional[int] = None,
) -> List[Dict[str, Any]]:
    if not SUPABASE_AVAILABLE:
        return []

    client = get_supabase_client()
    if not client:
        return []

    rows: List[Dict[str, Any]] = []
    offset = 0
    page_size = max(page_size, 1)

    while True:
        if max_rows is not None and len(rows) >= max_rows:
            break

        fetch_size = page_size
        if max_rows is not None:
            remaining = max_rows - len(rows)
            if remaining <= 0:
                break
            fetch_size = min(fetch_size, remaining)

        end = offset + fetch_size - 1
        try:
            response = (
                client.table(table)
                .select(select)
                .eq("user_id", user_id)
                .order(order_column, desc=desc)
                .range(offset, end)
                .execute()
            )
            batch = response.data or []
        except Exception as exc:
            logger.warning(f"Supabase {table} fetch failed: {exc}")
            break

        rows.extend(batch)
        if len(batch) < fetch_size:
            break

        offset += fetch_size

    return rows


def _get_voice_logs_between_supabase(
    user_id: str,
    start: datetime,
    end: datetime,
    limit: int,
) -> List[Dict[str, str]]:
    if not SUPABASE_AVAILABLE:
        return []

    client = get_supabase_client()
    if not client:
        return []

    try:
        response = client.table(VOICE_LOG_TABLE).select("*").eq(
            "user_id", user_id
        ).gte(
            "created_at", start.isoformat()
        ).lt(
            "created_at", end.isoformat()
        ).order("created_at", desc=True).limit(limit).execute()
        rows = response.data or []
        for row in rows:
            if "created_at" in row and "timestamp" not in row:
                row["timestamp"] = row["created_at"]
        return rows
    except Exception as exc:
        logger.warning(f"Supabase voice log range fetch failed: {exc}")
        return []


def _get_voice_logs_between(
    user_id: str,
    start: datetime,
    end: datetime,
    limit: int,
) -> List[Dict[str, str]]:
    entries = _get_voice_logs_between_supabase(user_id, start, end, limit)
    if entries:
        return [
            e for e in entries
            if e.get("timestamp")
            and start.isoformat() <= e.get("timestamp") < end.isoformat()
        ][:limit]

    user_dir = _get_user_dir(user_id)
    path = user_dir / "voice_log.jsonl"
    entries = _read_log_lines(path)
    if not entries:
        return []
    filtered = [
        e for e in entries
        if e.get("timestamp")
        and start.isoformat() <= e.get("timestamp") < end.isoformat()
    ]
    return filtered[-limit:][::-1]


def _get_chat_messages_between_supabase(
    user_id: str,
    start: datetime,
    end: datetime,
    limit: int,
) -> List[Dict[str, str]]:
    if not SUPABASE_AVAILABLE:
        return []

    client = get_supabase_client()
    if not client:
        return []

    try:
        response = client.table("chat_messages").select(
            "role, content, created_at"
        ).eq(
            "user_id", user_id
        ).gte(
            "created_at", start.isoformat()
        ).lt(
            "created_at", end.isoformat()
        ).order(
            "created_at", desc=True
        ).limit(limit).execute()
        rows = response.data or []
        for row in rows:
            row["timestamp"] = row.get("created_at")
        return rows
    except Exception as exc:
        logger.warning(f"Supabase chat_messages fetch failed: {exc}")
        return []


def _get_recent_chat_messages_supabase(
    user_id: str,
    limit: Optional[int],
) -> List[Dict[str, str]]:
    rows = _fetch_supabase_rows(
        "chat_messages",
        "role, content, created_at",
        user_id,
        max_rows=limit,
    )
    for row in rows:
        row["timestamp"] = row.get("created_at")
    return rows


def get_checkin_context(
    user_id: str,
    day_offset: int = 1,
    limit: int = 20,
) -> Dict[str, List[Dict[str, str]]]:
    start, end = _get_day_range(day_offset)
    voice_logs = _get_voice_logs_between(user_id, start, end, limit)
    chat_messages = _get_chat_messages_between_supabase(user_id, start, end, limit)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "voice_logs": voice_logs,
        "chat_messages": chat_messages,
    }


def get_checkin_context_days(
    user_id: str,
    days: int = 7,
    limit: int = 50,
) -> Dict[str, List[Dict[str, str]]]:
    end = datetime.now()
    start = end - timedelta(days=days)
    voice_logs = _get_voice_logs_between(user_id, start, end, limit)
    chat_messages = _get_chat_messages_between_supabase(user_id, start, end, limit)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "voice_logs": voice_logs,
        "chat_messages": chat_messages,
    }


def get_checkin_context_all(
    user_id: str,
    limit: Optional[int] = 100,
) -> Dict[str, List[Dict[str, str]]]:
    voice_logs = get_recent_voice_logs(user_id, limit=limit)
    chat_messages = _get_recent_chat_messages_supabase(user_id, limit=limit)
    return {
        "start": "",
        "end": "",
        "voice_logs": voice_logs,
        "chat_messages": chat_messages,
    }


def _get_latest_checkin_summary_supabase(
    user_id: str,
    start: datetime,
    end: datetime,
) -> Optional[Dict[str, str]]:
    if not SUPABASE_AVAILABLE:
        return None

    client = get_supabase_client()
    if not client:
        return None

    target_date = start.date().isoformat()
    try:
        response = client.table(VOICE_CHECKIN_TABLE).select("*").eq(
            "user_id", user_id
        ).eq(
            "summary_date", target_date
        ).order("created_at", desc=True).limit(1).execute()
        rows = response.data or []
        if not rows:
            return None
        row = rows[0]
        if "created_at" in row and "timestamp" not in row:
            row["timestamp"] = row["created_at"]
        return row
    except Exception as exc:
        logger.warning(f"Supabase checkin summary fetch failed: {exc}")
        return None


def get_latest_checkin_summary(user_id: str, day_offset: int = 1) -> Optional[Dict[str, str]]:
    start, end = _get_day_range(day_offset)
    supa = _get_latest_checkin_summary_supabase(user_id, start, end)
    if supa:
        return supa

    user_dir = _get_user_dir(user_id)
    path = user_dir / "checkin_summary.jsonl"
    entries = _read_log_lines(path)
    if not entries:
        return None

    target_date = start.date().isoformat()
    filtered = [
        e for e in entries
        if e.get("summary_date") == target_date
        or (
            e.get("timestamp")
            and start.isoformat() <= e.get("timestamp") < end.isoformat()
        )
    ]
    return filtered[-1] if filtered else None


def _normalize_summary_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    summary_json = entry.get("summary_json")
    if isinstance(summary_json, str):
        try:
            summary_json = json.loads(summary_json)
        except json.JSONDecodeError:
            summary_json = {}
    entry["summary_json"] = summary_json

    if not entry.get("summary_date"):
        timestamp = entry.get("timestamp") or entry.get("created_at")
        if isinstance(timestamp, str) and len(timestamp) >= 10:
            entry["summary_date"] = timestamp[:10]

    if "created_at" in entry and "timestamp" not in entry:
        entry["timestamp"] = entry["created_at"]
    return entry


def _get_checkin_summaries_supabase(
    user_id: str,
    limit: Optional[int],
) -> List[Dict[str, Any]]:
    rows = _fetch_supabase_rows(
        VOICE_CHECKIN_TABLE,
        "*",
        user_id,
        max_rows=limit,
    )
    return [_normalize_summary_entry(row) for row in rows]


def _get_checkin_summaries_local(user_id: str, limit: Optional[int]) -> List[Dict[str, Any]]:
    user_dir = _get_user_dir(user_id)
    path = user_dir / "checkin_summary.jsonl"
    entries = _read_log_lines(path)
    if not entries:
        return []
    normalized = [_normalize_summary_entry(entry) for entry in entries]
    ordered = list(reversed(normalized))
    return ordered if limit is None else ordered[:limit]


def get_checkin_summaries(user_id: str, limit: Optional[int] = 30) -> List[Dict[str, Any]]:
    summaries = _get_checkin_summaries_supabase(user_id, limit)
    if summaries:
        return summaries
    return _get_checkin_summaries_local(user_id, limit)


def _shorten(text: Optional[str], limit: int = 160) -> str:
    if not text:
        return ""
    text = text.strip().replace("\n", " ")
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def build_checkin_context_text(
    context: Dict[str, List[Dict[str, str]]],
    max_items: Optional[int] = 8,
) -> str:
    voice_logs = context.get("voice_logs", [])
    chat_messages = context.get("chat_messages", [])

    lines: List[str] = []
    voice_slice = voice_logs if max_items is None else voice_logs[:max_items]
    for entry in voice_slice:
        user_text = _shorten(entry.get("user_text"))
        assistant_text = _shorten(entry.get("assistant_text"))
        if user_text:
            lines.append(f"- 사용자(음성): {user_text}")
        if assistant_text:
            lines.append(f"- 에이전트(음성): {assistant_text}")

    chat_slice = chat_messages if max_items is None else chat_messages[:max_items]
    for entry in chat_slice:
        role = entry.get("role")
        if role == "tool":
            continue
        content = _shorten(entry.get("content"))
        if content:
            lines.append(f"- {role}: {content}")

    if max_items is None:
        return "\n".join(lines).strip()

    return "\n".join(lines[: max_items * 2]).strip()


def build_checkin_summaries_context_text(
    summaries: List[Dict[str, Any]],
    max_items: Optional[int] = 10,
) -> str:
    if not summaries:
        return ""

    lines: List[str] = []
    summary_slice = summaries if max_items is None else summaries[:max_items]
    for entry in summary_slice:
        summary_date = entry.get("summary_date") or ""
        summary_text = build_checkin_summary_text(entry)
        if not summary_text:
            continue
        label = f"[{summary_date}]" if summary_date else "[체크인]"
        lines.append(label)
        lines.append(summary_text)

    return "\n".join(lines)


def build_checkin_summary_text(summary: Dict[str, str]) -> str:
    if not summary:
        return ""
    summary_json = summary.get("summary_json") or {}
    if isinstance(summary_json, str):
        try:
            summary_json = json.loads(summary_json)
        except json.JSONDecodeError:
            summary_json = {}

    lines = []
    if summary_json.get("yesterday_summary"):
        lines.append(f"- 어제: {summary_json.get('yesterday_summary')}")
    if summary_json.get("learnings"):
        items = summary_json.get("learnings")
        if isinstance(items, list) and items:
            lines.append(f"- 학습: {', '.join(items[:3])}")
    if summary_json.get("emotion_state"):
        lines.append(f"- 감정: {summary_json.get('emotion_state')}")
    if summary_json.get("team_tasks"):
        items = summary_json.get("team_tasks")
        if isinstance(items, list) and items:
            lines.append(f"- 팀 과업: {', '.join(items[:3])}")
    if summary_json.get("today_priorities"):
        items = summary_json.get("today_priorities")
        if isinstance(items, list) and items:
            lines.append(f"- 우선순위: {', '.join(items[:3])}")
    if summary_json.get("next_actions"):
        items = summary_json.get("next_actions")
        if isinstance(items, list) and items:
            lines.append(f"- 다음: {', '.join(items[:3])}")

    return "\n".join(lines)

def _get_recent_voice_logs_supabase(
    user_id: str,
    limit: Optional[int],
) -> List[Dict[str, str]]:
    rows = _fetch_supabase_rows(
        VOICE_LOG_TABLE,
        "*",
        user_id,
        max_rows=limit,
    )
    for row in rows:
        if "created_at" in row and "timestamp" not in row:
            row["timestamp"] = row["created_at"]
    return rows


def get_recent_voice_logs(user_id: str, limit: Optional[int] = 20) -> List[Dict[str, str]]:
    entries = _get_recent_voice_logs_supabase(user_id, limit)
    if entries:
        return entries

    user_dir = _get_user_dir(user_id)
    path = user_dir / "voice_log.jsonl"
    entries = _read_log_lines(path)
    if not entries:
        return []
    ordered = list(reversed(entries))
    return ordered if limit is None else ordered[:limit]


def get_latest_checkin(user_id: str, modes: Iterable[str] = ("checkin", "1on1")) -> Optional[Dict[str, str]]:
    entries = get_recent_voice_logs(user_id, limit=50)
    for entry in entries:
        if entry.get("mode") in modes:
            return entry
    return None
