# VC Investment Agent SDK - Claude Agent SDK 마이그레이션

> **중요**: 이 프로젝트는 Anthropic SDK에서 **Claude Agent SDK**로 마이그레이션되었습니다.

## Claude Agent SDK vs Anthropic SDK

| 항목 | Anthropic SDK | Claude Agent SDK |
|------|---------------|------------------|
| 목적 | 범용 API 클라이언트 | 에이전트 구축 전용 |
| 컨텍스트 관리 | 수동 (직접 메시지 배열 관리) | 자동 (세션 기반) |
| 도구 통합 | 수동 (직접 tool_choice 처리) | 자동 (MCP 지원) |
| 스트리밍 | `messages.stream()` | `query()` |
| 세션 지속성 | 없음 | 내장 |
| 에이전트 최적화 | 없음 | 프롬프트 캐싱, 컨텍스트 압축 |
| 프로덕션 기능 | 직접 구현 필요 | 에러 핸들링, 모니터링 내장 |

---

## 문제 인식

**Skill의 장점 (유연성)**
- "SAFE 전환은 빼고, 대신 Liquidation Preference 2x로 분석해줘"
- "부분 매각을 2029년 30%, 2030년 40%, 2031년 30%로 3단계로 나눠줘"
- "이번 분석은 PER 대신 EV/Revenue 멀티플로 해줘"

**Agent SDK의 위험 (경직성)**
```python
# ❌ 이렇게 되면 새로운 요구사항마다 코드 수정 필요
def generate_projection(
    investment_amount: float,
    projection_type: Literal["basic", "advanced", "complete"]  # 고정된 3가지만
):
    if projection_type == "basic":
        ...
    elif projection_type == "advanced":
        ...
```

---

## 해결책: Conversational Agent Architecture

### 핵심 아이디어
**구조화된 도구 + Claude의 자연어 이해력 = 무한한 유연성**

