# 🤖 True Agent Quick Start

## What is True Agent?

**Before (Chatbot):**
```
You: 엑셀 분석해줘
Bot: (분석 완료)
You: IRR 계산해줘
Bot: (계산 완료)
You: 엑셀 만들어줘
Bot: (생성 완료)
```
→ 3번 명령 필요

**After (True Agent):**
```
You: 투자 분석 완료해줘
Agent: [자동 계획] 엑셀 분석 → IRR 계산 → 엑셀 생성
       [자동 실행] ███████████████ 100%
       ✅ 완료!
```
→ 1번 명령으로 끝

---

## 🚀 즉시 사용법

### 1. Goal 기반 자율 실행

```bash
python cli.py goal "투자 분석 완료" -f "Valuation_비사이드미_202511.xlsx"
```

**실행 과정:**
```
🎯 Goal: 투자 분석 완료

📋 Phase 1: Planning...
계획 수립 완료 (5 단계)
  1. analyze_excel - 엑셀 파일에서 투자 데이터 추출
  2. calculate_valuation - PER 기반 기업가치 계산
  3. calculate_irr - IRR과 멀티플 계산
  4. generate_exit_projection - Exit 프로젝션 엑셀 생성
  5. verify_output - 출력 파일 검증

🔄 Phase 2: Executing Plan...

🔄 Step 1/5: analyze_excel
   Reason: 엑셀 파일에서 투자 데이터 추출
   ✅ Success

🔄 Step 2/5: calculate_valuation
   Reason: PER 기반 기업가치 계산
   ✅ Success

🔄 Step 3/5: calculate_irr
   Reason: IRR과 멀티플 계산
   ✅ Success

🔄 Step 4/5: generate_exit_projection
   Reason: Exit 프로젝션 엑셀 생성
   ✅ Success
   📄 Generated: 비사이드미_2029_Exit_프로젝션.xlsx

🔄 Step 5/5: verify_output
   Reason: 출력 파일 검증
   ✅ Success

✓ Phase 3: Verifying Goal Achievement...

============================================================
✅ Goal 달성! (완성도: 100%)
============================================================

📊 실행 결과
============================================================
✅ Goal 달성! (완성도: 100%)

📄 생성된 파일:
  • 비사이드미_2029_Exit_프로젝션.xlsx

💡 추천사항:
  • 민감도 분석 추가 고려
  • 여러 시나리오 비교 분석 권장
```

---

## 💡 사용 예시

### 예시 1: 기본 분석

```bash
python cli.py goal "비사이드미 투자 분석" -f "Valuation_비사이드미_202511.xlsx"
```

**Agent가 자동으로:**
1. 엑셀 파일 분석
2. 투자 조건 추출
3. 기업가치 계산
4. IRR/멀티플 계산
5. 결과 리포트 생성

### 예시 2: 복잡한 시나리오

```bash
python cli.py goal "SAFE 전환 포함한 Exit 프로젝션 생성" \
  -f "data.xlsx" \
  -p '{"safe_amount": 100000000, "target_year": 2029}'
```

**Agent가 자동으로:**
1. 파일 분석
2. SAFE 전환 희석 효과 계산
3. 다양한 PER 시나리오 분석
4. Complete Exit 프로젝션 엑셀 생성
5. 희석 분석 포함

### 예시 3: 자율 복구 테스트

```bash
# 일부러 잘못된 파일명
python cli.py goal "투자 분석" -f "wrong_file.xlsx"
```

**Agent의 자율 복구:**
```
🔄 Step 1/3: analyze_excel
   Reason: 엑셀 파일 분석
   ⚠️  Error: File not found: wrong_file.xlsx
   🔧 Attempting autonomous recovery...

   [Agent 사고 과정]
   - 유사한 파일명 검색
   - Valuation_*.xlsx 패턴 발견
   - 사용자에게 확인 요청 or 자동 선택

   ✅ Recovered: 유사 파일 'Valuation_비사이드미_202511.xlsx' 사용
```

---

## 🎯 Goal 작성 가이드

### Good Goals (구체적, 실행 가능)

✅ "투자 분석 완료 및 Exit 프로젝션 생성"
✅ "PER 15배 기준 IRR 계산"
✅ "SAFE 전환 시나리오 분석"
✅ "2029-2030 2단계 Exit 프로젝션"

### Bad Goals (모호함)

❌ "분석해줘" (무엇을?)
❌ "계산" (어떤 계산?)
❌ "도와줘" (무엇을?)

### Goal 작성 팁

