# 강화학습 (Reinforcement Learning) 활용 가이드

## 개요

VC Investment Agent는 사용자 피드백을 수집하여 **지속적으로 개선**되는 시스템입니다.

### 왜 강화학습인가?

1. **사용자 맞춤형 학습**: 실제 사용자 피드백으로 에이전트 성능 향상
2. **프롬프트 최적화**: 어떤 질문/응답 패턴이 좋은 평가를 받는지 학습
3. **도구 사용 최적화**: 어떤 도구 조합이 최적의 결과를 내는지 파악
4. **자동화된 개선**: 피드백 데이터가 쌓일수록 자동으로 더 똑똑해짐

---

## 피드백 수집 흐름

```
사용자 질문
    ↓
메리 응답 생성
    ↓
사용자 피드백 (👍/👎)
    ↓
┌─────────────────────────────────┐
│  1. JSONL 파일 저장             │
│  2. SQLite DB 저장 (통합 관리) │
│  3. 보상 점수 계산 (-1 ~ 1)    │
└─────────────────────────────────┘
    ↓
강화학습 데이터셋 생성
    ↓
프롬프트/응답 패턴 분석
```

---

## 데이터 구조

### 1. 피드백 데이터 (`feedback/feedback_data.jsonl`)

```json
{
  "id": "20251215_143000_123456",
  "timestamp": "2025-12-15T14:30:00",
  "user_message": "temp/투자검토.xlsx를 2030년 PER 10배로 분석해줘",
  "assistant_response": "분석을 완료했습니다. IRR 35.2%...",
  "feedback_type": "thumbs_up",
  "context": {
    "tools_used": ["read_excel_as_text", "analyze_and_generate_projection"]
  },
  "reward": 1.0
}
```

### 2. 강화학습 데이터셋 (`feedback/rl_dataset.jsonl`)

```json
{
  "prompt": "temp/투자검토.xlsx를 2030년 PER 10배로 분석해줘",
  "response": "분석을 완료했습니다. IRR 35.2%...",
  "reward": 1.0,
  "tools_used": ["read_excel_as_text", "analyze_and_generate_projection"],
  "timestamp": "2025-12-15T14:30:00"
}
```

### 3. SQLite 데이터베이스 (`feedback/feedback.db`)

**테이블 구조:**

- `feedbacks`: 모든 피드백 기록
- `session_stats`: 세션별 통계
- `rl_dataset`: 강화학습 훈련용 데이터

**왜 DB를 추가했나?**
- JSONL은 빠르게 쌓이지만 쿼리가 느림
- DB는 복잡한 분석 (통계, 패턴 분석) 가능
- 전체 조직의 피드백을 통합 관리

---

## 강화학습 활용 방법

### 1. 프롬프트 개선 (Prompt Engineering)

#### 목표
시스템 프롬프트를 개선하여 더 나은 응답 생성

#### 방법

```python
from agent.feedback_db import FeedbackDatabase, RLTrainingPipeline

db = FeedbackDatabase()
pipeline = RLTrainingPipeline(db)

# 낮은 평가를 받은 패턴 분석
low_patterns = db.get_low_performing_patterns(min_occurrences=3)

for pattern in low_patterns:
    print(f"문제 질문: {pattern['user_message']}")
    print(f"발생 횟수: {pattern['occurrences']}")
    print(f"평균 보상: {pattern['avg_reward']}")
    # → 이런 질문에 대한 처리를 시스템 프롬프트에 추가
```

#### 실제 활용 예시

**문제 발견:**
```
질문: "이 파일 분석해줘"
평균 보상: -0.8
발생 횟수: 15회
```

**시스템 프롬프트 개선:**
```python
# vc_agent.py 시스템 프롬프트에 추가
"""
사용자가 "이 파일" 같은 애매한 표현을 쓰면:
1. 어떤 파일인지 명확히 확인
2. 경로를 자동으로 찾아서 제안
3. 사용자 확인 후 진행
"""
```

