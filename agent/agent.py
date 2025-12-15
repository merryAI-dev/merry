"""Conversational VC Investment Agent"""

import os
from typing import AsyncIterator, Dict, Any, List
from dotenv import load_dotenv

# TODO: Migrate to Claude Agent SDK when available on PyPI
# from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from anthropic import Anthropic, AsyncAnthropic

from .tools import register_tools, execute_tool

# 환경 변수 로드
load_dotenv()


class AgentContext:
    """에이전트 작업 컨텍스트 (메모리)"""

    def __init__(self):
        self.analyzed_files: List[str] = []
        self.cached_results: Dict[str, Any] = {}
        self.user_preferences: Dict[str, Any] = {}

    def remember(self, key: str, value: Any):
        """정보 기억"""
        self.cached_results[key] = value

    def recall(self, key: str) -> Any:
        """정보 회상"""
        return self.cached_results.get(key)

    def add_analyzed_file(self, file_path: str):
        """분석한 파일 기록"""
        if file_path not in self.analyzed_files:
            self.analyzed_files.append(file_path)


class ConversationalVCAgent:
    """자연어로 소통 가능한 VC 투자 분석 에이전트"""

    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4"):
        """
        Args:
            api_key: Anthropic API 키 (없으면 환경변수에서 로드)
            model: 사용할 모델 (claude-sonnet-4, claude-opus-4 등)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY가 설정되지 않았습니다. "
                ".env 파일을 생성하거나 환경변수를 설정하세요."
            )

        # Using Anthropic SDK (will migrate to Claude Agent SDK when available)
        self.client = Anthropic(api_key=self.api_key)
        self.async_client = AsyncAnthropic(api_key=self.api_key)
        self.model = model

        # 도구 등록
        self.tools = register_tools()

        # 대화 히스토리 (for session continuity)
        self.conversation_history: List[Dict[str, Any]] = []

        # 컨텍스트 (메모리)
        self.context = AgentContext()

    def _build_system_prompt(self) -> str:
        """동적 시스템 프롬프트 생성"""

        analyzed_files_str = ", ".join(self.context.analyzed_files) if self.context.analyzed_files else "없음"

        return f"""당신은 VC 투자 분석 전문가입니다. 사용자의 요구사항을 이해하고 적절한 도구를 조합하여 분석을 수행합니다.

## 현재 컨텍스트
- 분석된 파일: {analyzed_files_str}
- 캐시된 결과: {len(self.context.cached_results)}개

## 능력
1. **유연한 시나리오 분석**: 사용자가 요청한 어떤 조합의 시나리오도 분석 가능
   - 표준 시나리오: 전체 매각, 부분 매각, SAFE 전환, 콜옵션
   - 맞춤 시나리오: 사용자가 정의한 독특한 구조

2. **다양한 밸류에이션 방법론**
   - PER, EV/Revenue, EV/EBITDA 등 모든 방법론 지원
   - 혼합 방식도 가능 (예: 2029년은 PER, 2030년은 EV/Revenue)

3. **복잡한 희석 구조**
   - SAFE, 콜옵션, 신규 투자 라운드 등
   - 다단계 투자 라운드 시뮬레이션

4. **맞춤형 Exit 시나리오**
   - 2단계, 3단계, N단계 매각
   - 시간에 따른 가치 변화 반영

## 작업 방식
1. 사용자 요구사항을 정확히 이해
2. 필요한 데이터 확인 (없으면 질문)
3. 적절한 도구 조합으로 분석 수행
4. 결과를 명확하게 설명
5. 추가 분석이나 수정사항 제안

## 중요 원칙
- **절대 고정된 틀에 맞추지 마세요**: "이건 basic/advanced/complete 중 하나"가 아닙니다
- **사용자 의도를 파악하세요**: "부분 매각"이라고 하면 비율과 시점을 물어보세요
- **창의적으로 조합하세요**: 기존에 없던 시나리오도 도구를 조합해 분석하세요
- **한국어로 친절하게 답변하세요**: 전문 용어는 쉽게 설명하세요

