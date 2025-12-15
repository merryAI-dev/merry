"""
Feedback Collection & Reinforcement Learning System
사용자 피드백 수집 및 강화학습 시스템
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

try:
    from .feedback_db import FeedbackDatabase
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


class FeedbackSystem:
    """
    사용자 피드백 수집 및 강화학습용 데이터 생성

    피드백 타입:
    - thumbs_up: 긍정적 피드백 (👍)
    - thumbs_down: 부정적 피드백 (👎)
    - text_feedback: 텍스트 피드백 (💬)
    - correction: 수정 요청 (사용자가 원하는 답변 제공)
    - rating: 1-5점 평점
    """

    def __init__(self, storage_dir: str = "feedback", session_id: str = None, user_nickname: str = None, company_name: str = None):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)

        # 피드백 데이터 파일
        self.feedback_file = self.storage_dir / "feedback_data.jsonl"

        # 강화학습용 데이터셋 파일
        self.rl_dataset_file = self.storage_dir / "rl_dataset.jsonl"

        # 데이터베이스 (통합 관리)
        self.db = FeedbackDatabase() if DB_AVAILABLE else None

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
        """
        피드백 추가

        Args:
            user_message: 사용자 질문
            assistant_response: 에이전트 응답
            feedback_type: 피드백 타입 (thumbs_up, thumbs_down, correction, rating)
            feedback_value: 피드백 값 (correction일 경우 올바른 답변, rating일 경우 점수)
            context: 추가 컨텍스트 (파일 경로, 도구 사용 등)

        Returns:
            피드백 ID
        """
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

        # JSONL 형식으로 저장 (한 줄에 하나의 JSON)
        with open(self.feedback_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(feedback_entry, ensure_ascii=False) + '\n')

        # 강화학습용 데이터셋 생성
        self._generate_rl_data(feedback_entry)

        # 데이터베이스에 저장 (통합 관리)
        if self.db:
            reward = self._calculate_reward(feedback_type, feedback_value)
            self.db.add_feedback(
                feedback_id=feedback_id,
                session_id=self.session_id or "unknown",
                user_nickname=self.user_nickname or "anonymous",
                company_name=self.company_name or "unknown",
                user_message=user_message,
                assistant_response=assistant_response,
                feedback_type=feedback_type,
                reward=reward,
                feedback_value=feedback_value,
                context=context,
                metadata=feedback_entry["metadata"]
            )

        return feedback_id

    def _generate_rl_data(self, feedback_entry: Dict[str, Any]):
        """
        강화학습용 데이터셋 생성 (OpenAI RLHF 형식)

        Format:
        {
            "prompt": "사용자 질문",
            "response": "에이전트 응답",
            "reward": 점수 (-1 ~ 1),
            "context": {...},
            "timestamp": "..."
        }
        """
        # 피드백 타입에 따라 보상 점수 계산
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

        # Correction이 있으면 preferred_response 추가
        if feedback_entry["feedback_type"] == "correction":
            rl_entry["preferred_response"] = feedback_entry["feedback_value"]

        with open(self.rl_dataset_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rl_entry, ensure_ascii=False) + '\n')

    def _calculate_reward(self, feedback_type: str, feedback_value: Any = None) -> float:
        """
        피드백 타입에 따른 보상 점수 계산

        Returns:
            -1.0 ~ 1.0 사이의 보상 점수
        """
        reward_map = {
            "thumbs_up": 1.0,
            "thumbs_down": -1.0,
            "text_feedback": 0.0,  # 중립 (내용 분석 필요)
            "rating": (feedback_value / 5.0 * 2) - 1 if feedback_value else 0.0,  # 1-5점 → -1~1
            "correction": -0.5  # 수정 요청은 부정적 피드백
        }

        return reward_map.get(feedback_type, 0.0)

    def get_feedback_stats(self) -> Dict[str, Any]:
        """
        피드백 통계 생성

        Returns:
            {
                "total_feedback": 전체 피드백 수,
                "positive_feedback": 긍정 피드백 수,
                "negative_feedback": 부정 피드백 수,
                "average_rating": 평균 평점,
                "feedback_by_type": {...}
            }
        """
        if not self.feedback_file.exists():
            return {
                "total_feedback": 0,
                "positive_feedback": 0,
                "negative_feedback": 0,
                "average_rating": 0.0,
                "feedback_by_type": {}
            }

        feedbacks = []
        with open(self.feedback_file, 'r', encoding='utf-8') as f:
            for line in f:
                feedbacks.append(json.loads(line))

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
            "satisfaction_rate": positive / total if total > 0 else 0.0
        }

    def export_rl_dataset(self, format: str = "jsonl") -> str:
        """
        강화학습용 데이터셋 내보내기

        Args:
            format: 출력 형식 ("jsonl", "csv", "parquet")

        Returns:
            출력 파일 경로
        """
        if not self.rl_dataset_file.exists():
            return None

        if format == "jsonl":
            return str(self.rl_dataset_file)

        # CSV 변환
        elif format == "csv":
            import csv

            output_file = self.storage_dir / "rl_dataset.csv"

            with open(self.rl_dataset_file, 'r', encoding='utf-8') as f_in:
                entries = [json.loads(line) for line in f]

            if not entries:
                return None

            with open(output_file, 'w', newline='', encoding='utf-8') as f_out:
                writer = csv.DictWriter(f_out, fieldnames=entries[0].keys())
                writer.writeheader()
                writer.writerows(entries)

            return str(output_file)

        return str(self.rl_dataset_file)

    def get_recent_feedback(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        최근 피드백 가져오기

        Args:
            limit: 가져올 피드백 수

        Returns:
            최근 피드백 리스트
        """
        if not self.feedback_file.exists():
            return []

        feedbacks = []
        with open(self.feedback_file, 'r', encoding='utf-8') as f:
            for line in f:
                feedbacks.append(json.loads(line))

        return feedbacks[-limit:]

    def analyze_feedback_patterns(self) -> Dict[str, Any]:
        """
        피드백 패턴 분석

        Returns:
            {
                "common_issues": [...],  # 자주 나타나는 문제
                "high_performing_patterns": [...],  # 높은 평가를 받는 패턴
                "improvement_areas": [...]  # 개선이 필요한 영역
            }
        """
        if not self.feedback_file.exists():
            return {
                "common_issues": [],
                "high_performing_patterns": [],
                "improvement_areas": []
            }

        feedbacks = []
        with open(self.feedback_file, 'r', encoding='utf-8') as f:
            for line in f:
                feedbacks.append(json.loads(line))

        # 부정적 피드백 패턴 분석
        negative_feedbacks = [f for f in feedbacks if f["feedback_type"] in ["thumbs_down", "correction"]]

        common_issues = []
        if negative_feedbacks:
            # 도구 사용 여부별 실패율
            tool_failures = sum(1 for f in negative_feedbacks if f["metadata"].get("has_tool_use"))
            common_issues.append({
                "issue": "도구 사용 시 오류",
                "count": tool_failures,
                "percentage": tool_failures / len(negative_feedbacks) * 100
            })

        # 긍정적 피드백 패턴 분석
        positive_feedbacks = [f for f in feedbacks if f["feedback_type"] == "thumbs_up"]

        high_performing_patterns = []
        if positive_feedbacks:
            # 응답 길이 분석
            avg_length = sum(f["metadata"]["message_length"] for f in positive_feedbacks) / len(positive_feedbacks)
            high_performing_patterns.append({
                "pattern": "최적 응답 길이",
                "value": f"{avg_length:.0f}자"
            })

        # 개선 영역
        improvement_areas = []
        stats = self.get_feedback_stats()

        if stats["satisfaction_rate"] < 0.7:
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