```python
# agent.py
from anthropic import Anthropic
from typing import Any, AsyncIterator

class ConversationalVCAgent:
    """자연어로 소통 가능한 VC 투자 분석 에이전트"""

    def __init__(self):
        self.client = Anthropic()
        # 기본 도구들 (building blocks)
        self.tools = self._register_tools()
        # 대화 히스토리
        self.conversation_history = []
        # 현재 작업 컨텍스트
        self.context = AgentContext()

    def _register_tools(self):
        """원자적(atomic) 도구들만 등록"""
        return [
            # 데이터 읽기
            {
                "name": "read_excel_sheet",
                "description": "엑셀 파일의 특정 시트 읽기",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string"},
                        "sheet_name": {"type": "string"},
                        "cell_range": {"type": "string", "description": "A1:Z100 형식"}
                    }
                }
            },

            # 계산 도구
            {
                "name": "calculate_valuation",
                "description": "기업가치 계산 (다양한 방법론 지원)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "enum": ["per", "ev_revenue", "ev_ebitda", "dcf"],
                            "description": "밸류에이션 방법론"
                        },
                        "base_value": {"type": "number", "description": "기준 값 (순이익, 매출 등)"},
                        "multiple": {"type": "number", "description": "적용할 배수"}
                    }
                }
            },

            # 희석 계산
            {
                "name": "calculate_dilution",
                "description": "지분 희석 효과 계산 (SAFE, 콜옵션, 신주발행 등)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dilution_event": {
                            "type": "object",
                            "description": "희석 이벤트 정보 (유연한 구조)"
                        },
                        "current_shares": {"type": "number"}
                    }
                }
            },

            # IRR 계산
            {
                "name": "calculate_irr",
                "description": "현금흐름 기반 IRR 계산",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "cash_flows": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "date": {"type": "string"},
                                    "amount": {"type": "number"}
                                }
                            }
                        }
                    }
                }
            },

            # 엑셀 생성
            {
                "name": "create_excel_output",
                "description": "분석 결과를 엑셀로 출력",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "sections": {
                            "type": "array",
                            "description": "출력할 섹션 리스트 (동적 구성)"
                        },
                        "styling": {"type": "object"}
                    }
                }
            }
        ]

    async def chat(self, user_message: str) -> AsyncIterator[str]:
        """자연어 대화 인터페이스"""

        # 대화 히스토리에 추가
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Claude에게 시스템 프롬프트와 함께 요청
        system_prompt = self._build_system_prompt()

        response = await self.client.messages.create(
            model="claude-sonnet-4",
            system=system_prompt,
            messages=self.conversation_history,
            tools=self.tools,
            max_tokens=4096,
            stream=True
        )

        # 스트리밍 응답 처리
        async for event in response:
            if event.type == "content_block_delta":
                yield event.delta.text

            elif event.type == "tool_use":
                # Claude가 도구 사용 요청
                tool_result = await self._execute_tool(
                    event.name,
                    event.input
                )

                # 결과를 대화에 추가
                self.conversation_history.append({
                    "role": "assistant",
                    "content": event.content
                })
                self.conversation_history.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": event.id,
                        "content": str(tool_result)
                    }]
                })

                # Claude가 다음 행동 결정하도록 재귀 호출
                async for chunk in self._continue_conversation():
                    yield chunk

    def _build_system_prompt(self) -> str:
        """동적 시스템 프롬프트 생성"""
        return f"""
당신은 VC 투자 분석 전문가입니다. 사용자의 요구사항을 이해하고 적절한 도구를 조합하여 분석을 수행합니다.

## 현재 컨텍스트
- 분석된 파일: {self.context.analyzed_files}
- 이전 계산 결과: {self.context.cached_results}

## 능력
1. **유연한 시나리오 분석**: 사용자가 요청한 어떤 조합의 시나리오도 분석 가능
   - 표준 시나리오: 전체 매각, 부분 매각, SAFE 전환, 콜옵션
   - 맞춤 시나리오: 사용자가 정의한 독특한 구조

2. **다양한 밸류에이션 방법론**
   - PER, EV/Revenue, EV/EBITDA, DCF 등 모든 방법론 지원
   - 혼합 방식도 가능 (예: 2029년은 PER, 2030년은 EV/Revenue)

3. **복잡한 희석 구조**
   - SAFE, 콜옵션, Liquidation Preference, 전환우선주 등
   - 다단계 투자 라운드 시뮬레이션

4. **맞춤형 Exit 시나리오**
   - 2단계, 3단계, N단계 매각
   - 조건부 Earnout 포함
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
"""

    async def _execute_tool(self, tool_name: str, tool_input: dict) -> Any:
        """도구 실행"""

        if tool_name == "read_excel_sheet":
            return await self._read_excel_sheet(**tool_input)

        elif tool_name == "calculate_valuation":
            return await self._calculate_valuation(**tool_input)

        elif tool_name == "calculate_dilution":
            return await self._calculate_dilution(**tool_input)

        elif tool_name == "calculate_irr":
            return await self._calculate_irr(**tool_input)

        elif tool_name == "create_excel_output":
            return await self._create_excel_output(**tool_input)

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    # === 도구 구현들 ===

    async def _calculate_valuation(
        self,
        method: str,
        base_value: float,
        multiple: float
    ) -> dict:
        """유연한 밸류에이션 계산"""

        if method == "per":
            enterprise_value = base_value * multiple
        elif method == "ev_revenue":
            enterprise_value = base_value * multiple
        elif method == "ev_ebitda":
            enterprise_value = base_value * multiple
        elif method == "dcf":
            # DCF 계산 로직
            enterprise_value = self._dcf_calculation(base_value, multiple)
        else:
            raise ValueError(f"Unsupported valuation method: {method}")

        return {
            "method": method,
            "enterprise_value": enterprise_value,
            "base_value": base_value,
            "multiple": multiple
        }

    async def _calculate_dilution(
        self,
        dilution_event: dict,
        current_shares: float
    ) -> dict:
        """동적 희석 계산"""

        event_type = dilution_event.get("type")

        if event_type == "safe":
            # SAFE 전환 로직
            safe_amount = dilution_event["amount"]
            valuation_cap = dilution_event["valuation_cap"]
            new_shares = (safe_amount / valuation_cap) * current_shares

        elif event_type == "call_option":
            # 콜옵션 로직
            new_shares = 0  # 희석 없음 (주식 매입)

        elif event_type == "new_round":
            # 신규 투자 라운드
            investment = dilution_event["amount"]
            pre_money = dilution_event["pre_money_valuation"]
            new_shares = (investment / pre_money) * current_shares

        elif event_type == "custom":
            # 사용자 정의 희석
            # Claude가 자연어로 설명한 구조를 Python으로 계산
            new_shares = self._calculate_custom_dilution(dilution_event["formula"])

        total_shares = current_shares + new_shares
        dilution_ratio = new_shares / total_shares

        return {
            "new_shares": new_shares,
            "total_shares": total_shares,
            "dilution_ratio": dilution_ratio
        }

    async def _calculate_irr(self, cash_flows: list) -> dict:
        """시간 기반 IRR 계산 (복잡한 현금흐름 지원)"""

        import numpy as np
        from scipy.optimize import newton

        # 날짜를 연도로 변환
        dates = [cf["date"] for cf in cash_flows]
        amounts = [cf["amount"] for cf in cash_flows]

        # XIRR 계산 (Excel의 XIRR 함수와 동일)
        def xnpv(rate, cash_flows):
            t0 = cash_flows[0]["date"]
            return sum([
                cf["amount"] / (1 + rate) ** ((cf["date"] - t0).days / 365.0)
                for cf in cash_flows
            ])

        irr = newton(lambda r: xnpv(r, cash_flows), 0.1)

        return {
            "irr": irr,
            "cash_flows": cash_flows,
            "multiple": sum(amounts[1:]) / abs(amounts[0])
        }

    async def _create_excel_output(self, sections: list, styling: dict) -> str:
        """동적 엑셀 생성 (사용자 요청에 맞춘 구조)"""

        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active

        row = 1
        for section in sections:
            if section["type"] == "scenario_table":
                # 시나리오 테이블 추가
                row = self._add_scenario_table(ws, row, section["data"])

            elif section["type"] == "comparison_chart":
                # 비교 차트 추가
                row = self._add_comparison_chart(ws, row, section["data"])

            elif section["type"] == "sensitivity_analysis":
                # 민감도 분석 추가
                row = self._add_sensitivity_table(ws, row, section["data"])

            elif section["type"] == "custom":
                # 사용자 정의 섹션
                row = self._add_custom_section(ws, row, section["data"])

            row += 2  # 섹션 간격

        output_path = f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        wb.save(output_path)

        return output_path


class AgentContext:
    """에이전트 작업 컨텍스트"""

    def __init__(self):
        self.analyzed_files = []
        self.cached_results = {}
        self.user_preferences = {}

    def remember(self, key: str, value: Any):
        """정보 기억"""
        self.cached_results[key] = value

    def recall(self, key: str) -> Any:
        """정보 회상"""
        return self.cached_results.get(key)
```

