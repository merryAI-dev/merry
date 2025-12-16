"""
Chat History & Memory Management
채팅 히스토리 아카이빙 및 메모리 관리
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


class ChatMemory:
    """채팅 히스토리 저장 및 관리"""

    def __init__(self, storage_dir: str = "chat_history", custom_session_id: str = None):
        """
        Args:
            storage_dir: 채팅 히스토리 저장 디렉토리
            custom_session_id: 사용자 정의 세션 ID (없으면 타임스탬프 사용)
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)

        # 현재 세션 ID (커스텀 또는 타임스탬프)
        if custom_session_id:
            self.session_id = custom_session_id
        else:
            self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.current_session_file = self.storage_dir / f"session_{self.session_id}.json"

        # 세션 메타데이터
        self.session_metadata = {
            "session_id": self.session_id,
            "start_time": datetime.now().isoformat(),
            "messages": [],
            "analyzed_files": [],
            "generated_files": [],
            "user_info": {}  # 사용자 정보 (별명, 기업명 등)
        }

    def set_user_info(self, nickname: str = None, company: str = None, google_email: str = None):
        """
        사용자 정보 설정 및 세션 ID 업데이트

        Args:
            nickname: 사내기업가 별명
            company: 분석 대상 기업명
            google_email: Google OAuth 인증 이메일
        """
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

            # 기존 파일 삭제
            if self.current_session_file.exists():
                self.current_session_file.unlink()

            # 새 세션 ID로 업데이트
            self.session_id = new_session_id
            self.session_metadata["session_id"] = new_session_id
            self.current_session_file = self.storage_dir / f"session_{new_session_id}.json"

            # 저장
            self._save_session()

    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None):
        """
        메시지 추가 및 저장

        Args:
            role: 역할 (user, assistant, tool)
            content: 메시지 내용
            metadata: 추가 메타데이터 (파일 경로, 도구 이름 등)
        """
        message = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
            "metadata": metadata or {}
        }

        self.session_metadata["messages"].append(message)
        self._save_session()

    def add_file_analysis(self, file_path: str):
        """분석된 파일 추가"""
        if file_path not in self.session_metadata["analyzed_files"]:
            self.session_metadata["analyzed_files"].append(file_path)
            self._save_session()

    def add_generated_file(self, file_path: str):
        """생성된 파일 추가"""
        if file_path not in self.session_metadata["generated_files"]:
            self.session_metadata["generated_files"].append(file_path)
            self._save_session()

    def _save_session(self):
        """현재 세션을 파일로 저장"""
        with open(self.current_session_file, 'w', encoding='utf-8') as f:
            json.dump(self.session_metadata, f, ensure_ascii=False, indent=2)

    def get_recent_sessions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        최근 세션 목록 가져오기

        Args:
            limit: 가져올 세션 수

        Returns:
            최근 세션 메타데이터 리스트
        """
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

    def load_session(self, session_id: str) -> Dict[str, Any]:
        """
        특정 세션 불러오기

        Args:
            session_id: 세션 ID

        Returns:
            세션 메타데이터
        """
        session_file = self.storage_dir / f"session_{session_id}.json"

        if not session_file.exists():
            return None

        with open(session_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_context_summary(self) -> str:
        """
        현재 세션의 컨텍스트 요약 생성

        Returns:
            컨텍스트 요약 문자열
        """
        summary = []

        # 분석된 파일
        if self.session_metadata["analyzed_files"]:
            summary.append("**분석된 파일:**")
            for file_path in self.session_metadata["analyzed_files"]:
                summary.append(f"- {Path(file_path).name}")

        # 생성된 파일
        if self.session_metadata["generated_files"]:
            summary.append("\n**생성된 파일:**")
            for file_path in self.session_metadata["generated_files"]:
                summary.append(f"- {file_path}")

        # 메시지 수
        message_count = len(self.session_metadata["messages"])
        summary.append(f"\n**총 메시지:** {message_count}개")

        return "\n".join(summary) if summary else "컨텍스트 없음"

    def export_session(self, session_id: str = None, output_path: str = None) -> str:
        """
        세션을 마크다운 파일로 내보내기

        Args:
            session_id: 세션 ID (None이면 현재 세션)
            output_path: 출력 파일 경로 (None이면 자동 생성)

        Returns:
            출력 파일 경로
        """
        if session_id:
            session_data = self.load_session(session_id)
        else:
            session_data = self.session_metadata

        if not session_data:
            return None

        # 마크다운 생성
        lines = [
            f"# 채팅 히스토리 - {session_data['session_id']}",
            f"",
            f"**시작 시간:** {session_data['start_time']}",
            f"**메시지 수:** {len(session_data['messages'])}",
            f"",
            f"---",
            f""
        ]

        # 분석된 파일
        if session_data.get("analyzed_files"):
            lines.append("## 분석된 파일")
            lines.append("")
            for file_path in session_data["analyzed_files"]:
                lines.append(f"- `{file_path}`")
            lines.append("")

        # 생성된 파일
        if session_data.get("generated_files"):
            lines.append("## 생성된 파일")
            lines.append("")
            for file_path in session_data["generated_files"]:
                lines.append(f"- `{file_path}`")
            lines.append("")

        # 대화 내용
        lines.append("## 대화 내용")
        lines.append("")

        for msg in session_data["messages"]:
            timestamp = msg["timestamp"]
            role = msg["role"]
            content = msg["content"]

            role_emoji = {
                "user": "👤",
                "assistant": "🤖",
                "tool": "🔧"
            }.get(role, "💬")

            lines.append(f"### {role_emoji} {role.upper()} ({timestamp})")
            lines.append("")
            lines.append(content)
            lines.append("")
            lines.append("---")
            lines.append("")

        # 파일 저장
        if not output_path:
            output_path = self.storage_dir / f"export_{session_data['session_id']}.md"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

        return str(output_path)
