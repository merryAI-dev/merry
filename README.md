# VC 투자 분석 에이전트

투자 검토 엑셀/IR PDF/기업현황 진단시트를 AI와 대화하며 분석하고 결과 엑셀을 자동 생성하는 도구입니다.

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
- **Peer PER 분석**: 유사 상장기업 PER 비교 및 밸류에이션 지원
- **기업현황 진단시트**: 체크리스트/가중치 기반 점수 산출 + 컨설턴트 보고서 엑셀 반영
- **AI 대화형 분석**: 한국어로 자연스럽게 질문하고 즉시 답변
- **전문 엑셀 생성**: 색상 코딩된 Exit 프로젝션 파일 자동 생성

---

## 🛠️ 기타 사용 방법

### 1. Claude Skill로 사용
```bash
# Claude Code에서
/vc-investment-analyzer        # 투자 분석
/g2b-bid-downloader 액셀러레이팅  # 나라장터 입찰 검색
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

# 모드 지정 (exit | peer | diagnosis)
python cli.py chat --mode diagnosis
python cli.py analyze <파일경로> --mode peer
```

---

## 🤖 Claude Code 스킬 설정 (비개발자용)

Claude Code를 처음 사용하시는 분은 아래 순서대로 설정하세요.

### Step 1. 사전 설치

**터미널 열기**: `Cmd + Space` → "터미널" 입력 → Enter

```bash
# Homebrew 설치 (없는 경우)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Node.js 설치 (없는 경우)
brew install node
```

### Step 2. Claude Code 설치

```bash
npm install -g @anthropic-ai/claude-code
```

### Step 3. Claude Code 로그인

```bash
claude
```
→ 브라우저에서 Anthropic 계정 로그인 → "Claude Code 액세스 허용" 클릭

### Step 4. 프로젝트 폴더로 이동

```bash
cd "/Users/$(whoami)/Library/CloudStorage/GoogleDrive-본인이메일@mysc.co.kr/공유 드라이브/C. 조직 (랩, 팀, 위원회, 클럽)/00.AX솔루션/projection_helper"
```

(본인이메일 부분을 본인 구글 계정으로 변경)

**폴더 이동이 안 되면**: Finder에서 폴더를 터미널 창에 드래그 앤 드롭

### Step 5. 추가 패키지 설치 (나라장터 스킬용)

```bash
source venv/bin/activate
pip install playwright olefile
playwright install chromium
```

### Step 6. 스킬 사용

```bash
claude
```

Claude Code가 실행되면:
```
나라장터에서 액셀러레이팅 입찰 찾아줘
```

또는 스킬 직접 실행:
```
/g2b-bid-downloader 액셀러레이팅
```

**상세 가이드**: [.claude/skills/g2b-bid-downloader/SKILL.md](.claude/skills/g2b-bid-downloader/SKILL.md)

---

## 문서

- [CLAUDE.md](CLAUDE.md) - Claude Code 사용 가이드
- [AGENT_SDK_DESIGN.md](AGENT_SDK_DESIGN.md) - Agent 아키텍처 설계
- [DEPLOYMENT.md](DEPLOYMENT.md) - 배포 전략
- [SECURITY_FAQ.md](SECURITY_FAQ.md) - 보안 FAQ

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
