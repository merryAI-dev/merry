"""
Feedback Collection & Reinforcement Learning System
사용자 피드백 수집 및 강화학습 시스템
- Supabase 영구 저장 지원
- 로컬 파일 Fallback
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from shared.logging_config import get_logger

logger = get_logger("feedback")

# Supabase 스토리지 (옵션)
try:
    from .supabase_storage import SupabaseStorage
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logger.info("Supabase storage not available for feedback")


class FeedbackSystem:
    """
    사용자 피드백 수집 및 강화학습용 데이터 생성
    - Supabase 영구 저장 지원
    - 로컬 파일 Fallback

    피드백 타입:
    - thumbs_up: 긍정적 피드백
    - thumbs_down: 부정적 피드백
    - text_feedback: 텍스트 피드백
    - correction: 수정 요청 (사용자가 원하는 답변 제공)
    - rating: 1-5점 평점
    """

    def __init__(self, storage_dir: str = "feedback", session_id: str = None, user_nickname: str = None, company_name: str = None, user_id: str = None):
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

        # 피드백 데이터 파일
        self.feedback_file = self.storage_dir / "feedback_data.jsonl"

        # 강화학습용 데이터셋 파일
        self.rl_dataset_file = self.storage_dir / "rl_dataset.jsonl"

        # 세션 정보
        self.session_id = session_id
        self.user_nickname = user_nickname
        self.company_name = company_name

    def add_feedback(
        self,
        user_message: str,
        assistant_response: str,
        feedback_type: str,
        feedback_value: Any = None,
        context: Dict[str, Any] = None
    ) -> str:
        """피드백 추가"""
        feedback_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        feedback_entry = {
            "id": feedback_id,
            "timestamp": datetime.now().isoformat(),
            "user_message": user_message,
            "assistant_response": assistant_response,
            "feedback_type": feedback_type,
            "feedback_value": feedback_value,
            "context": context or {},
            "metadata": {
                "message_length": len(assistant_response),
                "has_tool_use": bool(context and context.get("tools_used"))
            }
        }

        # Supabase에 저장
        if self.db:
            self.db.add_feedback(
                session_id=self.session_id or "unknown",
                user_message=user_message,
                assistant_response=assistant_response,
                feedback_type=feedback_type,
                feedback_value=feedback_value,
                context=context
            )

        # 로컬 JSONL 저장 (Fallback + 백업)
        try:
            with open(self.feedback_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(feedback_entry, ensure_ascii=False) + '\n')
        except PermissionError as e:
            logger.error(f"Permission denied saving feedback to {self.feedback_file}: {e}")
        except OSError as e:
            logger.error(f"OS error saving feedback to {self.feedback_file}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving feedback: {e}", exc_info=True)

        # 강화학습용 데이터셋 생성
        self._generate_rl_data(feedback_entry)

        return feedback_id

    def _generate_rl_data(self, feedback_entry: Dict[str, Any]):
        """강화학습용 데이터셋 생성 (OpenAI RLHF 형식)"""
        reward = self._calculate_reward(
            feedback_entry["feedback_type"],
            feedback_entry.get("feedback_value")
        )

        rl_entry = {
            "prompt": feedback_entry["user_message"],
            "response": feedback_entry["assistant_response"],
            "reward": reward,
            "context": feedback_entry["context"],
            "feedback_id": feedback_entry["id"],
            "timestamp": feedback_entry["timestamp"],
            "metadata": feedback_entry["metadata"]
        }

        if feedback_entry["feedback_type"] == "correction":
            rl_entry["preferred_response"] = feedback_entry["feedback_value"]

        try:
            with open(self.rl_dataset_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(rl_entry, ensure_ascii=False) + '\n')
        except PermissionError as e:
            logger.error(f"Permission denied saving RL dataset to {self.rl_dataset_file}: {e}")
        except OSError as e:
            logger.error(f"OS error saving RL dataset to {self.rl_dataset_file}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving RL dataset: {e}", exc_info=True)

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
                return (float(feedback_value) / 5.0 * 2) - 1
            except (ValueError, TypeError):
                return 0.0

        return reward_map.get(feedback_type, 0.0)

    def get_feedback_stats(self) -> Dict[str, Any]:
        """피드백 통계 생성"""
        # Supabase 우선
        if self.db:
            stats = self.db.get_feedback_stats()
            if stats.get("total", 0) > 0:
                return {
                    "total_feedback": stats["total"],
                    "positive_feedback": stats["positive"],
                    "negative_feedback": stats["negative"],
                    "satisfaction_rate": stats["satisfaction_rate"],
                    "average_rating": 0.0,
                    "feedback_by_type": {},
                    "storage": "supabase"
                }

        # 로컬 Fallback
        if not self.feedback_file.exists():
            return {
                "total_feedback": 0,
                "positive_feedback": 0,
                "negative_feedback": 0,
                "average_rating": 0.0,
                "feedback_by_type": {},
                "satisfaction_rate": 0.0,
                "storage": "local"
            }

        feedbacks = []
        with open(self.feedback_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    feedbacks.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        total = len(feedbacks)
        positive = sum(1 for f in feedbacks if f["feedback_type"] == "thumbs_up")
        negative = sum(1 for f in feedbacks if f["feedback_type"] == "thumbs_down")

        ratings = [f["feedback_value"] for f in feedbacks if f["feedback_type"] == "rating" and f["feedback_value"]]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

        feedback_by_type = {}
        for f in feedbacks:
            ftype = f["feedback_type"]
            feedback_by_type[ftype] = feedback_by_type.get(ftype, 0) + 1

        return {
            "total_feedback": total,
            "positive_feedback": positive,
            "negative_feedback": negative,
            "average_rating": avg_rating,
            "feedback_by_type": feedback_by_type,
            "satisfaction_rate": positive / total if total > 0 else 0.0,
            "storage": "local"
        }

    def get_recent_feedback(self, limit: int = 10) -> List[Dict[str, Any]]:
        """최근 피드백 가져오기"""
        # Supabase 우선
        if self.db:
            feedbacks = self.db.get_recent_feedback(limit)
            if feedbacks:
                return feedbacks

        # 로컬 Fallback
        if not self.feedback_file.exists():
            return []

        feedbacks = []
        with open(self.feedback_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    feedbacks.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        return feedbacks[-limit:]

    def export_rl_dataset(self, format: str = "jsonl") -> Optional[str]:
        """강화학습용 데이터셋 내보내기"""
        if not self.rl_dataset_file.exists():
            return None

        if format == "jsonl":
            return str(self.rl_dataset_file)

        if format == "csv":
            import csv

            output_file = self.storage_dir / "rl_dataset.csv"

            entries = []
            with open(self.rl_dataset_file, 'r', encoding='utf-8') as f_in:
                for line in f_in:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

            if not entries:
                return None

            with open(output_file, 'w', newline='', encoding='utf-8') as f_out:
                writer = csv.DictWriter(f_out, fieldnames=entries[0].keys())
                writer.writeheader()
                writer.writerows(entries)

            return str(output_file)

        return str(self.rl_dataset_file)

    def analyze_feedback_patterns(self) -> Dict[str, Any]:
        """피드백 패턴 분석"""
        feedbacks = self.get_recent_feedback(limit=100)

        if not feedbacks:
            return {
                "common_issues": [],
                "high_performing_patterns": [],
                "improvement_areas": []
            }

        negative_feedbacks = [f for f in feedbacks if f.get("feedback_type") in ["thumbs_down", "correction"]]
        positive_feedbacks = [f for f in feedbacks if f.get("feedback_type") == "thumbs_up"]

        common_issues = []
        if negative_feedbacks:
            tool_failures = sum(1 for f in negative_feedbacks if f.get("metadata", {}).get("has_tool_use"))
            if tool_failures > 0:
                common_issues.append({
                    "issue": "도구 사용 시 오류",
                    "count": tool_failures,
                    "percentage": tool_failures / len(negative_feedbacks) * 100
                })

        high_performing_patterns = []
        if positive_feedbacks:
            lengths = [f.get("metadata", {}).get("message_length", 0) for f in positive_feedbacks]
            if lengths:
                avg_length = sum(lengths) / len(lengths)
                high_performing_patterns.append({
                    "pattern": "최적 응답 길이",
                    "value": f"{avg_length:.0f}자"
                })

        improvement_areas = []
        stats = self.get_feedback_stats()
        if stats.get("satisfaction_rate", 0) < 0.7:
            improvement_areas.append({
                "area": "전체 만족도",
                "current": f"{stats['satisfaction_rate']*100:.1f}%",
                "target": "70% 이상"
            })

        return {
            "common_issues": common_issues,
            "high_performing_patterns": high_performing_patterns,
            "improvement_areas": improvement_areas
        }
