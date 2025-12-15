"""
True Autonomous VC Investment Agent

Goal-oriented agent that autonomously plans, executes, and verifies tasks.
"""

import json
import asyncio
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
import os

# Migrated to Claude Agent SDK!
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock

from .tools import execute_tool, register_tools

load_dotenv()


class AutonomousVCAgent:
    """
    자율적으로 계획하고 실행하는 True Agent

    특징:
    - Goal 제시 → 자동으로 계획 수립
    - Agentic Loop: 계획된 단계 자율 실행
    - Autonomous Recovery: 에러 발생 시 스스로 복구
    - Goal Verification: 목표 달성 여부 검증
    """

    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY가 필요합니다")

        # Claude Agent SDK client (API key from environment variable)
        self.client = ClaudeSDKClient(
            options=ClaudeAgentOptions(
                model=model,
                setting_sources=["project"],  # Auto-load CLAUDE.md
                allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],  # Enable Claude Code built-in tools
                permission_mode="acceptEdits"  # Auto-accept file edits
            )
        )
        self.model = model
        self.tools = register_tools()

        # Execution state
        self.current_plan = None
        self.execution_log = []
        self.context = {}

    # ========================================
    # Core Agent Methods
    # ========================================

    async def achieve_goal(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Goal을 자율적으로 달성 (Claude SDK가 모든 작업을 수행)

        Args:
            goal: 최종 목표 (예: "투자 분석 완료 및 Exit 프로젝션 생성")
            context: 초기 컨텍스트 (파일 경로, 파라미터 등)
            verbose: 진행상황 출력 여부

        Returns:
            {
                "goal": str,
                "achieved": bool,
                "response": str,
                "messages": List[Message]
            }
        """

        if verbose:
            print("=" * 60)
            print(f"🎯 Goal: {goal}")
            print("=" * 60)
            print()

        # Connect to Claude Agent SDK
        await self.client.connect()

        # Initialize context
        self.context = context or {}

        # Build the goal prompt with context
        context_str = json.dumps(self.context, ensure_ascii=False, indent=2) if self.context else "없음"

        goal_prompt = f"""당신은 VC 투자 분석 전문 에이전트입니다.

Goal: {goal}

Context:
{context_str}

이 Goal을 자율적으로 달성해주세요. 필요한 도구를 사용하고, 파일을 읽고, 분석하고, 결과를 생성하세요.

중요한 원칙:
1. Goal 달성에 필요한 모든 단계를 수행하세요
2. 사용 가능한 도구: Read, Write, Edit, Bash, Glob, Grep
3. 에러 발생 시 스스로 문제를 해결하세요
4. 최종적으로 Goal이 달성되었는지 확인하고 결과를 보고하세요

작업을 시작하세요!"""

        # Send goal to Claude
        await self.client.query(goal_prompt)

        # Collect all responses
        full_response = ""
        all_messages = []

        if verbose:
            print("🤖 Claude Agent 작업 중...")
            print()

        async for message in self.client.receive_response():
            all_messages.append(message)

            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        full_response += block.text
                        if verbose:
                            print(block.text, end="", flush=True)

        if verbose:
            print()
            print()
            print("=" * 60)
            print("✅ 작업 완료!")
            print("=" * 60)

        # Disconnect from Claude Agent SDK
        await self.client.disconnect()

        # Return result
        return {
            "goal": goal,
            "achieved": True,  # Assume success if no exceptions
            "response": full_response,
            "messages": all_messages
        }

    # ========================================
    # Phase 1: Planning
    # ========================================

    async def _create_plan(
        self,
        goal: str,
        context: Dict[str, Any],
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        Goal을 달성하기 위한 구체적인 실행 계획 수립

        Returns:
            {
                "goal": str,
                "steps": [
                    {
                        "step": 1,
                        "action": "analyze_excel",
                        "params": {...},
                        "reason": "엑셀 파일에서 투자 데이터 추출 필요",
                        "critical": true,
                        "expected_output": "투자조건, IS요약, Cap Table"
                    },
                    ...
                ],
                "estimated_time": "5분",
                "dependencies": {...}
            }
        """

        context_str = json.dumps(context, ensure_ascii=False, indent=2) if context else "없음"

        planning_prompt = f"""당신은 VC 투자 분석 전문 에이전트입니다.

Goal: {goal}

Context:
{context_str}

이 Goal을 자율적으로 달성해주세요. 필요한 도구를 사용하고, 파일을 읽고, 분석하고, 결과를 생성하세요.

중요한 원칙:
1. Goal 달성에 필요한 모든 단계를 수행하세요
2. 사용 가능한 도구: Read, Write, Edit, Bash, Glob, Grep
3. 에러 발생 시 스스로 문제를 해결하세요
4. 최종적으로 Goal이 달성되었는지 확인하세요

작업을 시작하세요!"""

        # Claude Agent SDK streaming query with live output
        await self.client.query(planning_prompt)

        plan_text = ""
        async for message in self.client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        plan_text += block.text
                        if verbose:
                            print(".", end="", flush=True)

        plan = self._parse_json_from_text(plan_text)

        return plan

    # ========================================
    # Phase 2: Agentic Loop Execution
    # ========================================

    async def _execute_agentic_loop(
        self,
        plan: Dict[str, Any],
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        계획을 자율적으로 실행 (Agentic Loop)

        핵심:
        - 각 단계를 순차적으로 실행
        - 이전 단계 결과를 다음 단계에 전달
        - 실패 시 자율 복구 시도
        """

        results = {}
        output_files = []

        for step_info in plan['steps']:
            step_num = step_info['step']
            action = step_info['action']
            params = step_info.get('params', {})

            if verbose:
                print(f"🔄 Step {step_num}/{len(plan['steps'])}: {action}")
                print(f"   Reason: {step_info.get('reason', 'N/A')}")

            try:
                # 파라미터에 컨텍스트 값 대입
                resolved_params = self._resolve_params(params, results)

                # Tool 실행
                result = await self._execute_tool_with_retry(
                    tool_name=action,
                    params=resolved_params,
                    max_retries=3
                )

                # 성공 로깅
                self.execution_log.append({
                    "step": step_num,
                    "action": action,
                    "status": "success",
                    "result": result
                })

                # 결과 저장
                results[action] = result

                # 출력 파일 추적
                if result.get('success') and 'output_file' in result:
                    output_files.append(result['output_file'])

                if verbose:
                    print(f"   ✅ Success")
                    if 'output_file' in result:
                        print(f"   📄 Generated: {result['output_file']}")

            except Exception as e:
                if verbose:
                    print(f"   ⚠️  Error: {str(e)}")

                # 실패 로깅
                self.execution_log.append({
                    "step": step_num,
                    "action": action,
                    "status": "failed",
                    "error": str(e)
                })

                # Autonomous Recovery
                recovery_result = await self._autonomous_recovery(
                    step_info=step_info,
                    error=e,
                    context=results,
                    verbose=verbose
                )

                if recovery_result['recovered']:
                    if verbose:
                        print(f"   ✅ Recovered: {recovery_result['solution']}")

                    results[action] = recovery_result['result']

                    self.execution_log.append({
                        "step": step_num,
                        "action": action,
                        "status": "recovered",
                        "recovery": recovery_result
                    })
                else:
                    # Critical 단계 실패 시 중단
                    if step_info.get('critical', False):
                        if verbose:
                            print(f"   ❌ Critical step failed. Aborting.")
                        raise
                    else:
                        if verbose:
                            print(f"   ⏭️  Skipping non-critical step")

            if verbose:
                print()

        return {
            "results": results,
            "output_files": output_files
        }

    # ========================================
    # Phase 3: Goal Verification
    # ========================================

    async def _verify_goal(
        self,
        goal: str,
        execution_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Goal 달성 여부 검증

        Returns:
            {
                "goal_achieved": bool,
                "completeness": 0.0-1.0,
                "missing_items": List[str],
                "recommendations": List[str]
            }
        """

        verification_prompt = f"""당신은 VC 투자 분석 작업의 품질 검증자입니다.

Goal: {goal}

실행 결과:
{json.dumps(execution_result, ensure_ascii=False, indent=2, default=str)}

실행 로그:
{json.dumps(self.execution_log, ensure_ascii=False, indent=2, default=str)}

Goal이 성공적으로 달성되었는지 엄격하게 검증하세요.

평가 기준:
1. Goal에서 요구한 모든 항목이 완료되었는가?
2. 출력 파일이 올바르게 생성되었는가?
3. 데이터 품질이 충분한가?
4. 추가로 필요한 작업이 있는가?

출력 형식 (JSON):
{{
  "goal_achieved": true/false,
  "completeness": 0.0-1.0,
  "missing_items": ["항목1", "항목2"],
  "quality_issues": ["이슈1", "이슈2"],
  "recommendations": ["추천사항1", "추천사항2"]
}}

JSON만 출력하세요.
"""

        # Claude Agent SDK streaming query
        await self.client.query(verification_prompt)

        verification_text = ""
        async for message in self.client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        verification_text += block.text

        verification = self._parse_json_from_text(verification_text)

        return verification

    # ========================================
    # Autonomous Recovery
    # ========================================

    async def _autonomous_recovery(
        self,
        step_info: Dict[str, Any],
        error: Exception,
        context: Dict[str, Any],
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        실패한 단계를 자율적으로 복구 시도

        전략:
        1. 파라미터 조정하여 재시도
        2. 대안 Tool 사용
        3. 단계 건너뛰기 (non-critical인 경우)
        """

        if verbose:
            print(f"   🔧 Attempting autonomous recovery...")

        recovery_prompt = f"""작업 실패가 발생했습니다. 자율적으로 해결 방안을 찾으세요.

실패한 단계:
{json.dumps(step_info, ensure_ascii=False, indent=2)}

오류: {str(error)}

현재 컨텍스트:
{json.dumps(context, ensure_ascii=False, indent=2, default=str)}

Available Tools:
{json.dumps([tool["name"] for tool in self.tools], ensure_ascii=False)}

다음 중 최선의 전략을 선택하고 구체적인 해결 방안을 제시하세요:
1. **retry**: 파라미터를 조정하여 재시도
2. **alternative**: 대안 Tool 사용
3. **skip**: 단계 건너뛰기 (non-critical만)

출력 형식 (JSON):
{{
  "strategy": "retry|alternative|skip",
  "solution": "구체적인 해결 방안 설명",
  "new_params": {{"key": "value"}},  // retry인 경우
  "alternative_tool": "tool_name"     // alternative인 경우
}}

JSON만 출력하세요.
"""

        # Claude Agent SDK streaming query
        await self.client.query(recovery_prompt)

        recovery_text = ""
        async for message in self.client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        recovery_text += block.text

        recovery_plan = self._parse_json_from_text(recovery_text)

        # 복구 전략 실행
        if recovery_plan['strategy'] == 'retry':
            try:
                result = await self._execute_tool_with_retry(
                    tool_name=step_info['action'],
                    params=recovery_plan.get('new_params', {}),
                    max_retries=1
                )
                return {
                    "recovered": True,
                    "strategy": "retry",
                    "solution": recovery_plan['solution'],
                    "result": result
                }
            except:
                pass

        elif recovery_plan['strategy'] == 'alternative':
            try:
                alt_tool = recovery_plan.get('alternative_tool')
                result = await self._execute_tool_with_retry(
                    tool_name=alt_tool,
                    params=recovery_plan.get('new_params', {}),
                    max_retries=1
                )
                return {
                    "recovered": True,
                    "strategy": "alternative",
                    "solution": recovery_plan['solution'],
                    "result": result
                }
            except:
                pass

        elif recovery_plan['strategy'] == 'skip':
            if not step_info.get('critical', False):
                return {
                    "recovered": True,
                    "strategy": "skip",
                    "solution": recovery_plan['solution'],
                    "result": None
                }

        # 복구 실패
        return {
            "recovered": False,
            "strategy": recovery_plan['strategy'],
            "solution": "Recovery failed"
        }

    # ========================================
    # Helper Methods
    # ========================================

    async def _execute_tool_with_retry(
        self,
        tool_name: str,
        params: Dict[str, Any],
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Tool 실행 (재시도 포함)"""

        last_error = None

        for attempt in range(max_retries):
            try:
                result = execute_tool(tool_name, params)

                if result.get('success'):
                    return result
                else:
                    last_error = Exception(result.get('error', 'Unknown error'))

            except Exception as e:
                last_error = e
                await asyncio.sleep(1)  # 재시도 전 대기

        raise last_error

    def _resolve_params(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        파라미터에서 변수 참조를 컨텍스트 값으로 치환

        예: {"excel_path": "$analyze_excel.data.investment_terms.file"}
        → {"excel_path": "actual_file_path.xlsx"}
        """

        resolved = {}

        for key, value in params.items():
            if isinstance(value, str) and value.startswith('$'):
                # 컨텍스트에서 값 추출
                path = value[1:].split('.')
                current = context

                for part in path:
                    if isinstance(current, dict):
                        current = current.get(part)
                    else:
                        break

                resolved[key] = current if current is not None else value
            else:
                resolved[key] = value

        return resolved

    def _parse_json_from_text(self, text: str) -> Dict[str, Any]:
        """텍스트에서 JSON 추출"""

        # 코드 블록 제거
        text = text.strip()
        if text.startswith('```'):
            lines = text.split('\n')
            text = '\n'.join(lines[1:-1])

        # json 키워드 제거
        if text.startswith('json'):
            text = text[4:].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            # JSON 파싱 실패 시 간단한 복구 시도
            # 마지막 } 찾기
            last_brace = text.rfind('}')
            if last_brace != -1:
                text = text[:last_brace+1]
                return json.loads(text)
            raise e
