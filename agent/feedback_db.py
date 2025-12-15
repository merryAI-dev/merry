"""
Feedback Database & Analytics
피드백 데이터베이스 및 분석 시스템
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd


class FeedbackDatabase:
    """
    SQLite 기반 피드백 데이터베이스

    전체 조직의 피드백을 통합 관리하고 분석
    """

    def __init__(self, db_path: str = "feedback/feedback.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)

        # 데이터베이스 연결 및 테이블 생성
        self._init_database()

    def _init_database(self):
        """데이터베이스 및 테이블 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 피드백 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedbacks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feedback_id TEXT UNIQUE NOT NULL,
                timestamp TEXT NOT NULL,
                session_id TEXT,
                user_nickname TEXT,
                company_name TEXT,
                user_message TEXT NOT NULL,
                assistant_response TEXT NOT NULL,
                feedback_type TEXT NOT NULL,
                feedback_value TEXT,
                reward REAL,
                context TEXT,
                metadata TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 세션 통계 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_stats (
                session_id TEXT PRIMARY KEY,
                user_nickname TEXT,
                company_name TEXT,
                start_time TEXT,
                end_time TEXT,
                total_messages INTEGER DEFAULT 0,
                positive_feedback INTEGER DEFAULT 0,
                negative_feedback INTEGER DEFAULT 0,
                satisfaction_rate REAL DEFAULT 0.0,
                analyzed_files TEXT,
                generated_files TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 강화학습 데이터셋 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rl_dataset (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feedback_id TEXT NOT NULL,
                prompt TEXT NOT NULL,
                response TEXT NOT NULL,
                reward REAL NOT NULL,
                preferred_response TEXT,
                tools_used TEXT,
                success BOOLEAN,
                response_length INTEGER,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (feedback_id) REFERENCES feedbacks(feedback_id)
            )
        """)

        # 인덱스 생성
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON feedbacks(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedbacks(feedback_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON feedbacks(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reward ON rl_dataset(reward)")

        conn.commit()
        conn.close()

    def add_feedback(
        self,
        feedback_id: str,
        session_id: str,
        user_nickname: str,
        company_name: str,
        user_message: str,
        assistant_response: str,
        feedback_type: str,
        reward: float,
        feedback_value: Any = None,
        context: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None
    ):
        """피드백 추가"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO feedbacks (
                feedback_id, timestamp, session_id, user_nickname, company_name,
                user_message, assistant_response, feedback_type, feedback_value,
                reward, context, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            feedback_id,
            datetime.now().isoformat(),
            session_id,
            user_nickname,
            company_name,
            user_message,
            assistant_response,
            feedback_type,
            json.dumps(feedback_value) if feedback_value else None,
            reward,
            json.dumps(context or {}),
            json.dumps(metadata or {})
        ))

        # RL 데이터셋 추가
        tools_used = context.get("tools_used", []) if context else []
        cursor.execute("""
            INSERT INTO rl_dataset (
                feedback_id, prompt, response, reward, tools_used,
                response_length, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            feedback_id,
            user_message,
            assistant_response,
            reward,
            json.dumps(tools_used),
            len(assistant_response),
            datetime.now().isoformat()
        ))

        conn.commit()
        conn.close()

    def get_all_feedbacks(self, limit: int = None) -> List[Dict[str, Any]]:
        """모든 피드백 조회"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM feedbacks ORDER BY timestamp DESC"
        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]

        feedbacks = []
        for row in cursor.fetchall():
            feedback = dict(zip(columns, row))
            # JSON 필드 파싱
            for field in ['context', 'metadata', 'feedback_value']:
                if feedback.get(field):
                    try:
                        feedback[field] = json.loads(feedback[field])
                    except:
                        pass
            feedbacks.append(feedback)

        conn.close()
        return feedbacks

    def get_global_stats(self) -> Dict[str, Any]:
        """전체 통계"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 전체 피드백 수
        cursor.execute("SELECT COUNT(*) FROM feedbacks")
        total = cursor.fetchone()[0]

        # 긍정/부정 피드백
        cursor.execute("SELECT COUNT(*) FROM feedbacks WHERE feedback_type = 'thumbs_up'")
        positive = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM feedbacks WHERE feedback_type = 'thumbs_down'")
        negative = cursor.fetchone()[0]

        # 평균 보상
        cursor.execute("SELECT AVG(reward) FROM feedbacks")
        avg_reward = cursor.fetchone()[0] or 0.0

        # 세션 수
        cursor.execute("SELECT COUNT(DISTINCT session_id) FROM feedbacks")
        total_sessions = cursor.fetchone()[0]

        # 사용자 수
        cursor.execute("SELECT COUNT(DISTINCT user_nickname) FROM feedbacks WHERE user_nickname IS NOT NULL")
        total_users = cursor.fetchone()[0]

        conn.close()

        return {
            "total_feedback": total,
            "positive_feedback": positive,
            "negative_feedback": negative,
            "satisfaction_rate": positive / total if total > 0 else 0.0,
            "average_reward": avg_reward,
            "total_sessions": total_sessions,
            "total_users": total_users
        }

    def get_user_stats(self, user_nickname: str) -> Dict[str, Any]:
        """특정 사용자 통계"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN feedback_type = 'thumbs_up' THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN feedback_type = 'thumbs_down' THEN 1 ELSE 0 END) as negative,
                AVG(reward) as avg_reward
            FROM feedbacks
            WHERE user_nickname = ?
        """, (user_nickname,))

        row = cursor.fetchone()
        conn.close()

        return {
            "total_feedback": row[0],
            "positive_feedback": row[1],
            "negative_feedback": row[2],
            "average_reward": row[3] or 0.0,
            "satisfaction_rate": row[1] / row[0] if row[0] > 0 else 0.0
        }

    def get_low_performing_patterns(self, min_occurrences: int = 3) -> List[Dict[str, Any]]:
        """낮은 평가를 받은 패턴 분석 (개선 대상)"""
        conn = sqlite3.connect(self.db_path)

        # 부정적 피드백이 많은 프롬프트 패턴
        query = """
            SELECT
                user_message,
                COUNT(*) as occurrences,
                AVG(reward) as avg_reward,
                GROUP_CONCAT(assistant_response, ' | ') as responses
            FROM feedbacks
            WHERE reward < 0
            GROUP BY user_message
            HAVING COUNT(*) >= ?
            ORDER BY avg_reward ASC, occurrences DESC
            LIMIT 10
        """

        df = pd.read_sql_query(query, conn, params=(min_occurrences,))
        conn.close()

        return df.to_dict('records')

    def get_high_performing_patterns(self, min_occurrences: int = 3) -> List[Dict[str, Any]]:
        """높은 평가를 받은 패턴 분석 (학습 대상)"""
        conn = sqlite3.connect(self.db_path)

        query = """
            SELECT
                user_message,
                COUNT(*) as occurrences,
                AVG(reward) as avg_reward,
                AVG(LENGTH(assistant_response)) as avg_response_length,
                GROUP_CONCAT(DISTINCT context) as contexts
            FROM feedbacks
            WHERE reward > 0
            GROUP BY user_message
            HAVING COUNT(*) >= ?
            ORDER BY avg_reward DESC, occurrences DESC
            LIMIT 10
        """

        df = pd.read_sql_query(query, conn, params=(min_occurrences,))
        conn.close()

        return df.to_dict('records')

    def export_rl_training_data(self, min_reward: float = 0.0) -> str:
        """강화학습 훈련 데이터 내보내기 (JSONL)"""
        conn = sqlite3.connect(self.db_path)

        query = """
            SELECT
                prompt,
                response,
                reward,
                preferred_response,
                tools_used,
                timestamp
            FROM rl_dataset
            WHERE reward >= ?
            ORDER BY reward DESC
        """

        df = pd.read_sql_query(query, conn, params=(min_reward,))
        conn.close()

        # JSONL 내보내기
        output_path = self.db_path.parent / "rl_training_data.jsonl"

        with open(output_path, 'w', encoding='utf-8') as f:
            for _, row in df.iterrows():
                entry = {
                    "prompt": row['prompt'],
                    "response": row['response'],
                    "reward": row['reward'],
                    "timestamp": row['timestamp']
                }

                if row['preferred_response']:
                    entry['preferred_response'] = row['preferred_response']

                if row['tools_used']:
                    try:
                        entry['tools_used'] = json.loads(row['tools_used'])
                    except:
                        pass

                f.write(json.dumps(entry, ensure_ascii=False) + '\n')

        return str(output_path)

    def generate_prompt_improvement_report(self) -> str:
        """프롬프트 개선 리포트 생성"""
        conn = sqlite3.connect(self.db_path)

        report_lines = []
        report_lines.append("# 프롬프트 개선 리포트")
        report_lines.append(f"\n생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # 전체 통계
        stats = self.get_global_stats()
        report_lines.append("## 전체 통계")
        report_lines.append(f"- 총 피드백: {stats['total_feedback']}개")
        report_lines.append(f"- 만족도: {stats['satisfaction_rate']*100:.1f}%")
        report_lines.append(f"- 평균 보상: {stats['average_reward']:.2f}")
        report_lines.append(f"- 총 세션: {stats['total_sessions']}개")
        report_lines.append(f"- 총 사용자: {stats['total_users']}명\n")

        # 개선 필요 패턴
        report_lines.append("## 개선이 필요한 패턴 (부정적 피드백)")
        low_patterns = self.get_low_performing_patterns(min_occurrences=2)

        if low_patterns:
            for i, pattern in enumerate(low_patterns[:5], 1):
                report_lines.append(f"\n### {i}. {pattern['user_message'][:50]}...")
                report_lines.append(f"- 발생 횟수: {pattern['occurrences']}회")
                report_lines.append(f"- 평균 보상: {pattern['avg_reward']:.2f}")
        else:
            report_lines.append("- 개선이 필요한 패턴 없음")

        # 우수 패턴
        report_lines.append("\n## 우수 패턴 (긍정적 피드백)")
        high_patterns = self.get_high_performing_patterns(min_occurrences=2)

        if high_patterns:
            for i, pattern in enumerate(high_patterns[:5], 1):
                report_lines.append(f"\n### {i}. {pattern['user_message'][:50]}...")
                report_lines.append(f"- 발생 횟수: {pattern['occurrences']}회")
                report_lines.append(f"- 평균 보상: {pattern['avg_reward']:.2f}")
                report_lines.append(f"- 평균 응답 길이: {pattern['avg_response_length']:.0f}자")
        else:
            report_lines.append("- 우수 패턴 없음")

        conn.close()

        # 리포트 저장
        report_path = self.db_path.parent / f"improvement_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_content = "\n".join(report_lines)

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)

        return str(report_path)


class RLTrainingPipeline:
    """
    강화학습 훈련 파이프라인

    피드백 데이터를 활용하여:
    1. 프롬프트 개선
    2. 응답 품질 향상
    3. 도구 사용 최적화
    """

    def __init__(self, db: FeedbackDatabase):
        self.db = db

    def analyze_tool_usage_patterns(self) -> Dict[str, Any]:
        """도구 사용 패턴 분석"""
        conn = sqlite3.connect(self.db.db_path)

        # 도구 사용과 피드백 상관관계
        query = """
            SELECT
                context,
                AVG(reward) as avg_reward,
                COUNT(*) as occurrences
            FROM feedbacks
            WHERE context IS NOT NULL AND context != '{}'
            GROUP BY context
            ORDER BY avg_reward DESC
        """

        cursor = conn.cursor()
        cursor.execute(query)

        tool_patterns = []
        for row in cursor.fetchall():
            try:
                context = json.loads(row[0])
                if context.get('tools_used'):
                    tool_patterns.append({
                        'tools': context['tools_used'],
                        'avg_reward': row[1],
                        'occurrences': row[2]
                    })
            except:
                continue

        conn.close()

        return {
            "tool_patterns": tool_patterns,
            "recommendation": self._generate_tool_recommendations(tool_patterns)
        }

    def _generate_tool_recommendations(self, patterns: List[Dict]) -> str:
        """도구 사용 권장사항 생성"""
        if not patterns:
            return "데이터 부족"

        # 가장 높은 보상을 받은 도구 조합
        best_pattern = max(patterns, key=lambda x: x['avg_reward'])

        return f"권장 도구 조합: {', '.join(best_pattern['tools'])} (평균 보상: {best_pattern['avg_reward']:.2f})"

    def generate_system_prompt_improvements(self) -> str:
        """시스템 프롬프트 개선 제안"""
        low_patterns = self.db.get_low_performing_patterns(min_occurrences=2)
        high_patterns = self.db.get_high_performing_patterns(min_occurrences=2)

        improvements = []
        improvements.append("# 시스템 프롬프트 개선 제안\n")

        # 부정적 패턴 기반 개선
        if low_patterns:
            improvements.append("## 개선 필요 영역")
            for pattern in low_patterns[:3]:
                improvements.append(f"\n### 문제: {pattern['user_message'][:50]}...")
                improvements.append("제안: 이런 유형의 질문에 대해 더 명확한 지침 추가")

        # 긍정적 패턴 기반 강화
        if high_patterns:
            improvements.append("\n## 강화 영역")
            for pattern in high_patterns[:3]:
                improvements.append(f"\n### 우수 사례: {pattern['user_message'][:50]}...")
                improvements.append("제안: 이런 응답 패턴을 다른 영역에도 적용")

        return "\n".join(improvements)
