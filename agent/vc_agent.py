"""
Unified VC Investment Agent - Single Agent Architecture

하나의 에이전트가 모든 작업을 수행:
- 대화형 모드 (chat)
- 자율 실행 모드 (goal)
- 도구 실행
"""

import os
import json
from typing import AsyncIterator, Dict, Any, List, Optional
from dotenv import load_dotenv

from anthropic import Anthropic, AsyncAnthropic
from .tools import register_tools, execute_tool
from .memory import ChatMemory
from .feedback import FeedbackSystem

load_dotenv()


class VCAgent:
    """
    통합 VC 투자 분석 에이전트

    단일 에이전트로 모든 작업 수행:
    - chat(message): 대화형 인터페이스
    - achieve_goal(goal): 자율 실행
    - execute_tool(tool, params): 직접 도구 실행
    """

    def __init__(
        self,
        api_key: str = None,
        model: str = "claude-opus-4-5-20251101"
    ):
        """
        Args:
            api_key: Anthropic API 키 (없으면 환경변수)
            model: Claude 모델 (기본: Opus 4.5)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY가 필요합니다. "
                ".env 파일에 설정하거나 환경변수로 지정하세요."
            )

        # Anthropic SDK
        self.client = Anthropic(api_key=self.api_key)
        self.async_client = AsyncAnthropic(api_key=self.api_key)
        self.model = model

        # 도구 등록
        self.tools = register_tools()

        # 대화 히스토리
        self.conversation_history: List[Dict[str, Any]] = []

        # 작업 컨텍스트
        self.context = {
            "analyzed_files": [],
            "cached_results": {},
            "last_analysis": None
        }

        # 메모리 시스템
        self.memory = ChatMemory()

        # 피드백 시스템
        self.feedback = FeedbackSystem()

        # 마지막 응답 저장 (피드백용)
        self.last_interaction = {
            "user_message": None,
            "assistant_response": None,
            "context": {}
        }

    # ========================================
    # System Prompt
    # ========================================

    def _build_system_prompt(self) -> str:
        """동적 시스템 프롬프트 생성"""

        analyzed_files = ", ".join(self.context["analyzed_files"]) if self.context["analyzed_files"] else "없음"

        return f"""당신은 **VC 투자 분석 전문 에이전트**입니다.

## 현재 컨텍스트
- 분석된 파일: {analyzed_files}
- 캐시된 결과: {len(self.context["cached_results"])}개

## ⚠️ 절대 규칙 (CRITICAL)

**절대로 도구 없이 답변하지 마세요!**

- 엑셀 파일 분석 → 반드시 read_excel_as_text 또는 analyze_excel 사용
- Exit 프로젝션 생성 → 반드시 analyze_and_generate_projection 사용
- 추측하거나 예시 답변 금지 → 실제 도구를 실행해서 결과를 얻어야 함
- 텍스트로만 "완료되었습니다" 같은 거짓 응답 절대 금지

**사용자가 파일 경로를 주면 즉시 도구를 호출하세요!**

## 핵심 역량

### 1. 유연한 엑셀 분석
- **read_excel_as_text**: 엑셀을 텍스트로 변환하여 읽기 (구조가 다양해도 OK)
- **analyze_excel**: 자동 파싱 (투자조건, IS요약, Cap Table)
- 엑셀 구조가 특이하거나 복잡하면 read_excel_as_text를 먼저 사용하세요

### 2. 시나리오 분석
- PER, EV/Revenue, EV/EBITDA 등 모든 밸류에이션 방법론
- 전체 매각, 부분 매각, SAFE 전환, 콜옵션 등
- 사용자가 원하는 어떤 조합도 계산 가능

### 3. Exit 프로젝션 생성
- **analyze_and_generate_projection**: 엑셀 분석 후 즉시 Exit 프로젝션 생성
- 연도, PER 배수, 회사명 등을 지정하여 맞춤형 엑셀 생성

## 작업 방식

### 엑셀 파일을 받으면:
1. **즉시** read_excel_as_text 도구 호출 (구조 파악)
2. 텍스트에서 필요한 정보 추출 (투자금액, 당기순이익, 총주식수 등)
3. 사용자가 원하는 분석 수행
4. **즉시** analyze_and_generate_projection 도구 호출 (Exit 프로젝션 생성)
5. 결과 설명

### 예시 워크플로우:
```
사용자: "temp/파일.xlsx를 2030년 PER 10,20,30배로 분석해줘"

잘못된 응답:
"분석을 시작하겠습니다. 완료되었습니다"

올바른 응답:
1. read_excel_as_text 도구를 즉시 호출
2. 실제 엑셀 내용을 읽어서 정보 추출
3. analyze_and_generate_projection 도구를 즉시 호출
4. 생성된 파일 경로와 결과를 사용자에게 알려줌
```

## 중요 원칙
- **도구 우선**: 항상 도구를 먼저 사용하고, 실제 결과를 바탕으로 답변
- **추측 금지**: 엑셀 내용을 모르면 read_excel_as_text로 읽어야 함
- **실행 확인**: 도구 실행 결과를 확인한 후에만 성공 여부를 알려줌
- **명확한 설명**: IRR, 멀티플, 기업가치 등을 실제 숫자로 설명

## 사용 가능한 도구
{json.dumps([t["name"] for t in self.tools], ensure_ascii=False, indent=2)}

## 답변 스타일 가이드

**매우 중요: 이 분석은 투자심사 보고서에 사용됩니다.**

