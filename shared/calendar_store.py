"""
Team calendar storage using existing chat_sessions/chat_messages tables.
Falls back to local JSON when Supabase is unavailable.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional


class TeamCalendarStore:
    def __init__(self, team_id: str, local_dir: str = "temp/team_calendar"):
        self.team_id = team_id or "team_1"
        self.session_id = f"calendar_{self.team_id}"
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
        if self.db:
            if not self._session_created:
                self.db.create_session(self.session_id, {"type": "calendar"})
                self._session_created = True

    def list_events(self, limit: int = 50) -> List[Dict[str, str]]:
        if self.db:
            self._ensure_session()
            messages = self.db.get_messages(self.session_id)
            events = []
            for msg in messages:
                meta = msg.get("metadata") or {}
                if msg.get("role") != "calendar":
                    continue
                events.append({
                    "id": meta.get("id") or msg.get("id"),
                    "date": meta.get("date"),
                    "title": msg.get("content", ""),
                    "notes": meta.get("notes", ""),
                    "created_by": meta.get("created_by", ""),
                    "created_at": meta.get("created_at", msg.get("created_at")),
                })
            return sorted(events, key=lambda x: x.get("date") or "")[:limit]

        if not self.local_path.exists():
            return []
        try:
            data = json.loads(self.local_path.read_text(encoding="utf-8"))
            return sorted(data, key=lambda x: x.get("date") or "")[:limit]
        except Exception:
            return []

    def add_event(self, event_date: date, title: str, notes: str, created_by: str) -> Dict[str, str]:
        event = {
            "id": uuid.uuid4().hex[:12],
            "date": event_date.isoformat(),
            "title": title.strip(),
            "notes": notes.strip(),
            "created_by": created_by,
            "created_at": datetime.now().isoformat(),
        }

        if self.db:
            self._ensure_session()
            self.db.add_message(
                self.session_id,
                role="calendar",
                content=event["title"],
                metadata=event,
            )
            return event

        events = []
        if self.local_path.exists():
            try:
                events = json.loads(self.local_path.read_text(encoding="utf-8"))
            except Exception:
                events = []
        events.append(event)
        try:
            self.local_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return event
