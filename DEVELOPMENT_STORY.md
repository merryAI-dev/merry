# Claude SDK 기반 첫 Production AI 에이전트 구축기

투자심사 한 건당 4~6시간이 걸리던 Exit 프로젝션 분석을 30초로 줄인 이야기입니다. Claude Agent SDK를 활용해 구축한 국내 첫 Production-Grade VC 투자 분석 에이전트 '메리'의 개발 여정을 공유합니다.

---

## Impact Metrics

개발 6주 만에 달성한 성과입니다:

⏱️ **분석 시간: 2시간 → 30초 (240배 단축)**
투자 검토 엑셀 파싱부터 Exit 프로젝션 생성까지 완전 자동화

📊 **엑셀 파싱 성공률: 60% → 95%**
회사마다 다른 포맷도 Claude Opus 4.5가 자동 인식

💬 **멀티턴 대화 정확도: 92%**
"그럼 2030년으로 바꿔줘" 같은 후속 질문도 문맥 유지

⚡ **평균 응답 지연: 8.5초**
AsyncAnthropic 스트리밍으로 실시간 피드백

---

## 왜 Claude SDK였나

기존 LangChain/LlamaIndex는 추상화 레이어가 너무 두꺼웠습니다. Anthropic의 Tool Use API를 직접 쓰면서도 Production 수준의 에이전트를 만들고 싶었고, Claude Agent SDK가 딱 맞았습니다.

**Claude SDK의 장점:**
- Native Anthropic API 활용 (Tool Use, Streaming, Extended Thinking)
- 가벼운 추상화 (400 LoC vs LangChain 10K+ LoC)
- AsyncAnthropic 완벽 지원
- Pythonic 인터페이스 (decorators, async/await)

---

## Technical Challenge #1: Stateful Multi-turn Conversation

Claude API는 stateless입니다. 매 요청마다 전체 대화 이력을 전달해야 하죠. 하지만 200K 토큰 컨텍스트를 매번 보내면 비용이 폭발합니다.

**해결책: ChatMemory 구현**

파일 기반 세션 관리로 대화 상태를 유지하면서 토큰은 압축했습니다. 세션 ID는 `{사용자}_{기업}_{timestamp}` 형식으로 생성해 나중에 대화를 쉽게 찾을 수 있게 했습니다.

```python
class ChatMemory:
    def get_conversation_history(self, last_n=10):
        """최근 10개 턴만 전달 (200K → 20K 압축)"""
        messages = self.session_metadata["messages"][-last_n:]
        # 도구 실행 결과는 요약하여 토큰 절약
        return [self._compress_tool_results(m) for m in messages]
```

**결과:**
"검토.xlsx 분석해줘" → "그럼 2030년으로 바꿔줘"
두 번째 질문에서 이전 맥락이 완벽하게 유지됩니다.

---

## Technical Challenge #2: Async Streaming + Tool Use

동기 API로 30초 대기는 사용자 경험 최악입니다. AsyncAnthropic으로 실시간 스트리밍을 구현했지만, Tool Use와 함께 쓰기가 까다로웠습니다.

**해결책: AsyncIterator 패턴**

```python
async def chat(self, user_message: str) -> AsyncIterator[str]:
    async with self.async_client.messages.stream(...) as stream:
        async for event in stream:
            if event.type == "content_block_delta":
                yield event.delta.text  # 실시간 스트리밍

            elif event.type == "content_block_stop":
                # 도구 호출 감지 → 실행 → 결과 반환
                for block in message.content:
                    if block.type == "tool_use":
                        result = execute_tool(block.name, block.input)
                        yield f"\n\n**도구: {block.name}** 완료\n"
```

**사용자 경험:**
- [0초] 사용자 입력
- [0.5초] "분석을 시작하겠습니다" ← 즉시 응답
- [1초] **도구: read_excel_as_text**
- [3초] **완료**
- [3.5초] "투자금액은 3억원이며..." ← 스트리밍

30초가 아닌 8.5초로 느껴지는 이유는 0.5초 만에 첫 응답이 오기 때문입니다.

