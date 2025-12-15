# Production-Grade AI 에이전트 구축기: VC 투자 분석 자동화

투자심사 한 건당 4~6시간이 걸리던 Exit 프로젝션 분석을 30초로 줄인 이야기입니다.

---

## 문제: 반복되는 투자 분석 업무

VC 투자심사 현장에서 매번 반복되는 일들:
- 투자검토 엑셀 파일 파싱 (투자조건, IS요약, Cap Table)
- 2028년/2030년, PER 10배/20배/30배 등 수십 가지 시나리오 계산
- 투자위원회용 전문 엑셀 생성 (색상 코딩, 수식 포함)
- 가정 변경 시 모든 계산 다시 수행

**결과**: 한 건당 평균 4~6시간 소요, 급한 딜은 품질 저하

---

## 해결: AI 에이전트 '메리'

"엑셀 파일만 주면 자동으로 Exit 프로젝션을 만들어주는 AI"

### 핵심 성과
- ⏱️ 분석 시간: **2시간 → 30초** (240배 단축)
- 📊 엑셀 파싱 성공률: **60% → 95%** (다양한 포맷 처리)
- 💬 멀티턴 대화 정확도: **92%** (후속 질문 이해)
- ⚡ 평균 응답 지연: **8.5초** (실시간 스트리밍)

### 사용 예시
```
사용자: "temp/검토.xlsx를 2030년 PER 10,20,30배로 분석해줘"
메리: [파일 읽기 → 정보 추출 → Exit 프로젝션 생성]
     "exit_projection.xlsx 파일이 생성되었습니다"
     "2030년 IRR: 10배 23.5%, 15배 31.2%, 20배 37.8%"
```

---

## 기술적 도전 과제 5가지

### 1. Stateful Multi-turn Conversation

**문제**: Claude API는 stateless → 매번 전체 대화 이력을 전달해야 함

**해결**:
```python
class ChatMemory:
    """파일 기반 세션 관리"""
    def __init__(self):
        self.session_id = f"{사용자}_{기업}_{timestamp}"
        self.session_metadata = {
            "messages": [],
            "analyzed_files": [],
            "generated_files": []
        }

    def get_conversation_history(self, last_n=10):
        """최근 10개 턴만 전달 (200K → 20K 압축)"""
        # 도구 실행 결과는 요약하여 토큰 절약
```

**결과**:
```
[Turn 1] "검토.xlsx 분석해줘" → 분석 완료
[Turn 2] "그럼 2030년으로 바꿔줘" → 이전 맥락 유지 ✅
```

---

### 2. Async Streaming + Tool Use

**문제**: 동기 API는 30초 동안 빈 화면 → 사용자 경험 최악

**해결**: AsyncAnthropic + Server-Sent Events
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

**사용자 경험**:
```
[0초] 사용자 입력
[0.5초] "분석을 시작하겠습니다" ← 즉시 응답
[1초] **도구: read_excel_as_text**
[3초] **완료**
[3.5초] "투자금액은 3억원이며..." ← 스트리밍
```

---

### 3. Tool Use 신뢰성 확보

**문제**: LLM이 때때로 도구를 호출하지 않고 추측으로 답변
```python
# ❌ 잘못된 동작
User: "temp/검토.xlsx 분석해줘"
Claude: "투자금액은 약 3억원으로 추정되며..." (추측!)
```

