"""
Supabase Storage for Chat Sessions and Feedback
세션 및 피드백 데이터를 Supabase에 영구 저장
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

import streamlit as st


def get_supabase_client() -> Optional["Client"]:
    """
    Supabase 클라이언트 생성
    Streamlit secrets 또는 환경변수에서 설정 로드
    """
    if not SUPABASE_AVAILABLE:
        return None

    # Streamlit secrets에서 먼저 시도
    try:
        url = st.secrets.get("supabase", {}).get("url") or os.getenv("SUPABASE_URL")
        key = st.secrets.get("supabase", {}).get("key") or os.getenv("SUPABASE_KEY")
    except Exception:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        return None

    return create_client(url, key)


class SupabaseStorage:
    """
    Supabase 기반 영구 스토리지

    테이블 구조:
    - chat_sessions: 채팅 세션 메타데이터
    - chat_messages: 개별 메시지
    - feedback: 피드백 데이터
    """

    def __init__(self, user_id: str = "anonymous"):
        self.user_id = user_id
        self.client = get_supabase_client()
        self.available = self.client is not None

    # ========================================
    # Chat Sessions
    # ========================================

    def create_session(self, session_id: str, user_info: Dict[str, Any] = None) -> bool:
        """새 채팅 세션 생성"""
        if not self.available:
            return False

        try:
            data = {
                "session_id": session_id,
                "user_id": self.user_id,
                "user_info": json.dumps(user_info or {}),
                "analyzed_files": json.dumps([]),
                "generated_files": json.dumps([]),
                "created_at": datetime.now().isoformat()
            }
            self.client.table("chat_sessions").insert(data).execute()
            return True
        except Exception as e:
            print(f"Supabase create_session error: {e}")
            return False

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """세션 조회"""
        if not self.available:
            return None

        try:
            response = self.client.table("chat_sessions").select("*").eq(
                "session_id", session_id
            ).eq("user_id", self.user_id).execute()

            if response.data:
                session = response.data[0]
                # JSON 필드 파싱
                session["user_info"] = json.loads(session.get("user_info", "{}"))
                session["analyzed_files"] = json.loads(session.get("analyzed_files", "[]"))
                session["generated_files"] = json.loads(session.get("generated_files", "[]"))
                return session
            return None
        except Exception as e:
            print(f"Supabase get_session error: {e}")
            return None

    def get_recent_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """최근 세션 목록 조회"""
        if not self.available:
            return []

        try:
            response = self.client.table("chat_sessions").select("*").eq(
                "user_id", self.user_id
            ).order("created_at", desc=True).limit(limit).execute()

            sessions = []
            for session in response.data:
                session["user_info"] = json.loads(session.get("user_info", "{}"))
                session["analyzed_files"] = json.loads(session.get("analyzed_files", "[]"))
                session["generated_files"] = json.loads(session.get("generated_files", "[]"))
                sessions.append(session)
            return sessions
        except Exception as e:
            print(f"Supabase get_recent_sessions error: {e}")
            return []

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """세션 업데이트"""
        if not self.available:
            return False

        try:
            # JSON 필드 직렬화
            data = {}
            for key, value in updates.items():
                if key in ["user_info", "analyzed_files", "generated_files"]:
                    data[key] = json.dumps(value)
                else:
                    data[key] = value

            self.client.table("chat_sessions").update(data).eq(
                "session_id", session_id
            ).eq("user_id", self.user_id).execute()
            return True
        except Exception as e:
            print(f"Supabase update_session error: {e}")
            return False

    # ========================================
    # Chat Messages
    # ========================================

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """메시지 추가"""
        if not self.available:
            return False

        try:
            data = {
                "session_id": session_id,
                "user_id": self.user_id,
                "role": role,
                "content": content,
                "metadata": json.dumps(metadata or {}),
                "created_at": datetime.now().isoformat()
            }
            self.client.table("chat_messages").insert(data).execute()
            return True
        except Exception as e:
            print(f"Supabase add_message error: {e}")
            return False

    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """세션의 모든 메시지 조회"""
        if not self.available:
            return []

        try:
            response = self.client.table("chat_messages").select("*").eq(
                "session_id", session_id
            ).eq("user_id", self.user_id).order("created_at").execute()

            messages = []
            for msg in response.data:
                msg["metadata"] = json.loads(msg.get("metadata", "{}"))
                messages.append(msg)
            return messages
        except Exception as e:
            print(f"Supabase get_messages error: {e}")
            return []

    # ========================================
    # Feedback
    # ========================================

    def add_feedback(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
        feedback_type: str,
        feedback_value: Any = None,
        context: Dict[str, Any] = None
    ) -> bool:
        """피드백 추가"""
        if not self.available:
            return False

        try:
            # 보상 계산
            reward = self._calculate_reward(feedback_type, feedback_value)

            data = {
                "session_id": session_id,
                "user_id": self.user_id,
                "user_message": user_message,
                "assistant_response": assistant_response,
                "feedback_type": feedback_type,
                "feedback_value": json.dumps(feedback_value) if feedback_value else None,
                "reward": reward,
                "context": json.dumps(context or {}),
                "created_at": datetime.now().isoformat()
            }
            self.client.table("feedback").insert(data).execute()
            return True
        except Exception as e:
            print(f"Supabase add_feedback error: {e}")
            return False

    def get_feedback_stats(self) -> Dict[str, Any]:
        """피드백 통계"""
        if not self.available:
            return {"total": 0, "positive": 0, "negative": 0, "satisfaction_rate": 0.0}

        try:
            response = self.client.table("feedback").select("*").eq(
                "user_id", self.user_id
            ).execute()

            feedbacks = response.data
            total = len(feedbacks)
            positive = sum(1 for f in feedbacks if f["feedback_type"] == "thumbs_up")
            negative = sum(1 for f in feedbacks if f["feedback_type"] == "thumbs_down")

            return {
                "total": total,
                "positive": positive,
                "negative": negative,
                "satisfaction_rate": positive / total if total > 0 else 0.0
            }
        except Exception as e:
            print(f"Supabase get_feedback_stats error: {e}")
            return {"total": 0, "positive": 0, "negative": 0, "satisfaction_rate": 0.0}

    def get_recent_feedback(self, limit: int = 10) -> List[Dict[str, Any]]:
        """최근 피드백 조회"""
        if not self.available:
            return []

        try:
            response = self.client.table("feedback").select("*").eq(
                "user_id", self.user_id
            ).order("created_at", desc=True).limit(limit).execute()

            feedbacks = []
            for fb in response.data:
                if fb.get("feedback_value"):
                    fb["feedback_value"] = json.loads(fb["feedback_value"])
                fb["context"] = json.loads(fb.get("context", "{}"))
                feedbacks.append(fb)
            return feedbacks
        except Exception as e:
            print(f"Supabase get_recent_feedback error: {e}")
            return []

    def _calculate_reward(self, feedback_type: str, feedback_value: Any = None) -> float:
        """피드백 타입에 따른 보상 점수 계산"""
        reward_map = {
            "thumbs_up": 1.0,
            "thumbs_down": -1.0,
            "text_feedback": 0.0,
            "correction": -0.5
        }

        if feedback_type == "rating" and feedback_value:
            try:
                return (float(feedback_value) / 5.0 * 2) - 1  # 1-5 -> -1~1
            except (ValueError, TypeError):
                return 0.0

        return reward_map.get(feedback_type, 0.0)