---

### 2. 응답 품질 향상 (Response Quality)

#### 목표
높은 평가를 받은 응답 패턴을 학습

#### 방법

```python
# 우수 패턴 분석
high_patterns = db.get_high_performing_patterns(min_occurrences=3)

for pattern in high_patterns:
    print(f"우수 질문: {pattern['user_message']}")
    print(f"평균 응답 길이: {pattern['avg_response_length']}자")
    print(f"평균 보상: {pattern['avg_reward']}")
    # → 이런 응답 스타일을 다른 영역에도 적용
```

#### 발견 예시

**우수 패턴:**
```
질문: "2030년 PER 10,20,30배로 Exit 프로젝션 생성해줘"
평균 보상: 1.0
발생 횟수: 20회
평균 응답 길이: 450자
도구 사용: read_excel_as_text → analyze_and_generate_projection
```

**학습 내용:**
- 명확한 파라미터 (연도, PER 배수) → 높은 만족도
- 도구 2개 조합이 효과적
- 응답은 450자 정도가 적정

---

### 3. 도구 사용 최적화 (Tool Usage Optimization)

#### 목표
어떤 도구 조합이 최적의 결과를 내는지 학습

#### 방법

```python
# 도구 사용 패턴 분석
tool_analysis = pipeline.analyze_tool_usage_patterns()

print(tool_analysis['recommendation'])
# 출력: "권장 도구 조합: read_excel_as_text, analyze_and_generate_projection (평균 보상: 0.95)"
```

#### 활용 예시

**발견:**
- `analyze_excel` 단독 사용: 평균 보상 0.3
- `read_excel_as_text` → `analyze_and_generate_projection`: 평균 보상 0.95

**개선:**
```python
# vc_agent.py 시스템 프롬프트 수정
"""
엑셀 파일 분석 시:
1. 먼저 read_excel_as_text로 구조 파악 (권장)
2. 그 다음 analyze_and_generate_projection 실행
"""
```

---

### 4. Claude API 파인튜닝 (Fine-tuning)

#### 목표
실제 데이터로 Claude 모델 자체를 학습 (향후 가능)

#### 준비

```python
# 훈련 데이터 내보내기
db = FeedbackDatabase()
training_file = db.export_rl_training_data(min_reward=0.5)

print(f"훈련 데이터 생성: {training_file}")
# 출력: feedback/rl_training_data.jsonl
```

#### JSONL 형식 (Anthropic RLHF 형식)

```json
{
  "prompt": "사용자 질문",
  "response": "에이전트 응답",
  "reward": 1.0
}
```

#### 향후 활용 (Anthropic Fine-tuning API 사용)

```python
# Anthropic Fine-tuning API (향후)
from anthropic import Anthropic

client = Anthropic(api_key="...")

# 파인튜닝 작업 생성
fine_tune = client.fine_tuning.create(
    model="claude-opus-4-5-20251101",
    training_file="feedback/rl_training_data.jsonl",
    validation_file="feedback/rl_validation.jsonl"
)

# 파인튜닝된 모델 사용
agent = VCAgent(model=fine_tune.model_id)
```

---

## 리포트 생성

### 프롬프트 개선 리포트

```python
from agent.feedback_db import FeedbackDatabase

db = FeedbackDatabase()
report_path = db.generate_prompt_improvement_report()

print(f"리포트 생성: {report_path}")
```

**리포트 내용:**
- 전체 통계 (만족도, 피드백 수, 평균 보상)
- 개선 필요 패턴 (부정적 피드백 Top 5)
- 우수 패턴 (긍정적 피드백 Top 5)
- 구체적 개선 제안

---

## 실전 워크플로우

### 매주 금요일: 피드백 분석 및 개선