**해결**: 강력한 시스템 프롬프트
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
```

**도구 스키마 엄격 정의**:
```python
{
    "name": "read_excel_as_text",
    "description": """⚠️ 중요: 이 도구 없이 엑셀 내용을 추측하지 마세요

    이 도구를 사용해야 하는 경우:
    - 사용자가 엑셀 파일 경로를 제공했을 때 (필수)
    - analyze_and_generate_projection 전에 반드시 먼저 호출
    """,
    "input_schema": {...}
}
```

---

### 4. Observability with Langfuse

**문제**: "왜 이 답변이 나왔는지?" 파악 불가

**해결**: Langfuse Distributed Tracing
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

**대시보드에서 확인**:
```
[Trace ID: abc123] "검토.xlsx 분석해줘"
├─ [LLM Call #1] 2.3s, $0.015, "read_excel_as_text 선택"
├─ [tool:read_excel_as_text] 1.2s, ✅ Success
├─ [LLM Call #2] 1.8s, "analyze_and_generate_projection 선택"
├─ [tool:analyze_and_generate_projection] 3.5s, ✅ Success
└─ [LLM Call #3] 1.5s, "최종 답변 생성"

Total: 10.3s, $0.042
```

**실전 디버깅**:
```python
# 문제: IRR이 35%가 아닌 28%로 나옴
trace = langfuse.get_trace("abc123")
# → 발견: 당기순이익이 28억이 아닌 20억으로 파싱됨
# → 엑셀 "억원" 단위 파싱 오류 수정
```

---

### 5. 유연한 엑셀 파싱

**문제**: 투자검토 엑셀은 회사마다 다름
- 고정 셀 위치 (`B5`, `D10`) 가정 → 포맷 변경 시 실패
- 시트명 다양: "투자조건", "투자조건체크리스트", "Investment Terms"

**해결**: LLM 기반 유연 파싱
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

**출력 예시**:
```
=== 투자조건 ===
투자유형	코너스톤
투자금액	300,000,000원
투자단가	32,808원
투자주식수	9,145주

=== IS요약 ===
		2023	2024	2025E	2028E	2030E
매출액	2,500	3,200	4,100	8,900	15,000
당기순이익	120	250	380	1,120	2,000
```

**Claude Opus 4.5가 자동 파싱**:
```python
# 시트명/위치가 달라도 정보 추출 성공
{
  "투자금액": 300000000,
  "투자단가": 32808,
  "당기순이익_2030": 2000000000
}
```

---

## 강화학습 기반 지속적 개선

### 피드백 수집
- 👍/👎/💬 버튼으로 실시간 피드백
- JSONL + SQLite 이중 저장
- Reward 점수: -1.0 ~ 1.0

### 패턴 분석
```python
# 매주 금요일 자동 분석
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

### 개선 사이클
```
1주차: 피드백 20개 → 만족도 70%
   ↓ 패턴 분석
2주차: 프롬프트 개선 → 만족도 85% 상승
   ↓ 도구 최적화
3주차: 만족도 90% 달성 🎯
```

---

## 핵심 교훈

### 1. "LLM을 믿고 위임하라"
- ❌ Before: 개발자가 모든 흐름을 if-else로 제어
- ✅ After: LLM에게 도구를 주고 ReAct로 자율 판단

### 2. "Async는 선택이 아닌 필수"
- 동기 API: 30초 대기 (사용자 이탈)
- 비동기 스트리밍: 8초가 800ms처럼 느껴짐

### 3. "관찰성 없이는 개선 불가"
- Langfuse 없이는 디버깅 불가능
- 모든 LLM 호출 + 도구 실행 추적 필수

### 4. "강화학습은 장기 투자"
- 초기: 데이터 수집에만 집중
- 3개월 후: 만족도 70% → 90% 상승

---

## 기술 스택

**Core**
- Claude Opus 4.5 (Anthropic API)
- AsyncAnthropic (비동기 스트리밍)
- Python 3.12 + asyncio

**Agent Framework**
- Anthropic Tool Use (function calling)
- ChatMemory (파일 기반 세션 관리)
- ReAct (Reasoning + Acting)

**Observability**
- Langfuse (Distributed Tracing)
- SQLite (피드백 DB)
- pandas (RL 패턴 분석)

**Interface**
- Streamlit (웹 UI)
- Space Grotesk 폰트, 빨간색 액센트

---

## 다음 단계

**Q1 2025: Agent Ecosystem**
- 셀프 서비스로 각 팀이 자체 분석 도구 구축
- PER 분석, DCF 모델링 등 전문 에이전트 추가

**Q2 2025: Analytics Assistant**
- 시장 데이터 연동 (상장사 PER, 산업 평균)
- 유사 거래(Comparable Transaction) 자동 검색

**Q3 2025: 글로벌 확장**
- 다국어 지원 (영어 투자검토 자료)
- 해외 VC 펀드와 지식 공유

---

## 마무리

단순한 RAG 시스템에서 출발해:
- ✅ 멀티턴 대화 (ChatMemory + 세션 관리)
- ✅ 비동기 스트리밍 (AsyncAnthropic + SSE)
- ✅ Tool Use 신뢰성 (강력한 프롬프트 + 검증)
- ✅ 관찰성 (Langfuse Tracing)
- ✅ 강화학습 (피드백 수집 → 패턴 분석 → 개선)

까지 진화했습니다.

**Anthropic 개발자의 조언**: "LLM이 가진 가능성은 여러분이 생각하는 것보다 훨씬 큽니다. LLM에게 믿고 위임하세요."

이 한 문장이 모든 것을 바꿨습니다.

---

**작성**: AX솔루션팀
**문의**: mwbyun1220@mysc.co.kr
**GitHub**: [링크 추가 예정]

---

#AI #LLM #Claude #Anthropic #VentureCapital #ProductionAI #AgenticAI #AsyncProgramming #ReinforcementLearning #Observability #Langfuse #Python #Streamlit #TechBlog
