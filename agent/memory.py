"""
Chat History & Memory Management
채팅 히스토리 아카이빙 및 메모리 관리
- Supabase 영구 저장 지원
- 로컬 파일 Fallback
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Supabase 스토리지 (옵션)
try:
    from .supabase_storage import SupabaseStorage
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False


class ChatMemory:
    """채팅 히스토리 저장 및 관리 - user_id 기반 공유 + Supabase 영구 저장"""

    def __init__(self, storage_dir: str = "chat_history", custom_session_id: str = None, user_id: str = None):
        """
        Args:
            storage_dir: 채팅 히스토리 저장 디렉토리 (로컬 fallback)
            custom_session_id: 사용자 정의 세션 ID (없으면 타임스탬프 사용)
            user_id: 사용자 고유 ID (API 키 해시, 같은 ID끼리 세션 공유)
        """
        self.user_id = user_id or "anonymous"

        # Supabase 스토리지 초기화
        self.db: Optional[SupabaseStorage] = None
        if SUPABASE_AVAILABLE:
            self.db = SupabaseStorage(user_id=self.user_id)
            if not self.db.available:
                self.db = None

        # 로컬 파일 스토리지 (Fallback)
        self.storage_dir = Path(storage_dir) / self.user_id
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # 현재 세션 ID (커스텀 또는 타임스탬프)
        if custom_session_id:
            self.session_id = custom_session_id
        else:
            self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.current_session_file = self.storage_dir / f"session_{self.session_id}.json"

        # 세션 메타데이터
        self.session_metadata = {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "start_time": datetime.now().isoformat(),
            "messages": [],
            "analyzed_files": [],
            "generated_files": [],
            "user_info": {}
        }

        # Supabase에 세션 생성
        if self.db:
            self.db.create_session(self.session_id, self.session_metadata.get("user_info"))

    def set_user_info(self, nickname: str = None, company: str = None, google_email: str = None):
        """사용자 정보 설정 및 세션 ID 업데이트"""
        self.session_metadata["user_info"] = {
            "nickname": nickname,
            "company": company,
            "google_email": google_email,
            "authenticated_at": datetime.now().isoformat()
        }

        # 세션 ID를 의미있는 이름으로 업데이트
        if nickname and company:
            date_str = datetime.now().strftime("%Y%m%d_%H%M")
            new_session_id = f"{nickname}_{company}_{date_str}"

            # 로컬: 기존 파일 삭제
            if self.current_session_file.exists():
                self.current_session_file.unlink()

            # 새 세션 ID로 업데이트
            old_session_id = self.session_id
            self.session_id = new_session_id
            self.session_metadata["session_id"] = new_session_id
            self.current_session_file = self.storage_dir / f"session_{new_session_id}.json"

            # Supabase: 새 세션 생성
            if self.db:
                self.db.create_session(new_session_id, self.session_metadata["user_info"])

            # 저장
            self._save_session()

    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None):
        """메시지 추가 및 저장"""
        message = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
            "metadata": metadata or {}
        }

        self.session_metadata["messages"].append(message)

        # Supabase에 메시지 저장
        if self.db:
            self.db.add_message(self.session_id, role, content, metadata)

        # 로컬 저장
        self._save_session()

    def add_file_analysis(self, file_path: str):
        """분석된 파일 추가"""
        if file_path not in self.session_metadata["analyzed_files"]:
            self.session_metadata["analyzed_files"].append(file_path)

            # Supabase 업데이트
            if self.db:
                self.db.update_session(self.session_id, {
                    "analyzed_files": self.session_metadata["analyzed_files"]
                })

            self._save_session()

    def add_generated_file(self, file_path: str):
        """생성된 파일 추가"""
        if file_path not in self.session_metadata["generated_files"]:
            self.session_metadata["generated_files"].append(file_path)

            # Supabase 업데이트
            if self.db:
                self.db.update_session(self.session_id, {
                    "generated_files": self.session_metadata["generated_files"]
                })

            self._save_session()

    def _save_session(self):
        """현재 세션을 로컬 파일로 저장"""
        try:
            with open(self.current_session_file, 'w', encoding='utf-8') as f:
                json.dump(self.session_metadata, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # 로컬 저장 실패해도 Supabase에는 저장됨

    def get_recent_sessions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """최근 세션 목록 가져오기"""
        # Supabase 우선
        if self.db:
            sessions = self.db.get_recent_sessions(limit)
            if sessions:
                return sessions

        # 로컬 Fallback
        session_files = sorted(
            self.storage_dir.glob("session_*.json"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )

        sessions = []
        for session_file in session_files[:limit]:
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                    sessions.append({
                        "session_id": session_data.get("session_id"),
                        "start_time": session_data.get("start_time"),
                        "message_count": len(session_data.get("messages", [])),
                        "analyzed_files": session_data.get("analyzed_files", []),
                        "file_path": str(session_file)
                    })
            except Exception:
                continue

        return sessions

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """특정 세션 불러오기"""
        # Supabase 우선
        if self.db:
            session = self.db.get_session(session_id)
            if session:
                # 메시지도 로드
                messages = self.db.get_messages(session_id)
                session["messages"] = messages
                return session

        # 로컬 Fallback
        session_file = self.storage_dir / f"session_{session_id}.json"
        if not session_file.exists():
            return None

        with open(session_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_context_summary(self) -> str:
        """현재 세션의 컨텍스트 요약 생성"""
        summary = []

        if self.session_metadata["analyzed_files"]:
            summary.append("**분석된 파일:**")
            for file_path in self.session_metadata["analyzed_files"]:
                summary.append(f"- {Path(file_path).name}")

        if self.session_metadata["generated_files"]:
            summary.append("\n**생성된 파일:**")
            for file_path in self.session_metadata["generated_files"]:
                summary.append(f"- {file_path}")

        message_count = len(self.session_metadata["messages"])
        summary.append(f"\n**총 메시지:** {message_count}개")

        # 저장소 상태
        if self.db:
            summary.append("\n**저장소:** Supabase (영구)")
        else:
            summary.append("\n**저장소:** 로컬 (임시)")

        return "\n".join(summary) if summary else "컨텍스트 없음"

    def export_session(self, session_id: str = None, output_path: str = None) -> str:
        """세션을 마크다운 파일로 내보내기"""
        if session_id:
            session_data = self.load_session(session_id)
        else:
            session_data = self.session_metadata

        if not session_data:
            return None

        lines = [
            f"# 채팅 히스토리 - {session_data['session_id']}",
            f"",
            f"**시작 시간:** {session_data.get('start_time', 'N/A')}",
            f"**메시지 수:** {len(session_data.get('messages', []))}",
            f"",
            f"---",
            f""
        ]

        if session_data.get("analyzed_files"):
            lines.append("## 분석된 파일")
            lines.append("")
            for file_path in session_data["analyzed_files"]:
                lines.append(f"- `{file_path}`")
            lines.append("")

        if session_data.get("generated_files"):
            lines.append("## 생성된 파일")
            lines.append("")
            for file_path in session_data["generated_files"]:
                lines.append(f"- `{file_path}`")
            lines.append("")

        lines.append("## 대화 내용")
        lines.append("")

        for msg in session_data.get("messages", []):
            timestamp = msg.get("timestamp", "")
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            role_emoji = {"user": "U", "assistant": "A", "tool": "T"}.get(role, "?")
            lines.append(f"### [{role_emoji}] {role.upper()} ({timestamp})")
            lines.append("")
            lines.append(content)
            lines.append("")
            lines.append("---")
            lines.append("")

        if not output_path:
            output_path = self.storage_dir / f"export_{session_data['session_id']}.md"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

        return str(output_path)