---

## Technical Challenge #3: Tool Use 신뢰성 확보

가장 큰 문제였습니다. Claude가 때때로 도구를 호출하지 않고 추측으로 답변했습니다.

**문제 상황:**
```
User: "temp/검토.xlsx 분석해줘"
Claude: "투자금액은 약 3억원으로 추정되며..." (추측!)
```

**해결책: 강력한 시스템 프롬프트 + 도구 스키마**

시스템 프롬프트에서 절대 규칙을 명시하고, 도구 스키마에 "언제 사용해야 하는지" 명확히 기술했습니다.

```python
system_prompt = """
⚠️ 절대 규칙:
- 엑셀 파일 분석 → 반드시 read_excel_as_text 사용
- Exit 프로젝션 생성 → 반드시 analyze_and_generate_projection 사용
- 추측하거나 예시 답변 절대 금지

작업 방식:
1. 즉시 read_excel_as_text 도구 호출 (구조 파악)
2. 텍스트에서 필요한 정보 추출
3. 즉시 analyze_and_generate_projection 도구 호출
4. 결과 설명
"""

tools = [{
    "name": "read_excel_as_text",
    "description": """⚠️ 중요: 이 도구 없이 엑셀 내용을 추측하지 마세요

    이 도구를 사용해야 하는 경우:
    - 사용자가 엑셀 파일 경로를 제공했을 때 (필수)
    - analyze_and_generate_projection 전에 반드시 먼저 호출
    """,
    "input_schema": {...}
}]
```

**결과:** Tool Use 정확도 65% → 98%

---

## Technical Challenge #4: Observability with Langfuse

"왜 이 답변이 나왔는지?" 파악할 수 없으면 개선도 불가능합니다. Langfuse Distributed Tracing으로 LLM 호출과 도구 실행을 추적했습니다.

```python
from langfuse.decorators import observe

@observe()
async def chat(self, user_message: str):
    langfuse_context.update_current_trace(
        name="vc_analysis",
        user_id=self.memory.session_metadata["user_info"]["nickname"]
    )

    # 도구 호출 추적
    with langfuse_context.observe_span(name=f"tool:{tool_name}") as span:
        result = execute_tool(tool_name, tool_input)
        span.update(output=result, metadata={"success": True})
```

**Langfuse 대시보드:**
```
[Trace ID: abc123] "검토.xlsx 분석해줘"
├─ [LLM Call #1] 2.3s, $0.015, "read_excel_as_text 선택"
├─ [tool:read_excel_as_text] 1.2s, ✅ Success
├─ [LLM Call #2] 1.8s, "analyze_and_generate_projection 선택"
├─ [tool:analyze_and_generate_projection] 3.5s, ✅ Success
└─ [LLM Call #3] 1.5s, "최종 답변 생성"

Total: 10.3s, $0.042
```

**실전 디버깅 사례:**
"IRR이 35%가 아닌 28%로 나오는 버그" → Trace에서 당기순이익이 20억으로 파싱된 걸 발견 → 엑셀 "억원" 단위 파싱 오류 수정

---

## Technical Challenge #5: 유연한 엑셀 파싱

투자검토 엑셀은 회사마다 포맷이 다릅니다. 고정 셀 위치(`B5`, `D10`)로 파싱하면 포맷이 조금만 바뀌어도 실패합니다.

**해결책: LLM 기반 유연 파싱**

엑셀을 탭으로 구분된 텍스트로 변환한 뒤 Claude Opus 4.5가 직접 파싱하게 했습니다.

```python
def read_excel_as_text(excel_path: str) -> str:
    """엑셀을 텍스트로 변환 → LLM이 직접 파싱"""
    workbook = openpyxl.load_workbook(excel_path, data_only=True)

    result = []
    for sheet_name in workbook.sheetnames:
        result.append(f"=== {sheet_name} ===")
        for row in sheet.iter_rows(values_only=True):
            row_text = "\t".join([str(cell) for cell in row])
            result.append(row_text)

    return "\n".join(result)
```

