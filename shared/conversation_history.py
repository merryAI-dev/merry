"""
대화 기록 관리 모듈
- 팀별 대화 저장/불러오기
- 최근 대화 목록 조회
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import hashlib

from shared.logging_config import get_logger

logger = get_logger("conversation_history")

HISTORY_DIR = Path("conversation_history")
HISTORY_DIR.mkdir(exist_ok=True)


def _get_team_dir(team: str) -> Path:
    """팀별 디렉토리 경로 반환"""
    # 팀 이름을 파일시스템 안전한 이름으로 변환
    safe_team = team.replace(" ", "_").replace("/", "_")
    team_dir = HISTORY_DIR / safe_team
    team_dir.mkdir(exist_ok=True)
    return team_dir


def _get_conversation_id() -> str:
    """현재 시각 기반 대화 ID 생성"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 짧은 해시 추가 (충돌 방지)
    hash_suffix = hashlib.md5(timestamp.encode()).hexdigest()[:6]
    return f"{timestamp}_{hash_suffix}"


def save_conversation(
    team: str,
    messages: List[Dict],
    conversation_id: Optional[str] = None
) -> str:
    """
    대화 저장

    Args:
        team: 팀명
        messages: 메시지 리스트
        conversation_id: 기존 대화 ID (None이면 새로 생성)

    Returns:
        conversation_id
    """
    if not messages:
        logger.warning("저장할 메시지가 없습니다")
        return conversation_id or ""

    if not conversation_id:
        conversation_id = _get_conversation_id()

    team_dir = _get_team_dir(team)
    file_path = team_dir / f"{conversation_id}.json"

    data = {
        "conversation_id": conversation_id,
        "team": team,
        "created_at": datetime.now().isoformat(),
        "message_count": len(messages),
        "messages": messages,
    }

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"대화 저장 완료: {conversation_id} ({len(messages)}개 메시지)")
        return conversation_id
    except Exception as e:
        logger.error(f"대화 저장 실패: {e}")
        return ""


def load_conversation(
    team: str,
    conversation_id: str
) -> Tuple[List[Dict], Dict]:
    """
    대화 불러오기

    Args:
        team: 팀명
        conversation_id: 대화 ID

    Returns:
        (messages, metadata)
    """
    team_dir = _get_team_dir(team)
    file_path = team_dir / f"{conversation_id}.json"

    if not file_path.exists():
        logger.warning(f"대화 파일 없음: {conversation_id}")
        return [], {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        messages = data.get("messages", [])
        metadata = {
            "conversation_id": data.get("conversation_id"),
            "created_at": data.get("created_at"),
            "message_count": data.get("message_count"),
        }

        logger.info(f"대화 불러오기 완료: {conversation_id} ({len(messages)}개 메시지)")
        return messages, metadata

    except Exception as e:
        logger.error(f"대화 불러오기 실패: {e}")
        return [], {}


def list_conversations(
    team: str,
    limit: int = 10
) -> List[Dict]:
    """
    팀의 최근 대화 목록 조회

    Args:
        team: 팀명
        limit: 최대 개수

    Returns:
        대화 메타데이터 리스트 (최신순)
    """
    team_dir = _get_team_dir(team)

    conversations = []

    for file_path in sorted(team_dir.glob("*.json"), reverse=True)[:limit]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            conversations.append({
                "conversation_id": data.get("conversation_id"),
                "created_at": data.get("created_at"),
                "message_count": data.get("message_count", 0),
                "preview": _get_conversation_preview(data.get("messages", [])),
            })
        except Exception as e:
            logger.warning(f"대화 메타데이터 읽기 실패: {file_path.name} - {e}")
            continue

    return conversations


def _get_conversation_preview(messages: List[Dict]) -> str:
    """대화 미리보기 텍스트 생성 (첫 사용자 메시지)"""
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if content:
                # 최대 50자
                return content[:50] + ("..." if len(content) > 50 else "")
    return "새 대화"


def delete_conversation(team: str, conversation_id: str) -> bool:
    """
    대화 삭제

    Args:
        team: 팀명
        conversation_id: 대화 ID

    Returns:
        성공 여부
    """
    team_dir = _get_team_dir(team)
    file_path = team_dir / f"{conversation_id}.json"

    if not file_path.exists():
        logger.warning(f"삭제할 대화 없음: {conversation_id}")
        return False

    try:
        file_path.unlink()
        logger.info(f"대화 삭제 완료: {conversation_id}")
        return True
    except Exception as e:
        logger.error(f"대화 삭제 실패: {e}")
        return False
