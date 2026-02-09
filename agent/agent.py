"""Conversational VC Investment Agent"""

import os
from typing import AsyncIterator, Dict, Any, List, Optional
from dotenv import load_dotenv

# TODO: Migrate to Claude Agent SDK when available on PyPI
# from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from anthropic import Anthropic, AsyncAnthropic

from .tools import register_tools, execute_tool
from .streaming import AgentOutput
from .memory import ChatMemory
from shared.logging_config import get_logger

# 환경 변수 로드
load_dotenv()

logger = get_logger("agent")
MAX_HISTORY_MESSAGES = 20


class ConversationalVCAgent:
    """자연어로 소통 가능한 VC 투자 분석 에이전트"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-5-20250929",
        user_id: Optional[str] = None,
    ):
        """
        Args:
            api_key: Anthropic API 키 (없으면 환경변수에서 로드)
            model: 사용할 모델 (claude-sonnet-4-5-20250929, claude-opus-4-6 등)
            user_id: 세션 저장용 사용자 ID (없으면 anonymous)
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
        self.memory = ChatMemory(user_id=user_id)

    def _trim_history(self) -> None:
        if len(self.conversation_history) > MAX_HISTORY_MESSAGES:
            self.conversation_history = self.conversation_history[-MAX_HISTORY_MESSAGES:]

    def _build_tool_descriptions(self) -> str:
        lines = []
        for tool in self.tools:
            name = tool.get("name", "")
            description = tool.get("description", "")
            if name:
                lines.append(f"- `{name}`: {description}")
        return "\n".join(lines)

    def _build_system_prompt(self) -> str:
        """동적 시스템 프롬프트 생성"""

        analyzed_files = self.memory.session_metadata.get("analyzed_files", [])
        analyzed_files_str = ", ".join(analyzed_files) if analyzed_files else "없음"
        cached_count = len(self.memory.cached_results)
        tool_list = self._build_tool_descriptions()

        return f"""당신은 VC 투자 분석 전문가입니다. 사용자의 요구사항을 이해하고 적절한 도구를 조합하여 분석을 수행합니다.

## 현재 컨텍스트
- 분석된 파일: {analyzed_files_str}
- 캐시된 결과: {cached_count}개

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
{tool_list}

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

    async def chat_events(self, user_message: str) -> AsyncIterator[AgentOutput]:
        """
        자연어 대화 인터페이스 (비동기 스트리밍)

        Args:
            user_message: 사용자 메시지

        Yields:
            AgentOutput: 에이전트 응답 이벤트
        """

        logger.info("User message received: %s", user_message[:120])

        # 대화 히스토리에 추가
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        self._trim_history()

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

            assistant_content: List[str] = []

            async for event in stream:
                # 텍스트 출력
                if event.type == "content_block_delta":
                    if hasattr(event.delta, 'text'):
                        text = event.delta.text
                        assistant_content.append(text)
                        yield AgentOutput(type="text", content=text)

            message = await stream.get_final_message()

        tool_results = []
        tool_uses = [
            block for block in (message.content or [])
            if getattr(block, "type", "") == "tool_use"
        ]

        if tool_uses:
            for content_block in tool_uses:
                tool_name = content_block.name
                tool_input = content_block.input

                logger.info("Tool call: %s", tool_name)
                logger.debug("Tool input: %s", tool_input)
                yield AgentOutput(
                    type="tool_start",
                    content=tool_name,
                    data={"tool_input": tool_input},
                )

                try:
                    tool_result = execute_tool(tool_name, tool_input)
                except Exception as exc:
                    logger.exception("Tool execution failed: %s", tool_name)
                    tool_result = {"success": False, "error": str(exc)}
                    yield AgentOutput(
                        type="tool_error",
                        content=str(exc),
                        data={"tool_name": tool_name},
                    )

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": content_block.id,
                    "content": str(tool_result)
                })

                # 컨텍스트 업데이트
                if tool_name == "analyze_excel" and isinstance(tool_result, dict) and tool_result.get("success"):
                    self.memory.add_file_analysis(tool_input.get("excel_path"))
                    self.memory.remember("last_analysis", tool_result)

                yield AgentOutput(
                    type="tool_result",
                    content=str(tool_result),
                    data={
                        "tool_name": tool_name,
                        "success": not (isinstance(tool_result, dict) and tool_result.get("success") is False),
                    },
                )

        # Assistant 메시지 추가
        if tool_uses:
            self.conversation_history.append({
                "role": "assistant",
                "content": message.content
            })
            self._trim_history()

            # Tool 결과 추가
            self.conversation_history.append({
                "role": "user",
                "content": tool_results
            })
            self._trim_history()

            # Claude가 다음 응답 생성
            async for continuation_event in self._continue_conversation_events():
                yield continuation_event
        else:
            assistant_text = "".join(assistant_content).strip()
            if assistant_text:
                self.conversation_history.append({
                    "role": "assistant",
                    "content": assistant_text
                })
                self._trim_history()

    async def chat(self, user_message: str) -> AsyncIterator[str]:
        async for event in self.chat_events(user_message):
            if event.type == "text":
                yield event.content
            elif event.type == "tool_start":
                yield f"\n\n🔧 **도구 사용: {event.content}**\n"
            elif event.type == "tool_error":
                yield f"❌ 도구 실행 실패: {event.content}\n"
            elif event.type == "tool_result":
                tool_name = (event.data or {}).get("tool_name", "tool")
                tool_ok = (event.data or {}).get("success", True)
                yield f"✅ 도구 {tool_name} {'완료' if tool_ok else '실패'}\n\n"

    async def _continue_conversation_events(self) -> AsyncIterator[AgentOutput]:
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
                        yield AgentOutput(type="text", content=event.delta.text)

            message = await stream.get_final_message()

        tool_results = []
        tool_uses = [
            block for block in (message.content or [])
            if getattr(block, "type", "") == "tool_use"
        ]

        for content_block in tool_uses:
            tool_name = content_block.name
            tool_input = content_block.input

            logger.info("Tool call: %s", tool_name)
            logger.debug("Tool input: %s", tool_input)
            yield AgentOutput(type="tool_start", content=tool_name, data={"tool_input": tool_input})

            try:
                tool_result = execute_tool(tool_name, tool_input)
            except Exception as exc:
                logger.exception("Tool execution failed: %s", tool_name)
                tool_result = {"success": False, "error": str(exc)}
                yield AgentOutput(type="tool_error", content=str(exc), data={"tool_name": tool_name})

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": content_block.id,
                "content": str(tool_result),
            })

            if tool_name == "analyze_excel" and isinstance(tool_result, dict) and tool_result.get("success"):
                self.memory.add_file_analysis(tool_input.get("excel_path"))
                self.memory.remember("last_analysis", tool_result)

            yield AgentOutput(
                type="tool_result",
                content=str(tool_result),
                data={
                    "tool_name": tool_name,
                    "success": not (isinstance(tool_result, dict) and tool_result.get("success") is False),
                },
            )

        if tool_results:
            self.conversation_history.append({
                "role": "assistant",
                "content": message.content
            })

            self.conversation_history.append({
                "role": "user",
                "content": tool_results
            })
            self._trim_history()

            async for continuation_event in self._continue_conversation_events():
                yield continuation_event

    async def _continue_conversation(self) -> AsyncIterator[str]:
        async for event in self._continue_conversation_events():
            if event.type == "text":
                yield event.content

    def chat_sync(self, user_message: str) -> str:
        """
        동기 버전 (간단한 사용)

        Args:
            user_message: 사용자 메시지

        Returns:
            str: 에이전트 응답 (전체)
        """
        import asyncio
        import threading

        # 비동기 함수를 동기로 실행
        async def async_chat():
            response_text = ""
            async for chunk in self.chat(user_message):
                response_text += chunk
            return response_text

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(async_chat())

        if loop.is_running():
            result: Dict[str, str] = {}

            def _runner():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result["value"] = new_loop.run_until_complete(async_chat())
                finally:
                    new_loop.close()

            thread = threading.Thread(target=_runner)
            thread.start()
            thread.join()
            return result.get("value", "")

        return loop.run_until_complete(async_chat())

    def reset(self):
        """대화 히스토리 초기화"""
        self.conversation_history = []
        self.memory.start_new_session()
        self.memory.cached_results = {}
