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
from shared.logging_config import get_logger

load_dotenv()

logger = get_logger("vc_agent")

# 안전장치: 최대 도구 호출 횟수
MAX_TOOL_STEPS = 15


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
        model: str = "claude-opus-4-5-20251101",
        user_id: str = None
    ):
        """
        Args:
            api_key: Anthropic API 키 (없으면 환경변수)
            model: Claude 모델 (기본: Opus 4.5)
            user_id: 사용자 고유 ID (같은 ID끼리 세션/피드백 공유)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.user_id = user_id or "anonymous"

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

        # 메모리 시스템 (user_id 기반)
        self.memory = ChatMemory(user_id=self.user_id)

        # 피드백 시스템 (user_id 기반)
        self.feedback = FeedbackSystem(user_id=self.user_id)

        # 마지막 응답 저장 (피드백용)
        self.last_interaction = {
            "user_message": None,
            "assistant_response": None,
            "context": {}
        }

        # 토큰 사용량 추적
        self.token_usage = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "session_calls": 0
        }

        # 도구 호출 카운터 (무한 루프 방지)
        self._tool_step_count = 0

    # ========================================
    # System Prompt
    # ========================================

    def _build_system_prompt(self, mode: str = "exit") -> str:
        """동적 시스템 프롬프트 생성

        Args:
            mode: "exit" (Exit 프로젝션) 또는 "peer" (Peer PER 분석)
        """

        analyzed_files = ", ".join(self.context["analyzed_files"]) if self.context["analyzed_files"] else "없음"

        # Peer PER 분석 모드
        if mode == "peer":
            return self._build_peer_system_prompt(analyzed_files)

        # 기업현황 진단시트 모드
        if mode == "diagnosis":
            return self._build_diagnosis_system_prompt(analyzed_files)

        # Exit 프로젝션 모드 (기본)
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

    def _build_peer_system_prompt(self, analyzed_files: str) -> str:
        """Peer PER 분석 모드 시스템 프롬프트"""

        return f"""당신은 **VC 투자 분석 전문 에이전트**입니다. 현재 **Peer PER 분석 모드**입니다.

## 현재 컨텍스트
- 분석된 파일: {analyzed_files}
- 캐시된 결과: {len(self.context["cached_results"])}개

## 🚨 최우선 규칙 (이 규칙을 어기면 실패입니다)

### 규칙 1: 사용자가 PER 분석을 요청하면 즉시 도구 호출
사용자가 다음과 같이 말하면 **텍스트 응답 없이 바로 analyze_peer_per 도구를 호출**하세요:
- "해줘", "분석해줘", "진행해", "PER 분석", "조회해줘"
- "응", "네", "좋아", "OK", "ㅇㅇ", "그래", "고", "ㄱㄱ"
- Peer 기업 목록을 언급하는 경우

❌ 잘못된 예:
```
사용자: "저 기업으로 PER/PSR 분석을 해주세요"
에이전트: "기업 분석 결과를 정리하겠습니다..." (텍스트만 출력)
```

✅ 올바른 예:
```
사용자: "저 기업으로 PER/PSR 분석을 해주세요"
에이전트: [즉시 analyze_peer_per 도구 호출]
```

### 규칙 2: 같은 내용 반복 금지
- 이미 출력한 "기업 분석 결과" 표를 다시 출력하지 마세요
- 이미 제안한 Peer 기업 목록을 다시 나열하지 마세요
- 이전 응답을 요약하거나 반복하지 마세요

### 규칙 3: "~하겠습니다"로 끝내지 말 것
"분석하겠습니다", "진행하겠습니다"라고만 말하고 끝내면 안됩니다.
반드시 해당 도구를 실제로 호출해야 합니다.

## Peer PER 분석 워크플로우

### 1단계: PDF 분석 (최초 1회만)
사용자가 PDF 경로를 제공하면:
1. read_pdf_as_text 도구 호출
2. 기업 정보 요약 (1회만 출력)
3. Peer 기업 후보 제안 후 "진행할까요?" 질문

### 2단계: PER 조회 (사용자 동의 시 즉시 실행)
사용자가 동의하면 **설명 없이 바로** analyze_peer_per 도구 호출

### 3단계: 결과 요약
도구 결과를 바탕으로:
- PER 비교표 (마크다운 표)
- 통계 요약 (평균, 중간값, 범위)
- 적정 PER 배수 제안

## 사용 가능한 도구

- **read_pdf_as_text**: PDF를 텍스트로 변환
- **get_stock_financials**: 개별 기업 재무 지표 조회
- **analyze_peer_per**: 여러 Peer 기업 PER 일괄 조회 (⭐ 가장 많이 사용)

## 티커 형식
- 미국: AAPL, MSFT, GOOGL
- 한국 KOSPI: 005930.KS
- 한국 KOSDAQ: 035720.KQ

## 답변 스타일
- 전문적이고 간결하게
- 이모지 사용 금지
- 반복 금지 - 새로운 정보만 추가
	- 표 형식 활용
	
	한국어로 답변하세요.
	"""

    def _build_diagnosis_system_prompt(self, analyzed_files: str) -> str:
        """기업현황 진단시트 모드 시스템 프롬프트"""

        return f"""당신은 **프로그램 컨설턴트(VC/AC)**입니다. 현재 **기업현황 진단시트 작성 모드**입니다.

