# VC 투자 분석 에이전트

투자 검토 엑셀 파일을 AI와 대화하며 분석하고 Exit 프로젝션을 자동 생성하는 도구입니다.

## 🚀 빠른 시작 (3초 컷!)

### 원클릭 실행

```bash
./run.sh
```

이 명령어 하나로:
- ✅ 가상환경 자동 생성
- ✅ 패키지 자동 설치
- ✅ 웹 UI 자동 실행
- ✅ 브라우저가 자동으로 열립니다!

### API 키 설정 (최초 1회만)

`.env` 파일을 생성하고 API 키를 입력:

```bash
echo "ANTHROPIC_API_KEY=your-api-key-here" > .env
```

**그게 끝입니다!** 🎉

---

## 💬 사용 방법

웹 UI가 열리면:

1. **왼쪽 사이드바**에서 엑셀 파일 드래그&드롭
2. **채팅창**에 명령 입력:
   - "이 파일 분석해줘"
   - "2030년 PER 10배, 20배, 30배로 Exit 프로젝션 만들어줘"
   - "IRR은 얼마야?"
3. **빠른 명령어** 버튼으로 원클릭 분석

---

## 📊 주요 기능

- **자동 엑셀 분석**: 투자조건, IS요약, Cap Table 자동 추출
- **Exit 프로젝션 생성**: PER/EV 기반 시나리오별 수익률 계산
- **AI 대화형 분석**: 한국어로 자연스럽게 질문하고 즉시 답변
- **전문 엑셀 생성**: 색상 코딩된 Exit 프로젝션 파일 자동 생성

---

## 🛠️ 기타 사용 방법

### 1. Claude Skill로 사용
```bash
# Claude Code에서
/vc-investment-analyzer
```

### 2. Python 스크립트로 사용
```bash
# 엑셀 분석
python scripts/analyze_valuation.py "투자검토.xlsx"

# Exit 프로젝션 생성
python scripts/generate_exit_projection.py \
  --investment_amount 300000000 \
  --company_name "회사명" \
  ...
```

### 3. CLI로 사용
```bash
# 대화형 모드
python cli.py chat

# 파일 분석
python cli.py analyze <파일경로>
```

## 문서

- [CLAUDE.md](CLAUDE.md) - Claude Code 사용 가이드
- [AGENT_SDK_DESIGN.md](AGENT_SDK_DESIGN.md) - Agent 아키텍처 설계
- [DEPLOYMENT.md](DEPLOYMENT.md) - 배포 전략

## 설치

```bash
# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

## 📁 프로젝트 구조

```
projection_helper/
├── app.py                 # Streamlit 웹 UI ⭐
├── run.sh                 # 원클릭 실행 스크립트 ⭐
├── .env                   # API 키 (직접 생성 필요)
├── agent/                 # AI 에이전트 코어
│   ├── vc_agent.py       # 통합 에이전트
│   └── tools.py          # 도구 정의
├── scripts/               # Exit 프로젝션 생성 스크립트
│   ├── analyze_valuation.py
│   ├── generate_exit_projection.py
│   ├── generate_advanced_exit_projection.py
│   └── generate_complete_exit_projection.py
├── .streamlit/            # Streamlit 테마 설정
│   └── config.toml       # 다크 모드 + Space Grotesk 폰트
└── requirements.txt       # 의존성 패키지
```

---

## ❓ 문제 해결

### Q: `./run.sh` 실행이 안 돼요
```bash
chmod +x run.sh
./run.sh
```

### Q: API 키 오류가 나요
```bash
# .env 파일 확인
cat .env

# 없으면 생성
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

### Q: 웹 브라우저가 자동으로 안 열려요
수동으로 열어주세요:
```
http://localhost:8501
```

---

## 🔧 기술 스택

- **Claude Opus 4.5** - AI 모델
- **Streamlit** - 웹 UI 프레임워크
- **openpyxl** - 엑셀 처리
- **Python 3.12** - 런타임

---

## 📄 라이선스

Proprietary - MYSC AX솔루션

**문의**: mwbyun1220@mysc.co.kr
