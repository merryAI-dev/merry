# 🚀 Quick Start Guide

## ⚠️ 시작 전 필수 작업

### 1. API 키 설정

**중요: API 키를 절대 코드에 직접 넣지 마세요!**

```bash
# .env 파일 생성
cat > .env << EOF
ANTHROPIC_API_KEY=sk-ant-api03-your-actual-key-here
EOF

# .env 파일이 Git에 커밋되지 않도록 확인
echo ".env" >> .gitignore
```

**API 키 발급:**
1. https://console.anthropic.com/settings/keys 접속
2. "Create Key" 클릭
3. 생성된 키를 복사하여 .env 파일에 붙여넣기

---

## 📦 설치

### Step 1: Python 환경 설정

```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
source venv/bin/activate  # Mac/Linux
# 또는
venv\Scripts\activate  # Windows
```

### Step 2: 의존성 설치

```bash
pip install -r requirements.txt
```

---

## 🎯 사용 방법

### 방법 1: 대화형 모드 (추천)

```bash
python cli.py chat
```

**예시 대화:**
```
You: 안녕? 너는 무엇을 할 수 있어?
Agent: 안녕하세요! 저는 VC 투자 분석 전문 AI 에이전트입니다...

You: 비사이드미 투자 파일 분석해줘
Agent: 🔧 도구 사용: analyze_excel
      ✅ 완료

      분석 결과입니다:
      - 투자금액: 3억원
      - 투자단가: 32,808원
      ...

You: 2029년 PER 15로 Exit 하면 IRR이 어떻게 돼?
Agent: 🔧 도구 사용: calculate_valuation
      🔧 도구 사용: calculate_irr
      ✅ 완료

      2029년 PER 15배 기준:
      - 기업가치: 420억원
      - 회수금액: 31.5억원
      - 멀티플: 10.5x
      - IRR: 61.2%
```

### 방법 2: 파일 빠른 분석

```bash
python cli.py analyze "Valuation_비사이드미_202511.xlsx"
```

### 방법 3: 연결 테스트

```bash
python cli.py test
```

### 방법 4: 정보 확인

```bash
python cli.py info
```

---

## 💡 사용 예시

### 예시 1: 기본 분석

```
You: 비사이드미_202511.xlsx 파일 분석해줘

Agent: (파일 분석 후)
       투자조건:
       - 투자금액: 300,000,000원
       - 투자단가: 32,808원
       - 투자주식수: 9,145주
       ...
```

### 예시 2: 복잡한 시나리오

```
You: 다음 조건으로 Exit 분석해줘:
     1. 2028년에 30% 매각 (PER 12)
     2. 2029년에 SAFE 1억 전환 (밸류캡 50억)
     3. 2030년에 나머지 IPO (EV/Revenue 5배)

Agent: (자동으로 도구 조합하여 분석)
       복잡한 3단계 시나리오 분석 결과:
       - 1차 회수: 8.4억 (2028년)
       - SAFE 희석: 5.2%
       - 2차 회수: 23.1억 (2030년)
       - 총 멀티플: 10.5x
       - 복합 IRR: 61.2%
```

### 예시 3: 엑셀 생성

```
You: 이 분석 결과를 엑셀로 만들어줘.
     basic, advanced, complete 중에 complete로.

Agent: (엑셀 생성)
       ✅ 완료
       파일 생성: 비사이드미_Complete_Exit_프로젝션.xlsx
```

---

## 🔧 트러블슈팅

### 문제 1: API 키 오류

```
❌ ANTHROPIC_API_KEY가 설정되지 않았습니다.
```

**해결:**
```bash
# .env 파일 확인
cat .env

# API 키가 없으면 추가
echo "ANTHROPIC_API_KEY=sk-ant-api03-..." > .env
```

### 문제 2: 모듈 없음 오류

```
ModuleNotFoundError: No module named 'anthropic'
```

**해결:**
```bash
# 가상환경 활성화 확인
which python  # venv/bin/python이어야 함

# 의존성 재설치
pip install -r requirements.txt
```

### 문제 3: 엑셀 파일 못 찾음

```
Error: File not found
```

**해결:**
```bash
# 절대 경로 사용
python cli.py analyze "/Users/.../file.xlsx"

# 또는 상대 경로
python cli.py analyze "./Valuation_비사이드미_202511.xlsx"
```

---

## 🎓 다음 단계

### 1. 고급 기능 탐색
- [AGENT_SDK_DESIGN.md](AGENT_SDK_DESIGN.md) - 아키텍처 이해
- [CLAUDE.md](CLAUDE.md) - Python 스크립트 직접 사용

### 2. 팀 공유
- 구글 드라이브 동기화로 자동 공유
- 팀원들도 동일한 설치 과정 진행

### 3. 웹 인터페이스 (선택)
- Streamlit으로 웹 UI 추가 가능
- [DEPLOYMENT.md](DEPLOYMENT.md) 참고

---

## 📞 문의

문제가 있으면 다음 로그를 공유하세요:

```bash
# 환경 정보
python --version
pip list

# 에러 로그
python cli.py test 2>&1 | tee error.log
```

---

**즐거운 분석 되세요! 🚀**