```python
# 1. 통계 확인
db = FeedbackDatabase()
stats = db.get_global_stats()

print(f"이번 주 피드백: {stats['total_feedback']}개")
print(f"만족도: {stats['satisfaction_rate']*100:.1f}%")

# 2. 리포트 생성
report = db.generate_prompt_improvement_report()
print(f"리포트: {report}")

# 3. 패턴 분석
pipeline = RLTrainingPipeline(db)
low_patterns = db.get_low_performing_patterns()
high_patterns = db.get_high_performing_patterns()

# 4. 시스템 프롬프트 개선
improvements = pipeline.generate_system_prompt_improvements()
with open("prompt_improvements.md", "w") as f:
    f.write(improvements)

# 5. vc_agent.py 수정
# - 시스템 프롬프트 업데이트
# - 도구 사용 순서 조정
# - 응답 스타일 개선
```

---

## 통계 쿼리 예시

### 전체 통계

```python
stats = db.get_global_stats()
# {
#   "total_feedback": 150,
#   "positive_feedback": 120,
#   "negative_feedback": 30,
#   "satisfaction_rate": 0.80,
#   "average_reward": 0.65,
#   "total_sessions": 45,
#   "total_users": 12
# }
```

### 사용자별 통계

```python
user_stats = db.get_user_stats("홍길동")
# {
#   "total_feedback": 25,
#   "positive_feedback": 22,
#   "satisfaction_rate": 0.88
# }
```

### 패턴 분석

```python
# 개선 필요
low = db.get_low_performing_patterns(min_occurrences=3)

# 우수 사례
high = db.get_high_performing_patterns(min_occurrences=3)
```

---

## 지속적 개선 사이클

```
1주차
    ↓
피드백 수집 (20개)
    ↓
패턴 분석 → 문제 발견: "파일 경로 애매함"
    ↓
프롬프트 개선
    ↓
2주차
    ↓
피드백 수집 (30개)
    ↓
만족도 상승 (70% → 85%)
    ↓
새로운 패턴 발견: "응답 너무 짧음"
    ↓
응답 길이 조정
    ↓
3주차...
```

---

## 핵심 메트릭

### 추적해야 할 지표

1. **만족도 (Satisfaction Rate)**
   - 목표: 80% 이상
   - 계산: 👍 / (👍 + 👎)

2. **평균 보상 (Average Reward)**
   - 목표: 0.6 이상
   - 범위: -1.0 ~ 1.0

3. **개선 속도**
   - 주차별 만족도 증가율
   - 목표: 매주 2-5% 상승

4. **사용자 참여도**
   - 피드백 비율 (응답 당 피드백 수)
   - 목표: 30% 이상

---

## CLI 도구

### 피드백 통계 확인

```bash
# 전체 통계
python -c "from agent.feedback_db import FeedbackDatabase; db = FeedbackDatabase(); print(db.get_global_stats())"

# 리포트 생성
python -c "from agent.feedback_db import FeedbackDatabase; db = FeedbackDatabase(); print(db.generate_prompt_improvement_report())"

# 훈련 데이터 내보내기
python -c "from agent.feedback_db import FeedbackDatabase; db = FeedbackDatabase(); print(db.export_rl_training_data())"
```

---

## 결론

### 강화학습으로 달성할 수 있는 것

1. ✅ **자동화된 품질 개선**: 사용자 피드백으로 자동 학습
2. ✅ **프롬프트 최적화**: 데이터 기반 시스템 프롬프트 개선
3. ✅ **도구 사용 최적화**: 최적의 도구 조합 발견
4. ✅ **개인화**: 사용자/조직별 맞춤형 응답
5. ✅ **지속적 개선**: 데이터가 쌓일수록 더 똑똑해짐

### 다음 단계

1. **1개월 데이터 수집**: 최소 100개 피드백 확보
2. **패턴 분석**: 개선/우수 패턴 식별
3. **프롬프트 개선**: 시스템 프롬프트 업데이트
4. **A/B 테스트**: 개선 전/후 비교
5. **반복**: 지속적 개선 사이클 확립

**목표: 3개월 내 만족도 90% 달성! 🎯**