**출력 예시:**
```
=== 투자조건 ===
투자유형	코너스톤
투자금액	300,000,000원
투자단가	32,808원

=== IS요약 ===
		2023	2024	2030E
매출액	2,500	3,200	15,000
당기순이익	120	250	2,000
```

Claude Opus 4.5가 시트명이 "투자조건체크리스트"든 "Investment Terms"든 상관없이 필요한 정보를 추출합니다.

**결과:** 파싱 성공률 60% → 95%

---

## 강화학습 기반 지속적 개선

Streamlit UI에 👍/👎/💬 피드백 버튼을 달았습니다. JSONL + SQLite 이중 저장으로 데이터 손실을 방지하고, Reward 점수를 -1.0 ~ 1.0으로 정규화했습니다.

**패턴 분석 (매주 금요일):**
```python
db = FeedbackDatabase()

# 개선 필요 패턴
low_patterns = db.get_low_performing_patterns()
# → "이 파일 분석해줘" (평균 보상 -0.8)
# → 원인: 파일 경로 모호함
# → 시스템 프롬프트에 "파일명 명확히 확인" 추가

# 우수 패턴
high_patterns = db.get_high_performing_patterns()
# → "2030년 PER 10,20,30배로 분석해줘" (평균 보상 1.0)
# → 도구 조합: read_excel_as_text → analyze_and_generate_projection
```

**개선 사이클:**
1주차: 피드백 20개 → 만족도 70%
2주차: 프롬프트 개선 → 만족도 85% 상승
3주차: 만족도 90% 달성

---

## 핵심 교훈

**1. "LLM을 믿고 위임하라"**
개발자가 모든 흐름을 if-else로 제어하려 하지 마세요. LLM에게 도구를 주고 ReAct 패턴으로 자율 판단하게 하면 훨씬 유연합니다.

**2. "Async는 선택이 아닌 필수"**
동기 API로 30초 대기는 사용자 이탈로 이어집니다. 비동기 스트리밍으로 8초가 800ms처럼 느껴지게 만드세요.

**3. "관찰성 없이는 개선 불가"**
Langfuse 없이는 "왜 이 답변이 나왔는지" 디버깅이 불가능합니다. 모든 LLM 호출과 도구 실행을 추적하세요.

**4. "강화학습은 장기 투자"**
초기 3주는 데이터 수집에만 집중했습니다. 3개월 후 만족도가 70%에서 90%로 상승했습니다.

---

## 기술 스택

**Core:**
- Claude Opus 4.5 (Anthropic API)
- Claude Agent SDK (Python)
- AsyncAnthropic (비동기 스트리밍)
- Python 3.12 + asyncio

**Agent Framework:**
- Anthropic Tool Use (function calling)
- ChatMemory (파일 기반 세션 관리)
- ReAct (Reasoning + Acting)

**Observability:**
- Langfuse (Distributed Tracing)
- SQLite (피드백 DB)
- pandas (RL 패턴 분석)

**Interface:**
- Streamlit (웹 UI)
- Space Grotesk 폰트, 빨간색 액센트

---

## 마무리: Anthropic 개발자의 조언

단순한 RAG 시스템에서 출발해 멀티턴 대화, 비동기 스트리밍, Tool Use 신뢰성, 관찰성, 강화학습까지 갖춘 Production-Grade 에이전트로 진화했습니다.

**Anthropic 개발자의 조언:**
"LLM이 가진 가능성은 여러분이 생각하는 것보다 훨씬 큽니다. LLM에게 믿고 위임하세요."

이 한 문장이 모든 것을 바꿨습니다. Claude SDK를 활용해 6주 만에 국내 첫 Production AI 에이전트를 만들 수 있었던 비결입니다.

---

**작성:** AX솔루션팀
**문의:** mwbyun1220@mysc.co.kr
**GitHub:** https://github.com/merryAI-dev/merry

---

#ClaudeSDK #ProductionAI #AgenticAI #ClaudeOpus #Anthropic #VentureCapital #AsyncProgramming #ReinforcementLearning #Langfuse #Observability #Python #Streamlit #AIAgent #LLM #TechBlog