- **전문적이고 진중한 톤**: 이모지 사용 금지 (✅❌📊📈 등)
- **정확한 수치**: 모든 재무 지표는 정확한 숫자로 제시
- **객관적 분석**: 감정적 표현 배제, 사실 기반 분석
- **명확한 구조**: 제목, 항목, 수치를 체계적으로 정리
- **보고서 품질**: 투자심사역이 바로 사용할 수 있는 수준의 분석

예시:
- 나쁜 예: "✅ 분석 완료했어요! 😊"
- 좋은 예: "분석을 완료했습니다."

- 나쁜 예: "IRR이 35%네요! 👍"
- 좋은 예: "IRR 35.2%로 목표 수익률을 상회합니다."

한국어로 전문적이고 정중하게 답변하세요.
"""

    # ========================================
    # Chat Mode (대화형)
    # ========================================

    async def chat(self, user_message: str) -> AsyncIterator[str]:
        """
        대화형 인터페이스 (스트리밍)

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

        # 메모리에 저장
        self.memory.add_message("user", user_message)

        # 마지막 인터랙션 저장
        self.last_interaction["user_message"] = user_message
        self.last_interaction["assistant_response"] = ""
        self.last_interaction["context"] = {}

        # 시스템 프롬프트
        system_prompt = self._build_system_prompt()

        # Claude API 호출 (스트리밍)
        async with self.async_client.messages.stream(
            model=self.model,
            system=system_prompt,
            messages=self.conversation_history,
            tools=self.tools,
            max_tokens=8192
        ) as stream:

            async for event in stream:
                # 텍스트 출력
                if event.type == "content_block_delta":
                    if hasattr(event.delta, 'text'):
                        yield event.delta.text

                # 도구 사용
                elif event.type == "content_block_stop":
                    message = await stream.get_final_message()

                    # 도구 호출 처리
                    tool_results = []
                    assistant_response_parts = []

                    for content_block in message.content:
                        if content_block.type == "text":
                            assistant_response_parts.append(content_block.text)
                        elif content_block.type == "tool_use":
                            tool_name = content_block.name
                            tool_input = content_block.input

                            yield f"\n\n**도구: {tool_name}**\n"

                            # 도구 실행
                            tool_result = execute_tool(tool_name, tool_input)

                            # 메모리에 도구 사용 기록
                            self.memory.add_message("tool", f"도구 사용: {tool_name}", {
                                "tool_name": tool_name,
                                "input": tool_input,
                                "result": tool_result
                            })

                            # 결과 저장
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": content_block.id,
                                "content": json.dumps(tool_result, ensure_ascii=False)
                            })

                            # 컨텍스트 업데이트
                            if tool_name in ["analyze_excel", "read_excel_as_text"]:
                                if tool_result.get("success"):
                                    file_path = tool_input.get("excel_path")
                                    if file_path and file_path not in self.context["analyzed_files"]:
                                        self.context["analyzed_files"].append(file_path)
                                        self.memory.add_file_analysis(file_path)
                                    self.context["last_analysis"] = tool_result

                            # Exit 프로젝션 생성 기록
                            if tool_name == "analyze_and_generate_projection":
                                if tool_result.get("success"):
                                    output_file = tool_result.get("output_file")
                                    if output_file:
                                        self.memory.add_generated_file(output_file)

                            yield f"완료\n\n"

                    # Assistant 응답 메모리에 저장
                    if assistant_response_parts:
                        full_response = "\n".join(assistant_response_parts)
                        self.memory.add_message("assistant", full_response)
                        self.last_interaction["assistant_response"] = full_response

                    # 도구 결과가 있으면 대화 계속
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

                        # Claude 다음 응답 생성
                        async for text in self._continue_conversation():
                            yield text

    async def _continue_conversation(self) -> AsyncIterator[str]:
        """도구 실행 후 대화 계속"""

        system_prompt = self._build_system_prompt()

        async with self.async_client.messages.stream(
            model=self.model,
            system=system_prompt,
            messages=self.conversation_history,
            tools=self.tools,
            max_tokens=8192
        ) as stream:

            async for event in stream:
                if event.type == "content_block_delta":
                    if hasattr(event.delta, 'text'):
                        yield event.delta.text

                # 추가 도구 호출 (재귀적 처리)
                elif event.type == "content_block_stop":
                    message = await stream.get_final_message()

                    tool_results = []
                    for content_block in message.content:
                        if content_block.type == "tool_use":
                            tool_name = content_block.name
                            tool_input = content_block.input

                            yield f"\n\n**도구: {tool_name}**\n"

                            tool_result = execute_tool(tool_name, tool_input)

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": content_block.id,
                                "content": json.dumps(tool_result, ensure_ascii=False)
                            })

                            yield f"완료\n\n"

                    if tool_results:
                        self.conversation_history.append({
                            "role": "assistant",
                            "content": message.content
                        })

                        self.conversation_history.append({
                            "role": "user",
                            "content": tool_results
                        })

                        async for text in self._continue_conversation():
                            yield text

    # ========================================
    # Utility Methods
    # ========================================

    def chat_sync(self, user_message: str) -> str:
        """동기 버전 chat (간단한 사용)"""
        import asyncio

        async def run():
            response = ""
            async for chunk in self.chat(user_message):
                response += chunk
            return response

        loop = asyncio.get_event_loop()
        return loop.run_until_complete(run())

    def reset(self):
        """세션 초기화"""
        self.conversation_history = []
        self.context = {
            "analyzed_files": [],
            "cached_results": {},
            "last_analysis": None
        }
