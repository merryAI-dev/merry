"""
Team comments store backed by Supabase chat_messages or local JSON fallback.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class TeamCommentStore:
    def __init__(self, team_id: str, local_dir: str = "temp/team_comments"):
        self.team_id = team_id or "team_1"
        self.session_id = f"comments_{self.team_id}"
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
            self.db.create_session(self.session_id, {"type": "team_comments"})
            self._session_created = True

    def list_comments(self, limit: int = 20) -> List[Dict[str, str]]:
        comments: List[Dict[str, str]] = []

        if self.db:
            self._ensure_session()
            messages = self.db.get_messages(self.session_id)
            for msg in messages:
                if msg.get("role") != "team_comment":
                    continue
                meta = msg.get("metadata") or {}
                comments.append({
                    "text": msg.get("content", ""),
                    "created_by": meta.get("created_by", ""),
                    "created_at": meta.get("created_at") or msg.get("created_at"),
                })
        else:
            if self.local_path.exists():
                try:
                    comments = json.loads(self.local_path.read_text(encoding="utf-8"))
                except Exception:
                    comments = []

        comments = sorted(comments, key=lambda x: x.get("created_at") or "", reverse=True)
        return comments[:limit]

    def add_comment(self, text: str, created_by: str) -> Dict[str, str]:
        comment = {
            "text": text.strip(),
            "created_by": created_by,
            "created_at": datetime.now().isoformat(),
        }

        if self.db:
            self._ensure_session()
            self.db.add_message(
                self.session_id,
                role="team_comment",
                content=comment["text"],
                metadata=comment,
            )
            return comment

        comments = []
        if self.local_path.exists():
            try:
                comments = json.loads(self.local_path.read_text(encoding="utf-8"))
            except Exception:
                comments = []
        comments.append(comment)
        try:
            self.local_path.write_text(json.dumps(comments, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return comment
