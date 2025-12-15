# True Agent vs Current Implementation

## 문제 인식: 현재는 "Agent"가 아니다

### 현재 구현 (Tool-using Chatbot)
```python
# agent.py 현재 구조
class ConversationalVCAgent:
    async def chat(self, user_message: str):
        # 사용자가 명령 → Claude가 도구 선택 → 실행
        response = await self.client.messages.create(
            messages=[{"role": "user", "content": user_message}],
            tools=self.tools  # Claude에게 도구 제공
        )
```

**문제:**
- ❌ 사용자가 **매번 명령**해야 함
- ❌ Claude는 **반응**만 함 (reactive)
- ❌ **자율적 계획 수립** 없음
- ❌ **Goal-oriented** 아님

---

## True Agent의 정의

### Agent의 4가지 핵심 특성

#### 1. **Autonomy (자율성)**
> "사용자 개입 없이 스스로 작업 완수"

```python
# ❌ 현재 (Chatbot)
user: "엑셀 분석해줘"
agent: (엑셀 분석)
user: "이제 IRR 계산해줘"
agent: (IRR 계산)
user: "엑셀로 만들어줘"
agent: (엑셀 생성)

# ✅ True Agent
user: "투자 분석 완료해줘"
agent: [계획]
       1. 엑셀 파일 찾기
       2. 데이터 추출
       3. 시나리오 분석
       4. IRR 계산
       5. 엑셀 생성
       6. 결과 리포트
       → 자동으로 모두 실행
```

#### 2. **Goal-Oriented (목표 지향)**
> "최종 목표를 설정하고 그것을 달성하기 위한 계획 수립"

```python
# ❌ 현재 (단계별 명령)
user: "calculate_valuation 실행해"
agent: (단순 실행)

# ✅ True Agent
Goal: "투자 의사결정 자료 생성"
SubGoals:
  1. 데이터 검증
  2. 다양한 시나리오 분석
  3. 리스크 분석
  4. 추천 전략
  5. 엑셀 + PDF 리포트
```

#### 3. **Reactive + Proactive (반응 + 능동)**
> "문제 발견 시 스스로 해결책 제안"

```python
# ❌ 현재 (에러 발생 시 중단)
agent: "파일을 찾을 수 없습니다"
→ 종료

# ✅ True Agent
agent: "파일을 찾을 수 없습니다"
      [자율 판단]
      1. 유사한 파일명 검색
      2. 사용자에게 확인 요청
      3. 대안 제시
      → 스스로 문제 해결 시도
```

#### 4. **Persistent (지속성)**
> "한 번의 명령으로 장기간 작업 수행"

```python
# ❌ 현재 (세션 종료 시 중단)
user: "분석해줘"
agent: (분석 중...)
→ 브라우저 닫으면 중단

# ✅ True Agent (Background Job)
user: "투자 분석 시작"
agent: "백그라운드에서 실행합니다"
       → Job ID: #1234
user: (나중에 돌아와서)
     "분석 #1234 상태는?"
agent: "80% 완료, 예상 10분 남음"
```

---

## Claude Agent SDK로 True Agent 만들기

### Anthropic의 Agent 프레임워크

#### Option 1: **Agent Loop Pattern** (권장)

