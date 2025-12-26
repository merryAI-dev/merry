"""
Team task store backed by Supabase chat_messages or local JSON fallback.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, date, time
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo


STATUS_ORDER = {
    "todo": 1,
    "in_progress": 2,
    "done": 3,
    "blocked": 2,
}

STATUS_LABELS = {
    "todo": "진행 전",
    "in_progress": "진행 중",
    "done": "완료",
    "blocked": "진행 중",
}

KST = ZoneInfo("Asia/Seoul")


def normalize_status(status: str) -> str:
    if status == "blocked":
        return "in_progress"
    return status or "todo"


def format_remaining_kst(due_date: str) -> str:
    if not due_date:
        return ""
    try:
        if "T" in due_date:
            due_dt = datetime.fromisoformat(due_date)
        else:
            due_dt = datetime.combine(date.fromisoformat(due_date), time(23, 59, 59))
    except ValueError:
        return ""

    if due_dt.tzinfo is None:
        due_dt = due_dt.replace(tzinfo=KST)
    now = datetime.now(tz=KST)
    delta = due_dt - now
    seconds = int(delta.total_seconds())

    if seconds >= 0:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        if days > 0:
            return f"남은 {days}일 {hours}시간"
        return f"남은 {hours}시간"

    seconds = abs(seconds)
    days = seconds // 86400
    if days == 0:
        return "마감 지남"
    return f"마감 지남 {days}일"


class TeamTaskStore:
    def __init__(self, team_id: str, local_dir: str = "temp/team_tasks"):
        self.team_id = team_id or "team_1"
        self.session_id = f"tasks_{self.team_id}"
        self.local_path = Path(local_dir) / f"{self.team_id}.json"
        self.local_path.parent.mkdir(parents=True, exist_ok=True)
        self._session_created = False

        try:
            from agent.supabase_storage import SupabaseStorage
            self.db = SupabaseStorage(user_id=self.team_id)
            if not self.db.available:
                self.db = None
        except Exception:
            self.db = None

    def _ensure_session(self) -> None:
        if self.db and not self._session_created:
            self.db.create_session(self.session_id, {"type": "team_tasks"})
            self._session_created = True

    def list_tasks(self, include_done: bool = False, limit: int = 50) -> List[Dict[str, str]]:
        tasks: Dict[str, Dict[str, str]] = {}

        if self.db:
            self._ensure_session()
            messages = self.db.get_messages(self.session_id)
            for msg in messages:
                if msg.get("role") != "team_task":
                    continue
                meta = msg.get("metadata") or {}
                task_id = meta.get("task_id")
                if not task_id:
                    continue
                current = tasks.get(task_id)
                if not current:
                    tasks[task_id] = {
                        "id": task_id,
                        "title": meta.get("title") or msg.get("content", ""),
                        "status": meta.get("status", "todo"),
                        "owner": meta.get("owner", ""),
                        "due_date": meta.get("due_date", ""),
                        "notes": meta.get("notes", ""),
                        "updated_at": meta.get("updated_at") or meta.get("created_at") or msg.get("created_at"),
                    }
                    continue

                if "title" in meta:
                    current["title"] = meta.get("title") or current.get("title", "")
                if "status" in meta and meta.get("status"):
                    current["status"] = meta.get("status")
                if "owner" in meta:
                    current["owner"] = meta.get("owner") or ""
                if "due_date" in meta:
                    current["due_date"] = meta.get("due_date") or ""
                if "notes" in meta:
                    current["notes"] = meta.get("notes") or ""
                current["updated_at"] = meta.get("updated_at") or meta.get("created_at") or msg.get("created_at")
        else:
            if self.local_path.exists():
                try:
                    items = json.loads(self.local_path.read_text(encoding="utf-8"))
                except Exception:
                    items = []
                for item in items:
                    task_id = item.get("id")
                    if not task_id:
                        continue
                    tasks[task_id] = item

        values = list(tasks.values())
        if not include_done:
            values = [item for item in values if item.get("status") != "done"]

        def _sort_key(item: Dict[str, str]):
            status = normalize_status(item.get("status", "todo"))
            order = STATUS_ORDER.get(status, 9)
            due = item.get("due_date") or "9999-12-31"
            return (order, due)

        values.sort(key=_sort_key)
        return values[:limit]

    def add_task(
        self,
        title: str,
        owner: str,
        due_date: Optional[date] = None,
        notes: str = "",
        created_by: str = "",
    ) -> Dict[str, str]:
        task = {
            "id": uuid.uuid4().hex[:12],
            "title": title.strip(),
            "status": "todo",
            "owner": owner.strip(),
            "due_date": due_date.isoformat() if due_date else "",
            "notes": notes.strip(),
            "created_by": created_by,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        if self.db:
            self._ensure_session()
            self.db.add_message(
                self.session_id,
                role="team_task",
                content=task["title"],
                metadata={
                    "task_id": task["id"],
                    "title": task["title"],
                    "status": task["status"],
                    "owner": task["owner"],
                    "due_date": task["due_date"],
                    "notes": task["notes"],
                    "created_by": created_by,
                    "created_at": task["created_at"],
                    "updated_at": task["updated_at"],
                },
            )
            return task

        items = []
        if self.local_path.exists():
            try:
                items = json.loads(self.local_path.read_text(encoding="utf-8"))
            except Exception:
                items = []
        items.append(task)
        try:
            self.local_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return task

    def update_task(
        self,
        task_id: str,
        title: Optional[str] = None,
        status: Optional[str] = None,
        owner: Optional[str] = None,
        due_date: Optional[date] = None,
        notes: Optional[str] = None,
        updated_by: str = "",
    ) -> bool:
        payload = {
            "task_id": task_id,
            "updated_by": updated_by,
            "updated_at": datetime.now().isoformat(),
        }
        if title is not None:
            payload["title"] = title.strip()
        if status is not None:
            payload["status"] = status
        if owner is not None:
            payload["owner"] = owner.strip()
        if due_date is not None:
            payload["due_date"] = due_date.isoformat() if isinstance(due_date, date) else str(due_date)
        if notes is not None:
            payload["notes"] = notes.strip()

        if self.db:
            self._ensure_session()
            content = payload.get("title") or f"update:{task_id}"
            self.db.add_message(
                self.session_id,
                role="team_task",
                content=content,
                metadata=payload,
            )
            return True

        if not self.local_path.exists():
            return False
        try:
            items = json.loads(self.local_path.read_text(encoding="utf-8"))
        except Exception:
            return False
        updated = False
        for item in items:
            if item.get("id") == task_id:
                if title is not None:
                    item["title"] = title.strip()
                if status is not None:
                    item["status"] = status
                if owner is not None:
                    item["owner"] = owner.strip()
                if due_date is not None:
                    item["due_date"] = due_date.isoformat() if isinstance(due_date, date) else str(due_date)
                if notes is not None:
                    item["notes"] = notes.strip()
                item["updated_at"] = datetime.now().isoformat()
                item["updated_by"] = updated_by
                updated = True
                break
        if updated:
            try:
                self.local_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
        return updated

    def update_task_status(self, task_id: str, status: str, updated_by: str = "") -> bool:
        status = status or "todo"
        return self.update_task(task_id=task_id, status=status, updated_by=updated_by)
