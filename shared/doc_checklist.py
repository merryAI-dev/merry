"""
Team document checklist store backed by Supabase chat_messages or local JSON fallback.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional


DEFAULT_REQUIRED_DOCS = [
    {"name": "회사 소개서/IR Deck", "required": True},
    {"name": "사업계획서", "required": True},
    {"name": "재무제표 (최근 2~3년)", "required": True},
    {"name": "Cap Table", "required": True},
    {"name": "투자계약서/텀싯", "required": True},
    {"name": "주요 계약/특허/지식재산", "required": False},
    {"name": "주요 고객/매출 지표 자료", "required": True},
    {"name": "인력/조직도", "required": False},
    {"name": "시장/산업 리서치", "required": False},
    {"name": "ESG/임팩트 지표", "required": False},
]


class TeamDocChecklistStore:
    def __init__(self, team_id: str, local_dir: str = "temp/team_docs"):
        self.team_id = team_id or "team_1"
        self.session_id = f"docs_{self.team_id}"
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
            self.db.create_session(self.session_id, {"type": "doc_checklist"})
            self._session_created = True

    def list_docs(self) -> List[Dict[str, str]]:
        docs: Dict[str, Dict[str, str]] = {}

        if self.db:
            self._ensure_session()
            messages = self.db.get_messages(self.session_id)
            for msg in messages:
                if msg.get("role") != "team_doc":
                    continue
                meta = msg.get("metadata") or {}
                doc_id = meta.get("doc_id")
                if not doc_id:
                    continue
                current = docs.get(doc_id)
                if not current:
                    docs[doc_id] = {
                        "id": doc_id,
                        "name": meta.get("name") or msg.get("content", ""),
                        "required": bool(meta.get("required", False)),
                        "uploaded": bool(meta.get("uploaded", False)),
                        "owner": meta.get("owner", ""),
                        "notes": meta.get("notes", ""),
                        "updated_at": meta.get("updated_at") or meta.get("created_at") or msg.get("created_at"),
                    }
                    continue

                if "name" in meta:
                    current["name"] = meta.get("name") or current.get("name", "")
                if "required" in meta:
                    current["required"] = bool(meta.get("required", False))
                if "uploaded" in meta:
                    current["uploaded"] = bool(meta.get("uploaded", False))
                if "owner" in meta:
                    current["owner"] = meta.get("owner") or ""
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
                    doc_id = item.get("id")
                    if not doc_id:
                        continue
                    docs[doc_id] = item

        return sorted(docs.values(), key=lambda x: (not x.get("required"), x.get("name", "")))

    def add_doc(
        self,
        name: str,
        required: bool = True,
        owner: str = "",
        notes: str = "",
    ) -> Dict[str, str]:
        doc = {
            "id": uuid.uuid4().hex[:12],
            "name": name.strip(),
            "required": bool(required),
            "uploaded": False,
            "owner": owner.strip(),
            "notes": notes.strip(),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        if self.db:
            self._ensure_session()
            self.db.add_message(
                self.session_id,
                role="team_doc",
                content=doc["name"],
                metadata={
                    "doc_id": doc["id"],
                    "name": doc["name"],
                    "required": doc["required"],
                    "uploaded": doc["uploaded"],
                    "owner": doc["owner"],
                    "notes": doc["notes"],
                    "created_at": doc["created_at"],
                    "updated_at": doc["updated_at"],
                },
            )
            return doc

        items = []
        if self.local_path.exists():
            try:
                items = json.loads(self.local_path.read_text(encoding="utf-8"))
            except Exception:
                items = []
        items.append(doc)
        try:
            self.local_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return doc

    def update_doc(
        self,
        doc_id: str,
        name: Optional[str] = None,
        required: Optional[bool] = None,
        uploaded: Optional[bool] = None,
        owner: Optional[str] = None,
        notes: Optional[str] = None,
        updated_by: str = "",
    ) -> bool:
        payload: Dict[str, object] = {
            "doc_id": doc_id,
            "updated_by": updated_by,
            "updated_at": datetime.now().isoformat(),
        }
        if name is not None:
            payload["name"] = name.strip()
        if required is not None:
            payload["required"] = bool(required)
        if uploaded is not None:
            payload["uploaded"] = bool(uploaded)
        if owner is not None:
            payload["owner"] = owner.strip()
        if notes is not None:
            payload["notes"] = notes.strip()

        if self.db:
            self._ensure_session()
            content = payload.get("name") or f"doc:{doc_id}"
            self.db.add_message(
                self.session_id,
                role="team_doc",
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
            if item.get("id") == doc_id:
                if name is not None:
                    item["name"] = name.strip()
                if required is not None:
                    item["required"] = bool(required)
                if uploaded is not None:
                    item["uploaded"] = bool(uploaded)
                if owner is not None:
                    item["owner"] = owner.strip()
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

    def seed_defaults(self) -> int:
        existing = {doc.get("name") for doc in self.list_docs()}
        added = 0
        for item in DEFAULT_REQUIRED_DOCS:
            if item["name"] in existing:
                continue
            self.add_doc(name=item["name"], required=item.get("required", True))
            added += 1
        return added