```python
# true_agent.py
from anthropic import Anthropic
from typing import List, Dict, Any

class TrueVCInvestmentAgent:
    """자율적으로 계획하고 실행하는 True Agent"""

    def __init__(self):
        self.client = Anthropic()
        self.tools = register_tools()

    async def execute_goal(self, goal: str, context: Dict[str, Any] = None):
        """
        Goal을 받아 자율적으로 완수

        Args:
            goal: "투자 분석 완료", "Exit 프로젝션 생성" 등
            context: {"excel_file": "path/to/file.xlsx"}
        """

        # Phase 1: Planning
        plan = await self._create_plan(goal, context)

        # Phase 2: Execution (Agentic Loop)
        result = await self._execute_plan(plan)

        # Phase 3: Verification
        verified = await self._verify_result(result, goal)

        return verified

    async def _create_plan(self, goal: str, context: Dict[str, Any]) -> List[str]:
        """자율적으로 계획 수립"""

        planning_prompt = f"""
당신은 VC 투자 분석 에이전트입니다.

Goal: {goal}
Context: {context}

이 목표를 달성하기 위한 구체적인 실행 계획을 세우세요.

출력 형식:
{{
  "plan": [
    {{"step": 1, "action": "analyze_excel", "params": {{}}, "reason": "..."}},
    {{"step": 2, "action": "calculate_valuation", "params": {{}}, "reason": "..."}}
  ],
  "estimated_time": "5 minutes",
  "potential_issues": ["파일 형식 불일치", ...]
}}
"""

        response = await self.client.messages.create(
            model="claude-sonnet-4",
            messages=[{"role": "user", "content": planning_prompt}],
            max_tokens=2048
        )

        # JSON 파싱하여 계획 추출
        plan = self._parse_plan(response.content[0].text)

        print("📋 실행 계획:")
        for step in plan["plan"]:
            print(f"  {step['step']}. {step['action']} - {step['reason']}")

        return plan

    async def _execute_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """계획을 자율적으로 실행 (Agentic Loop)"""

        results = []
        context = {}

        for step in plan["plan"]:
            print(f"\n🔄 Step {step['step']}: {step['action']}")

            try:
                # 도구 실행
                result = await self._execute_tool_with_retry(
                    tool_name=step["action"],
                    params=step["params"],
                    context=context  # 이전 단계 결과 활용
                )

                # 성공 시 컨텍스트 업데이트
                context[step["action"]] = result
                results.append({
                    "step": step["step"],
                    "status": "success",
                    "result": result
                })

                print(f"  ✅ 성공")

            except Exception as e:
                # 실패 시 자율적 대응
                print(f"  ⚠️  오류: {e}")

                # Agent가 스스로 문제 해결 시도
                recovery = await self._autonomous_recovery(
                    failed_step=step,
                    error=e,
                    context=context
                )

                if recovery["success"]:
                    print(f"  ✅ 복구 성공: {recovery['solution']}")
                    context[step["action"]] = recovery["result"]
                else:
                    print(f"  ❌ 복구 실패")
                    # Goal을 달성할 수 없는 경우에만 중단
                    if step.get("critical", False):
                        raise
                    # 아니면 계속 진행 (선택적 단계)

        return {"steps": results, "context": context}

    async def _autonomous_recovery(
        self,
        failed_step: Dict[str, Any],
        error: Exception,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """실패 시 자율적으로 복구 시도"""

        recovery_prompt = f"""
작업 실패가 발생했습니다. 자율적으로 해결 방안을 찾으세요.

실패한 단계: {failed_step}
오류: {str(error)}
현재 컨텍스트: {context}

다음 중 하나를 선택하세요:
1. 파라미터를 조정하여 재시도
2. 대안 도구 사용
3. 사용자에게 추가 정보 요청
4. 해당 단계 건너뛰기 (가능한 경우)

출력 형식:
{{
  "strategy": "retry|alternative|ask_user|skip",
  "solution": "구체적인 해결 방안",
  "new_params": {{...}}
}}
"""

        response = await self.client.messages.create(
            model="claude-sonnet-4",
            messages=[{"role": "user", "content": recovery_prompt}],
            max_tokens=1024
        )

        recovery_plan = self._parse_json(response.content[0].text)

        # 자율적으로 복구 실행
        if recovery_plan["strategy"] == "retry":
            result = await self._execute_tool_with_retry(
                tool_name=failed_step["action"],
                params=recovery_plan["new_params"],
                context=context
            )
            return {"success": True, "result": result, "solution": recovery_plan["solution"]}

        elif recovery_plan["strategy"] == "alternative":
            # 대안 도구 실행
            alt_tool = recovery_plan.get("alternative_tool")
            result = await self._execute_tool_with_retry(
                tool_name=alt_tool,
                params=recovery_plan["new_params"],
                context=context
            )
            return {"success": True, "result": result, "solution": recovery_plan["solution"]}

        elif recovery_plan["strategy"] == "ask_user":
            # 사용자에게 질문 (동기화)
            user_response = input(f"Agent: {recovery_plan['question']}\nYou: ")
            # 사용자 응답으로 재시도
            return await self._autonomous_recovery(failed_step, error, context)

        else:  # skip
            return {"success": True, "result": None, "solution": "Step skipped"}

    async def _verify_result(self, result: Dict[str, Any], goal: str) -> Dict[str, Any]:
        """결과 검증 및 Goal 달성 여부 확인"""

        verification_prompt = f"""
Goal: {goal}
실행 결과: {result}

Goal이 성공적으로 달성되었는지 검증하세요.

출력 형식:
{{
  "goal_achieved": true/false,
  "completeness": 0.0-1.0,
  "missing_items": ["..."],
  "recommendations": ["..."]
}}
"""

        response = await self.client.messages.create(
            model="claude-sonnet-4",
            messages=[{"role": "user", "content": verification_prompt}],
            max_tokens=1024
        )

        verification = self._parse_json(response.content[0].text)

        if not verification["goal_achieved"]:
            print(f"\n⚠️  Goal 미달성 ({verification['completeness']*100}%)")
            print(f"누락 항목: {verification['missing_items']}")

            # 자율적으로 추가 작업 수행
            if verification["completeness"] > 0.7:
                print("추가 작업 실행 중...")
                # 누락 항목 자동 보완
                await self._fill_missing_items(verification["missing_items"], result)

        return verification


# === 사용 예시 ===

async def main():
    agent = TrueVCInvestmentAgent()

    # Goal만 제시 → Agent가 알아서 계획하고 실행
    result = await agent.execute_goal(
        goal="비사이드미 투자 분석 완료 및 Exit 프로젝션 엑셀 생성",
        context={
            "excel_file": "Valuation_비사이드미_202511.xlsx",
            "target_year": 2029,
            "scenarios": ["conservative", "base", "optimistic"]
        }
    )

    print("\n" + "="*60)
    print("✅ Goal 달성!")
    print(f"생성된 파일: {result['output_files']}")
    print(f"분석 결과: {result['summary']}")
```