## 현재 컨텍스트
- 분석된 파일: {analyzed_files}
- 캐시된 결과: {len(self.context["cached_results"])}개

## 🚨 최우선 규칙 (CRITICAL)

**절대로 도구 없이 답변하지 마세요!**

- 진단시트 분석 → 반드시 **analyze_company_diagnosis_sheet** 사용
- 컨설턴트 보고서 엑셀 반영 → 반드시 **write_company_diagnosis_report** 사용
- 추측/예시 답변 금지 → 실제 시트 내용 기반으로 작성

## 목표

사용자와의 대화를 통해 기업현황 진단시트의 **'(컨설턴트용) 분석보고서'**를 완성합니다.

## 작업 방식

### 1) 파일을 받으면 (CRITICAL - 즉시 실행)
사용자가 진단시트 파일 경로를 주면 → **즉시** analyze_company_diagnosis_sheet 호출

### 2) 보고서 초안 작성
도구 결과를 바탕으로 아래 2개 텍스트를 작성:
- **기업 상황 요약(기업진단)**: 강점/핵심 가설/현재 KPI/확장 포인트 중심으로 5~10문장
- **개선 필요사항**: 우선순위 3~7개, “왜 필요한지 + 다음 액션” 형태로 구체화

또한 점수(문제/솔루션/사업화/자금조달/팀/조직/임팩트)를 제안하되, 필요한 경우 컨설턴트 보정 근거를 함께 제시합니다.

### 3) 사용자 확인 후 엑셀 반영 (CRITICAL - 즉시 실행)
사용자가 아래처럼 긍정 응답하면 **다시 확인 요청하지 말고 즉시** write_company_diagnosis_report 호출:
- "응", "네", "좋아", "진행해", "반영해줘", "저장해줘", "엑셀로 만들어줘", "OK"

write_company_diagnosis_report에는 다음을 포함해 호출:
- excel_path (temp 내부 경로)
- scores (6개 항목 점수)
- summary_text, improvement_text
- (선택) company_name, report_datetime, output_filename

## 답변 스타일 가이드

**이 문서는 프로그램 운영/투자검토 문서로 사용됩니다.**

- 이모지 사용 금지
- 단정/과장 금지, 근거 중심
- 표/불릿으로 구조화
- “~하겠습니다”로 끝내지 말고, 가능한 경우 도구를 실행해 결과까지 제공