---

## 사용 예시: 자연어 유연성

### 예시 1: 복잡한 맞춤 시나리오

```python
agent = ConversationalVCAgent()

# 사용자 요청
user_request = """
비사이드미 투자 분석을 해주세요. 특이한 조건이 있습니다:

1. 2028년에 전략적 투자자가 30% 지분을 인수 (PER 12 기준)
2. 2029년에 SAFE 1억원이 밸류캡 50억으로 전환
3. 2030년에 IPO로 나머지 전량 매각 (EV/Revenue 5배 기준)
4. 단, Liquidation Preference 2x가 있어서 우선 회수 후 잔여 분배

이 구조로 IRR과 멀티플을 계산해주세요.
"""

async for response in agent.chat(user_request):
    print(response, end="")
```

**Agent의 내부 동작:**

```
[Claude의 사고 과정]
1. 이건 기존 "basic/advanced/complete" 중 어느 것도 아님
2. 3단계 Exit + SAFE 전환 + Liquidation Preference 조합
3. 2028년: PER 밸류에이션 → 30% 매각
4. 2029년: SAFE 희석 효과 반영
5. 2030년: Revenue 기준 밸류에이션 → IPO
6. Liquidation Preference 계산 필요

[도구 호출 순서]
→ read_excel_sheet("비사이드미.xlsx", "IS요약")
→ calculate_valuation(method="per", base_value=순이익_2028, multiple=12)
→ calculate_dilution(type="safe", amount=100000000, valuation_cap=5000000000)
→ calculate_valuation(method="ev_revenue", base_value=매출_2030, multiple=5)
→ calculate_irr(cash_flows=[
    {date: "2025-01-01", amount: -300000000},  # 투자
    {date: "2028-12-31", amount: 1차_회수액},   # 30% 매각
    {date: "2030-12-31", amount: 2차_회수액}    # IPO
])
→ create_excel_output(sections=[
    {type: "custom", title: "3단계 Exit 시나리오"},
    {type: "scenario_table", ...},
    {type: "dilution_analysis", ...}
])
```

**결과:**
```
분석을 완료했습니다.

## 시나리오 요약
- 2028년 1차 Exit (30%): 8.4억 회수
- 2029년 SAFE 전환: 지분 5.2% 희석
- 2030년 IPO (70%): 23.1억 회수
- **총 회수액: 31.5억원**
- **멀티플: 10.5x**
- **IRR: 61.2%**

Liquidation Preference 2x 적용 결과:
- 우선 회수: 6억원
- 잔여 분배: 25.5억원
- 실제 수령액: 31.5억원 (차이 없음 - 기업가치 충분)

상세 분석을 엑셀로 생성했습니다: output_20250115_143022.xlsx
```

---

### 예시 2: 대화형 수정

