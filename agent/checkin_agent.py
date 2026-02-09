"""
체크인 피드백 분석 에이전트

사용자 피드백을 분석하여 개선점을 도출하고 브리핑을 생성합니다.
Claude Agent SDK / Anthropic SDK를 사용합니다.
"""

import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트의 .env 파일 로드
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from anthropic import Anthropic

from shared.logging_config import get_logger

logger = get_logger("checkin_agent")


# 시스템 프롬프트
CHECKIN_SYSTEM_PROMPT = """당신은 **VC 투자 분석 도구의 체크인 에이전트**입니다.

## 역할
사용자의 피드백을 분석하여 서비스 개선점을 도출하고, 1:1 브리핑을 지원합니다.

## 현재 피드백 데이터
{feedback_data}

## 분석 원칙

### 1. 패턴 인식
- 반복되는 피드백 유형 식별
- 긍정적 피드백의 공통점 분석
- 부정적 피드백의 근본 원인 파악

### 2. 개선점 도출
- 구체적이고 실행 가능한 개선안 제시
- 우선순위 부여 (긴급/중요도)
- 예상 효과 설명

### 3. 브리핑 스타일
- 간결하고 명확한 언어 사용
- 데이터 기반 인사이트 제공
- 실행 가능한 액션 아이템 제시

## 출력 형식

### 피드백 요약
- 전체 피드백 수: X개
- 긍정: X개 (XX%)
- 개선 필요: X개 (XX%)

### 주요 인사이트
1. **[인사이트 제목]**: 설명...
2. ...

### 개선 제안
| 우선순위 | 항목 | 근거 | 예상 효과 |
|---------|------|------|----------|
| 높음 | ... | ... | ... |

### 다음 단계
- [ ] 액션 아이템 1
- [ ] 액션 아이템 2
"""


class CheckinAgent:
    """체크인 피드백 분석 에이전트"""

    def __init__(self, api_key: str = None, user_id: str = "anonymous"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.user_id = user_id
        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-5-20250929"

    def analyze_feedbacks(
        self,
        feedbacks: List[Dict[str, Any]],
        stats: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        피드백 데이터를 분석하여 인사이트와 개선점 도출

        Args:
            feedbacks: 피드백 리스트
            stats: 피드백 통계 (total, positive, negative, satisfaction_rate)

        Returns:
            분석 결과
        """
        if not feedbacks:
            return {
                "success": False,
                "error": "분석할 피드백이 없습니다."
            }

        # 피드백 데이터 포맷팅
        feedback_text = self._format_feedbacks(feedbacks, stats)

        # 시스템 프롬프트 생성
        system_prompt = CHECKIN_SYSTEM_PROMPT.format(feedback_data=feedback_text)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": "위 피드백 데이터를 분석하여 주요 인사이트와 개선점을 도출해주세요. 브리핑 형식으로 정리해주세요."
                    }
                ]
            )

            analysis = response.content[0].text

            return {
                "success": True,
                "analysis": analysis,
                "stats": stats,
                "feedback_count": len(feedbacks)
            }

        except Exception as e:
            logger.error(f"피드백 분석 실패: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def generate_briefing(
        self,
        feedbacks: List[Dict[str, Any]],
        stats: Dict[str, Any] = None,
        focus_area: str = None
    ) -> str:
        """
        1:1 브리핑용 요약 생성

        Args:
            feedbacks: 피드백 리스트
            stats: 피드백 통계
            focus_area: 집중 분석 영역 (선택)

        Returns:
            브리핑 텍스트
        """
        result = self.analyze_feedbacks(feedbacks, stats)

        if not result.get("success"):
            return f"브리핑 생성 실패: {result.get('error', '알 수 없는 오류')}"

        return result.get("analysis", "")

    def chat(self, message: str, feedbacks: List[Dict[str, Any]] = None) -> str:
        """
        대화형 피드백 분석

        Args:
            message: 사용자 메시지
            feedbacks: 피드백 데이터 (선택)

        Returns:
            에이전트 응답
        """
        feedback_text = ""
        if feedbacks:
            feedback_text = self._format_feedbacks(feedbacks)

        system_prompt = CHECKIN_SYSTEM_PROMPT.format(
            feedback_data=feedback_text if feedback_text else "피드백 데이터가 제공되지 않았습니다."
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": message}
                ]
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"체크인 에이전트 대화 실패: {e}", exc_info=True)
            return f"오류가 발생했습니다: {str(e)}"

    def _format_feedbacks(
        self,
        feedbacks: List[Dict[str, Any]],
        stats: Dict[str, Any] = None
    ) -> str:
        """피드백 데이터를 텍스트로 포맷팅"""
        lines = []

        # 통계 추가
        if stats:
            lines.append("## 통계")
            lines.append(f"- 전체: {stats.get('total', 0)}개")
            lines.append(f"- 긍정: {stats.get('positive', 0)}개")
            lines.append(f"- 부정: {stats.get('negative', 0)}개")
            lines.append(f"- 만족도: {stats.get('satisfaction_rate', 0)*100:.0f}%")
            lines.append("")

        # 피드백 목록
        lines.append("## 피드백 상세")
        for i, fb in enumerate(feedbacks, 1):
            fb_type = fb.get("feedback_type", "unknown")
            page = fb.get("context", {}).get("page", "알 수 없음")
            user_msg = fb.get("user_message", "")[:100]
            created = fb.get("created_at", "")[:10]
            fb_value = fb.get("feedback_value", "")

            lines.append(f"### {i}. [{fb_type}] - {page}")
            lines.append(f"- 날짜: {created}")
            if user_msg:
                lines.append(f"- 사용자 질문: {user_msg}...")
            if fb_value:
                if isinstance(fb_value, dict):
                    fb_value = fb_value.get("comment", str(fb_value))
                lines.append(f"- 피드백 내용: {fb_value}")
            lines.append("")

        return "\n".join(lines)


def run_feedback_analysis(
    feedbacks: List[Dict[str, Any]],
    stats: Dict[str, Any] = None,
    api_key: str = None
) -> Dict[str, Any]:
    """
    피드백 분석 실행 (간편 함수)

    Args:
        feedbacks: 피드백 리스트
        stats: 피드백 통계
        api_key: Anthropic API 키

    Returns:
        분석 결과
    """
    agent = CheckinAgent(api_key=api_key)
    return agent.analyze_feedbacks(feedbacks, stats)