한국어로 전문적이고 정중하게 답변하세요.
"""

	    # ========================================
	    # Chat Mode (대화형)
	    # ========================================

    async def chat(self, user_message: str, mode: str = "exit") -> AsyncIterator[str]:
        """
        대화형 인터페이스 (스트리밍)

        Args:
            user_message: 사용자 메시지
            mode: "exit" (Exit 프로젝션) 또는 "peer" (Peer PER 분석)

        Yields:
            str: 에이전트 응답 (스트리밍)
        """

        # 도구 호출 카운터 초기화 (새 메시지마다)
        self._tool_step_count = 0

        # 현재 모드 저장
        self._current_mode = mode

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
        self.last_interaction["context"] = {"mode": mode}

        # 시스템 프롬프트 (모드에 따라 다름)
        system_prompt = self._build_system_prompt(mode)

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

                    # 토큰 사용량 추적
                    if hasattr(message, 'usage'):
                        self.token_usage["total_input_tokens"] += message.usage.input_tokens
                        self.token_usage["total_output_tokens"] += message.usage.output_tokens
                        self.token_usage["session_calls"] += 1

                    # 도구 호출 처리
                    tool_results = []
                    assistant_response_parts = []

                    for content_block in message.content:
                        if content_block.type == "text":
                            assistant_response_parts.append(content_block.text)
                        elif content_block.type == "tool_use":
                            tool_name = content_block.name
                            tool_input = content_block.input

                            yield f"\n\n**도구: {tool_name}** 실행 중...\n"

                            # 도구 실행
                            tool_result = execute_tool(tool_name, tool_input)

                            # 결과 저장
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": content_block.id,
                                "content": json.dumps(tool_result, ensure_ascii=False)
                            })

                            # 메모리/컨텍스트 업데이트 (공통 헬퍼)
                            self._record_tool_usage(tool_name, tool_input, tool_result)

                            tool_ok = not (isinstance(tool_result, dict) and tool_result.get("success") is False)
                            yield f"**도구: {tool_name}** {'완료' if tool_ok else '실패'}\n\n"

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

        # 도구 호출 횟수 제한 확인 (무한 루프 방지)
        self._tool_step_count += 1
        if self._tool_step_count > MAX_TOOL_STEPS:
            logger.warning(f"Tool step limit reached: {MAX_TOOL_STEPS}")
            yield "\n\n[시스템] 도구 호출 횟수 제한에 도달했습니다. 새로운 메시지로 계속하세요."
            return

        # 저장된 모드 사용
        mode = getattr(self, '_current_mode', 'exit')
        system_prompt = self._build_system_prompt(mode)

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

                    # 토큰 사용량 추적
                    if hasattr(message, 'usage'):
                        self.token_usage["total_input_tokens"] += message.usage.input_tokens
                        self.token_usage["total_output_tokens"] += message.usage.output_tokens
                        self.token_usage["session_calls"] += 1

                    tool_results = []
                    for content_block in message.content:
                        if content_block.type == "tool_use":
                            tool_name = content_block.name
                            tool_input = content_block.input

                            yield f"\n\n**도구: {tool_name}** 실행 중...\n"

                            tool_result = execute_tool(tool_name, tool_input)

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": content_block.id,
                                "content": json.dumps(tool_result, ensure_ascii=False)
                            })

                            # 메모리/컨텍스트 업데이트 (재귀 호출에서도 기록)
                            self._record_tool_usage(tool_name, tool_input, tool_result)

                            tool_ok = not (isinstance(tool_result, dict) and tool_result.get("success") is False)
                            yield f"**도구: {tool_name}** {'완료' if tool_ok else '실패'}\n\n"

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

    def _record_tool_usage(self, tool_name: str, tool_input: dict, tool_result: dict):
        """도구 사용 결과를 메모리/컨텍스트에 기록 (공통 헬퍼)"""
        # 메모리에 도구 사용 기록
        self.memory.add_message("tool", f"도구 사용: {tool_name}", {
            "tool_name": tool_name,
            "input": tool_input,
            "result": tool_result
        })

        # 컨텍스트 업데이트 - 분석 파일
        if tool_name in ["analyze_excel", "read_excel_as_text", "analyze_company_diagnosis_sheet"]:
            if tool_result.get("success"):
                file_path = tool_input.get("excel_path")
                if file_path and file_path not in self.context["analyzed_files"]:
                    self.context["analyzed_files"].append(file_path)
                    self.memory.add_file_analysis(file_path)
                self.context["last_analysis"] = tool_result

        # 컨텍스트 업데이트 - PDF 분석
        if tool_name == "read_pdf_as_text":
            if tool_result.get("success"):
                file_path = tool_input.get("pdf_path")
                if file_path and file_path not in self.context["analyzed_files"]:
                    self.context["analyzed_files"].append(file_path)
                    self.memory.add_file_analysis(file_path)

        # 생성 파일 기록
        if tool_name in ["analyze_and_generate_projection", "generate_exit_projection", "write_company_diagnosis_report"]:
            if tool_result.get("success"):
                output_file = tool_result.get("output_file")
                if output_file:
                    self.memory.add_generated_file(output_file)

    # ========================================
    # Utility Methods
    # ========================================

    def chat_sync(self, user_message: str, mode: str = "exit") -> str:
        """동기 버전 chat (간단한 사용)

        Args:
            user_message: 사용자 메시지
            mode: "exit" (Exit 프로젝션) 또는 "peer" (Peer PER 분석)

        Returns:
            에이전트 응답 문자열
        """
        import asyncio

        async def run():
            response = ""
            async for chunk in self.chat(user_message, mode=mode):
                response += chunk
            return response

        # Python 3.10+ compatible: asyncio.run() 사용
        # 단, 이미 실행 중인 이벤트 루프가 있으면 nest_asyncio 필요
        try:
            # 이미 실행 중인 루프가 있는지 확인
            loop = asyncio.get_running_loop()
            # 실행 중인 루프가 있으면 (예: Jupyter, Streamlit)
            # nest_asyncio 또는 새 스레드에서 실행
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, run())
                return future.result()
        except RuntimeError:
            # 실행 중인 루프가 없으면 asyncio.run() 사용
            return asyncio.run(run())

    def get_token_usage(self) -> Dict[str, Any]:
        """토큰 사용량 및 예상 비용 반환"""
        # Claude Opus 4.5 가격 (2024년 기준)
        INPUT_PRICE_PER_1M = 15.0   # $15 / 1M input tokens
        OUTPUT_PRICE_PER_1M = 75.0  # $75 / 1M output tokens

        input_cost = (self.token_usage["total_input_tokens"] / 1_000_000) * INPUT_PRICE_PER_1M
        output_cost = (self.token_usage["total_output_tokens"] / 1_000_000) * OUTPUT_PRICE_PER_1M
        total_cost = input_cost + output_cost

        return {
            "input_tokens": self.token_usage["total_input_tokens"],
            "output_tokens": self.token_usage["total_output_tokens"],
            "total_tokens": self.token_usage["total_input_tokens"] + self.token_usage["total_output_tokens"],
            "api_calls": self.token_usage["session_calls"],
            "estimated_cost_usd": round(total_cost, 4),
            "estimated_cost_krw": round(total_cost * 1400, 0)  # 대략적 환율
        }

    def reset_token_usage(self):
        """토큰 사용량 초기화"""
        self.token_usage = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "session_calls": 0
        }

    def reset(self):
        """세션 초기화"""
        self.conversation_history = []
        self.context = {
            "analyzed_files": [],
            "cached_results": {},
            "last_analysis": None
        }
        self.reset_token_usage()