1. **구체적으로:** "분석" → "투자 분석 완료 및 엑셀 생성"
2. **최종 상태 명시:** "IRR을 계산해줘" → "IRR 계산하고 엑셀에 포함"
3. **필요한 것만:** "모든 것" 대신 실제 필요한 것

---

## 🔧 고급 사용법

### 1. Python 코드에서 직접 사용

```python
import asyncio
from agent.autonomous_agent import AutonomousVCAgent

async def main():
    agent = AutonomousVCAgent()

    result = await agent.achieve_goal(
        goal="투자 분석 완료 및 Exit 프로젝션 생성",
        context={
            "excel_file": "Valuation_비사이드미_202511.xlsx",
            "target_year": 2029,
            "per_multiples": [10, 15, 20]
        },
        verbose=True
    )

    print(f"Goal 달성: {result['achieved']}")
    print(f"생성 파일: {result['output_files']}")

asyncio.run(main())
```

### 2. 복수 Goal 실행

```python
goals = [
    "투자 분석 완료",
    "민감도 분석 수행",
    "PDF 리포트 생성"
]

for goal in goals:
    result = await agent.achieve_goal(goal)
    print(f"{goal}: {'✅' if result['achieved'] else '⚠️'}")
```

### 3. 백그라운드 실행 (향후 구현)

```python
# 장기 작업을 백그라운드에서
job_id = agent.achieve_goal_async(
    goal="전체 포트폴리오 분석",
    context={"portfolio_files": [...]}
)

# 나중에 확인
status = agent.get_job_status(job_id)
print(f"진행률: {status['progress']}%")
```

---

## 🆚 Chatbot vs True Agent 비교

| 사용 시나리오 | Chatbot (기존) | True Agent (신규) |
|--------------|----------------|-------------------|
| 간단한 질문 | ✅ "IRR이 뭐야?" | ⚠️ 과한 느낌 |
| 단계별 탐색 | ✅ 대화하며 진행 | ❌ 한번에 실행 |
| **자동 완성** | ❌ 매번 명령 | ✅ Goal만 제시 |
| **복잡한 작업** | ⚠️ 여러 번 명령 | ✅ 한 번에 완료 |
| 에러 복구 | ❌ 중단 | ✅ 자동 복구 |

**추천 사용법:**
- **탐색/학습:** Chatbot (`python cli.py chat`)
- **작업 자동화:** True Agent (`python cli.py goal "..."`)

---

## 🎓 다음 단계

### 1. 다양한 Goal 시도

```bash
# 기본
python cli.py goal "투자 분석 완료" -f data.xlsx

# SAFE 시나리오
python cli.py goal "SAFE 전환 포함 분석" -f data.xlsx

# 복잡한 Exit
python cli.py goal "3단계 부분 매각 시나리오 분석" -f data.xlsx
```

### 2. 에러 복구 관찰

일부러 에러를 발생시켜 Agent의 자율 복구를 확인:
- 잘못된 파일명
- 누락된 파라미터
- 잘못된 데이터

### 3. 커스텀 Goal 작성

```bash
python cli.py goal "2029년 PER 12배, 2030년 EV/Revenue 5배로 \
                    2단계 Exit 분석하고 엑셀 생성" \
  -f data.xlsx
```

---

## 🐛 트러블슈팅

### 문제 1: "계획 수립 실패"

**원인:** Goal이 너무 모호함

**해결:**
```bash
# ❌ 모호
python cli.py goal "분석"

# ✅ 구체적
python cli.py goal "투자 분석 완료 및 Exit 프로젝션 엑셀 생성"
```

### 문제 2: "Tool 실행 실패"

**원인:** 파일 경로 오류

**해결:**
```bash
# 절대 경로 사용
python cli.py goal "분석" -f "/full/path/to/file.xlsx"

# 또는 Agent가 자동으로 유사 파일 검색
```

### 문제 3: "Goal 미달성"

**확인:**
- 실행 로그 확인
- 누락 항목 확인
- Agent의 추천사항 확인

**Agent가 제안:**
```
⚠️  Goal 부분 달성 (완성도: 80%)
누락 항목: 민감도 분석, PDF 리포트

💡 추천사항:
  • 추가 Goal 실행: "민감도 분석 수행"
  • 또는 Goal 수정: "기본 분석만 완료"
```

---

## 📞 다음 문서

- [TRUE_AGENT_DESIGN.md](TRUE_AGENT_DESIGN.md) - 아키텍처 상세
- [AGENT_SDK_DESIGN.md](AGENT_SDK_DESIGN.md) - SDK 설계
- [CLAUDE.md](CLAUDE.md) - Python 스크립트 직접 사용

---

**즐거운 자동화 되세요! 🚀**