## 도구 사용 가이드
- `analyze_excel`: 엑셀 파일 분석 (첫 단계)
- `calculate_valuation`: 기업가치 계산 (PER, EV/Revenue 등)
- `calculate_dilution`: 지분 희석 계산 (SAFE, 신규 라운드 등)
- `calculate_irr`: IRR과 멀티플 계산
- `generate_exit_projection`: 최종 엑셀 파일 생성

## 예시 워크플로우
1. 사용자: "비사이드미 투자 분석해줘"
   → analyze_excel 사용

2. 사용자: "2029년 PER 15로 Exit 시 IRR은?"
   → calculate_valuation → calculate_irr

3. 사용자: "SAFE 1억 추가되면 희석 얼마?"
   → calculate_dilution

4. 사용자: "엑셀로 만들어줘"
   → generate_exit_projection
"""

    async def chat(self, user_message: str) -> AsyncIterator[str]:
        """
        자연어 대화 인터페이스 (비동기 스트리밍)

        Args:
            user_message: 사용자 메시지

        Yields:
            str: 에이전트 응답 (스트리밍)
        """

        # 대화 히스토리에 추가
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # 시스템 프롬프트 생성
        system_prompt = self._build_system_prompt()

        # Claude API 호출 (스트리밍)
        async with self.async_client.messages.stream(
            model=self.model,
            system=system_prompt,
            messages=self.conversation_history,
            tools=self.tools,
            max_tokens=4096
        ) as stream:

            assistant_content = []

            async for event in stream:
                # 텍스트 출력
                if event.type == "content_block_delta":
                    if hasattr(event.delta, 'text'):
                        text = event.delta.text
                        assistant_content.append({"type": "text", "text": text})
                        yield text

                # 도구 사용
                elif event.type == "content_block_stop":
                    message = await stream.get_final_message()

                    # 도구 호출 처리
                    tool_results = []
                    for content_block in message.content:
                        if content_block.type == "tool_use":
                            tool_name = content_block.name
                            tool_input = content_block.input

                            yield f"\n\n🔧 **도구 사용: {tool_name}**\n"

                            # 도구 실행
                            tool_result = execute_tool(tool_name, tool_input)

                            # 결과 저장
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": content_block.id,
                                "content": str(tool_result)
                            })

                            # 컨텍스트 업데이트
                            if tool_name == "analyze_excel" and tool_result.get("success"):
                                self.context.add_analyzed_file(tool_input.get("excel_path"))
                                self.context.remember("last_analysis", tool_result)

                            yield f"✅ 완료\n\n"

                    # 도구 결과가 있으면 대화에 추가하고 계속 진행
                    if tool_results:
                        # Assistant 메시지 추가
                        self.conversation_history.append({
                            "role": "assistant",
                            "content": message.content
                        })

                        # Tool 결과 추가
                        self.conversation_history.append({
                            "role": "user",
                            "content": tool_results
                        })

                        # Claude가 다음 응답 생성
                        async for continuation_text in self._continue_conversation():
                            yield continuation_text

    async def _continue_conversation(self) -> AsyncIterator[str]:
        """도구 실행 후 대화 계속"""

        system_prompt = self._build_system_prompt()

        async with self.async_client.messages.stream(
            model=self.model,
            system=system_prompt,
            messages=self.conversation_history,
            tools=self.tools,
            max_tokens=4096
        ) as stream:

            async for event in stream:
                if event.type == "content_block_delta":
                    if hasattr(event.delta, 'text'):
                        yield event.delta.text

    def chat_sync(self, user_message: str) -> str:
        """
        동기 버전 (간단한 사용)

        Args:
            user_message: 사용자 메시지

        Returns:
            str: 에이전트 응답 (전체)
        """
        import asyncio

        # 비동기 함수를 동기로 실행
        async def async_chat():
            response_text = ""
            async for chunk in self.chat(user_message):
                response_text += chunk
            return response_text

        loop = asyncio.get_event_loop()
        return loop.run_until_complete(async_chat())

    def reset(self):
        """대화 히스토리 초기화"""
        self.conversation_history = []
        self.context = AgentContext()