---

#### Option 2: **Claude Swarm Pattern** (다중 Agent)

```python
# swarm_agent.py
from anthropic import Anthropic

class AgentSwarm:
    """여러 전문 Agent가 협업하여 복잡한 작업 수행"""

    def __init__(self):
        self.client = Anthropic()

        # 전문 에이전트들
        self.agents = {
            "planner": PlannerAgent(),      # 계획 수립
            "analyst": AnalystAgent(),       # 데이터 분석
            "calculator": CalculatorAgent(), # 계산 수행
            "reporter": ReporterAgent()      # 리포트 생성
        }

    async def execute_complex_task(self, task: str):
        """복잡한 작업을 여러 Agent가 협업하여 수행"""

        # 1. Planner가 작업 분해
        subtasks = await self.agents["planner"].decompose(task)

        # 2. 각 Agent에게 할당
        assignments = await self._assign_tasks(subtasks)

        # 3. 병렬 실행
        results = await asyncio.gather(*[
            self.agents[agent_name].execute(subtask)
            for agent_name, subtask in assignments
        ])

        # 4. Reporter가 통합
        final_report = await self.agents["reporter"].synthesize(results)

        return final_report


class PlannerAgent:
    """계획 수립 전문"""
    async def decompose(self, task: str) -> List[Dict]:
        # Claude에게 작업 분해 요청
        ...


class AnalystAgent:
    """데이터 분석 전문"""
    async def execute(self, subtask: Dict) -> Dict:
        # 엑셀 분석, 데이터 추출
        ...


class CalculatorAgent:
    """계산 전문"""
    async def execute(self, subtask: Dict) -> Dict:
        # IRR, 멀티플, NPV 계산
        ...


class ReporterAgent:
    """리포트 생성 전문"""
    async def synthesize(self, results: List[Dict]) -> str:
        # 여러 결과를 통합하여 최종 리포트
        ...
```

---

## 비교: Tool-using Chatbot vs True Agent

| 특성 | 현재 구현 (Chatbot) | True Agent |
|------|---------------------|------------|
| **명령 방식** | 단계별 명령 필요 | 최종 Goal만 제시 |
| **계획 수립** | ❌ 없음 | ✅ 자율적 계획 |
| **에러 처리** | ❌ 중단 | ✅ 자율 복구 |
| **Goal 검증** | ❌ 없음 | ✅ 자동 검증 + 보완 |
| **장기 작업** | ❌ 세션 종속 | ✅ 백그라운드 실행 |
| **사용자 개입** | 매 단계 | Goal 설정 시만 |

### 사용 비교

**Chatbot (현재):**
```
User: 엑셀 분석해줘
Bot: (분석 완료)
User: IRR 계산해줘
Bot: (계산 완료)
User: 엑셀 생성해줘
Bot: (생성 완료)
→ 3번 명령
```

**True Agent:**
```
User: 투자 분석 완료해줘
Agent: [계획] 엑셀 분석 → IRR 계산 → 엑셀 생성
       [실행] 1/3... 2/3... 3/3...
       ✅ 완료!
→ 1번 명령
```

---

## 구현 로드맵

### Phase 1: Agentic Loop 추가 (1주)
```python
# agent/autonomous_agent.py
class AutonomousVCAgent(ConversationalVCAgent):
    """자율적으로 계획하고 실행하는 Agent"""

    async def achieve_goal(self, goal: str, context: Dict = None):
        plan = await self._plan(goal, context)
        result = await self._execute_loop(plan)
        return result
```

### Phase 2: Planning & Verification (1주)
- Claude에게 계획 수립 요청
- 각 단계 실행 후 검증
- Goal 달성 여부 확인

### Phase 3: Autonomous Recovery (1주)
- 에러 발생 시 자율 복구
- 대안 탐색
- 사용자 최소 개입

### Phase 4: Background Execution (1주)
- 장기 작업 백그라운드 실행
- Job 상태 추적
- 완료 시 알림

---

## 결론

**현재:** Tool-using Chatbot
- Claude가 도구를 사용하는 대화 봇
- 사용자가 매번 명령

**True Agent:**
- Goal 제시 → Agent가 알아서 계획/실행/검증
- 자율적 문제 해결
- 장기 작업 가능

**추천:** Phase 1부터 단계적으로 True Agent로 진화

필요하시면 `AutonomousVCAgent` 클래스를 구현해드릴까요?