```python
# 후속 질문
user: "2028년 매각을 50%로 늘리면 어떻게 돼?"

# Agent는 이전 컨텍스트를 기억하고 재계산
agent: """
2028년 매각 비율을 50%로 조정하여 재계산했습니다.

변경 사항:
- 1차 회수액: 8.4억 → 14.0억 (+5.6억)
- 2차 회수액: 23.1억 → 16.5억 (-6.6억)
- **총 회수액: 30.5억원** (기존 31.5억 대비 -1.0억)
- **IRR: 59.8%** (기존 61.2% 대비 -1.4%p)

분석: 조기 회수 비중이 높아져 IRR이 소폭 하락했습니다.
추천: 2028년 30%, 2030년 70% 유지가 유리합니다.
"""
```

---

### 예시 3: 새로운 방법론 요청

```python
user: "DCF로도 한번 계산해줘. WACC는 12% 적용"

agent: """
DCF 방식으로 재분석했습니다.

가정:
- WACC: 12%
- 영구성장률: 3%
- FCF 기반 밸류에이션

결과:
- 기업가치 (DCF): 127억원
- 기업가치 (PER 12x): 134억원
- **차이: -5.2%**

DCF 기준 Exit 분석:
- 멀티플: 9.8x (기존 10.5x 대비 -0.7x)
- IRR: 57.3% (기존 61.2% 대비 -3.9%p)

두 방법론 비교 차트를 추가했습니다.
"""
```

---

## 핵심 설계 원칙

### 1. **원자적 도구 (Atomic Tools)**
```python
# ❌ 나쁜 예: 고정된 워크플로우
def generate_complete_projection(params):
    # SAFE + 콜옵션 + 부분매각 + NPV를 무조건 다 계산
    pass

# ✅ 좋은 예: 조합 가능한 원자 도구
calculate_valuation(method="per", ...)
calculate_dilution(type="safe", ...)
calculate_irr(cash_flows=[...])
```

### 2. **Claude가 오케스트레이터**
```
사용자 요청 → Claude가 이해 → 적절한 도구 조합 → 결과 생성
```

### 3. **컨텍스트 유지**
```python
# 이전 분석 결과를 메모리에 저장
agent.context.remember("last_analysis", {
    "company": "비사이드미",
    "valuation": 134억,
    "irr": 61.2%
})

# 다음 요청 시 재사용
"아까 분석한 회사 PER을 15로 바꿔줘"
→ Claude가 "비사이드미"를 기억하고 재계산
```

### 4. **확장 가능**
```python
# 새로운 도구 추가 = 새로운 기능
agent.register_tool({
    "name": "calculate_earnout",
    "description": "조건부 성과급 (Earnout) 계산",
    "input_schema": {...}
})

# 즉시 사용 가능
user: "Earnout 조건으로 매출 100억 달성 시 추가 지급 조건 추가해줘"
→ Claude가 자동으로 새 도구 활용
```

---

## 배포 시나리오

### 1. **CLI (개발자용)**
```bash
$ vc-agent chat
> 비사이드미 투자 분석해줘
> SAFE 전환은 제외하고...
```

### 2. **웹 인터페이스 (비개발자용)**
```
[채팅창]
사용자: 엑셀 파일 업로드 (drag & drop)
Agent: 분석을 시작합니다. 어떤 시나리오를 원하시나요?
사용자: 2단계 Exit으로, 2029년 40%, 2030년 60%
Agent: [진행률 표시] 계산 중...
Agent: [결과 표시 + 엑셀 다운로드 버튼]
```

### 3. **API (통합용)**
```python
# 다른 시스템에서 호출
import requests

response = requests.post("https://api.vc-agent.com/analyze", json={
    "conversation": [
        {"role": "user", "content": "투자 분석해줘"},
        {"role": "assistant", "content": "파일을 업로드해주세요"},
        {"role": "user", "content": "업로드 완료. SAFE + 3단계 Exit"}
    ]
})
```

---

## 결론

### Skill vs Conversational Agent 비교

| 항목 | Skill (현재) | Conversational Agent |
|------|-------------|---------------------|
| 자연어 유연성 | ✅ 매우 높음 | ✅ 매우 높음 (유지) |
| 독립 실행 | ❌ Claude Code 필요 | ✅ 어디서나 실행 |
| 컨텍스트 유지 | ❌ 세션 한정 | ✅ 영구 메모리 |
| 새 시나리오 | ✅ 즉시 가능 | ✅ 즉시 가능 (더 강력) |
| 배포 | ❌ 로컬 전용 | ✅ 웹/API/CLI |
| 에러 복구 | ❌ 수동 | ✅ 자동 |
| 학습 | ❌ 불가 | ✅ 대화 기록 학습 |

**결론: Conversational Agent는 Skill의 유연성을 유지하면서 독립성과 확장성을 더합니다.**

이 방식이라면 "Liquidation Preference 3x + Participating Preferred + Full Ratchet"같은
이전에 본 적 없는 복잡한 구조도 자연어로 요청하면 Claude가 도구를 조합해서 분석할 수 있습니다.
