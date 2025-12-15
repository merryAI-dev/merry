# VC Investment Agent - 배포 전략 (Google Drive 환경)

## 현재 상황 분석

**문제점:**
```
현재 위치: Google Drive/공유 드라이브/00.AX솔루션/projection_helper
- 구글 드라이브 동기화 폴더
- 팀원들과 공유 중
- 파일 경로가 길고 한글 포함
- Git 저장소 아님 (독립 배포 어려움)
```

**질문: "VSCode로 열어서 사용하겠 될까?"**
→ **가능하지만 제한적입니다.** 더 나은 방법이 있습니다.

---

## 배포 전략 3단계

### ✅ 전략 1: 현재 위치에서 바로 사용 (권장: Phase 1)

**장점:**
- 추가 작업 없음
- 팀원들과 즉시 공유
- 구글 드라이브 동기화로 자동 백업

**단점:**
- 독립 배포 불가
- 버전 관리 어려움
- VSCode Extensions 제한적

**구현:**
```bash
# 1. 현재 위치에서 그대로 사용
cd "/Users/boram/Library/CloudStorage/GoogleDrive-mwbyun1220@mysc.co.kr/공유 드라이브/C. 조직 (랩, 팀, 위원회, 클럽)/00.AX솔루션/projection_helper"

# 2. Python 가상환경 설정
python -m venv venv
source venv/bin/activate
pip install anthropic openpyxl

# 3. Agent 실행
python agent.py
```

**파일 구조:**
```
projection_helper/  (현재 위치)
├── .claude/
│   └── skills/
│       └── vc-investment-analyzer/  # 기존 스킬 유지
├── scripts/                          # 기존 Python 스크립트 유지
│   ├── analyze_valuation.py
│   ├── generate_exit_projection.py
│   └── ...
├── agent/                            # 🆕 Agent SDK 추가
│   ├── __init__.py
│   ├── agent.py                      # ConversationalVCAgent
│   ├── tools.py                      # Tool 정의
│   └── context.py                    # AgentContext
├── cli.py                            # 🆕 CLI 인터페이스
├── requirements.txt
└── README.md
```

**사용 방법:**
```bash
# CLI로 사용
python cli.py chat
> 비사이드미 투자 분석해줘

# 또는 기존 스킬로 사용
# Claude Code에서 /vc-investment-analyzer
```

---

### ✅ 전략 2: Local Git + 심볼릭 링크 (권장: Phase 2)

**구글 드라이브는 공유용, Git은 개발용**

```bash
# 1. 로컬 Git 저장소 생성
cd ~/Projects
git init vc-investment-agent
cd vc-investment-agent

# 2. 코드 복사
cp -r "/Users/boram/Library/CloudStorage/.../projection_helper/agent" .
cp -r "/Users/boram/Library/CloudStorage/.../projection_helper/scripts" .

# 3. Git 설정
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourteam/vc-investment-agent.git
git push -u origin main

# 4. 구글 드라이브와 심볼릭 링크 연결
ln -s ~/Projects/vc-investment-agent/agent "/Users/boram/Library/CloudStorage/.../projection_helper/agent"
```

**장점:**
- Git으로 버전 관리
- 구글 드라이브와 동기화 유지
- 팀원들도 같은 방식으로 사용

**파일 구조:**
```
~/Projects/vc-investment-agent/  (Git 저장소)
├── .git/
├── agent/
├── scripts/
├── tests/
├── pyproject.toml
└── README.md

Google Drive/projection_helper/
├── agent/ → (심볼릭 링크 → ~/Projects/vc-investment-agent/agent)
└── .claude/skills/  (스킬은 여기 유지)
```

---

### ✅ 전략 3: pip 패키지 배포 (권장: Phase 3)

**독립 패키지로 배포 → 어디서나 사용 가능**

#### 3-1. 패키지 구조 생성

```bash
# 1. PyPI 패키지 구조
cd ~/Projects/vc-investment-agent

# 2. 표준 Python 패키지 구조
mkdir -p src/vc_investment_agent
```

**파일 구조:**
```
vc-investment-agent/
├── src/
│   └── vc_investment_agent/
│       ├── __init__.py
│       ├── agent.py
│       ├── tools.py
│       ├── cli.py
│       └── scripts/         # 기존 스크립트 포함
├── tests/
│   ├── test_agent.py
│   └── fixtures/
├── pyproject.toml
├── README.md
└── LICENSE
```

**pyproject.toml:**
```toml
[project]
name = "vc-investment-agent"
version = "0.1.0"
description = "VC 투자 분석 및 Exit 프로젝션 AI 에이전트"
authors = [
    {name = "AX Solutions", email = "team@axsolutions.com"}
]
dependencies = [
    "anthropic>=0.40.0",
    "openpyxl>=3.1.0",
    "click>=8.1.0",
]

[project.scripts]
vc-agent = "vc_investment_agent.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

#### 3-2. 배포 방법

**A. GitHub에서 직접 설치 (팀 내부용)**
```bash
# 팀원들이 이렇게 설치
pip install git+https://github.com/yourteam/vc-investment-agent.git

# 사용
vc-agent chat
vc-agent analyze investment.xlsx
```

**B. Private PyPI 서버 (회사 내부)**
```bash
# 1. Private PyPI 구축 (AWS S3 + pypiserver)
docker run -d -p 8080:8080 pypiserver/pypiserver

# 2. 패키지 업로드
python -m build
twine upload --repository-url http://pypi.internal dist/*

# 3. 팀원들 설치
pip install --index-url http://pypi.internal vc-investment-agent
```

**C. Public PyPI (오픈소스화 시)**
```bash
# PyPI.org에 배포
python -m build
twine upload dist/*

# 전 세계 누구나 설치 가능
pip install vc-investment-agent
```

---

## VSCode 사용 가이드

### 현재 구글 드라이브에서 VSCode 사용

```bash
# 1. VSCode로 폴더 열기
code "/Users/boram/Library/CloudStorage/GoogleDrive-mwbyun1220@mysc.co.kr/공유 드라이브/C. 조직 (랩, 팀, 위원회, 클럽)/00.AX솔루션/projection_helper"

# 2. Python 인터프리터 설정
# Command Palette (Cmd+Shift+P)
# > Python: Select Interpreter
# > ./venv/bin/python 선택

# 3. 터미널에서 실행
# VSCode 내장 터미널 (Ctrl+`)
python agent/agent.py
```

**VSCode Extensions 추천:**
```json
// .vscode/extensions.json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "ms-toolsai.jupyter",
    "anthropics.claude-code"  // Claude Code Extension
  ]
}
```

**VSCode 설정:**
```json
// .vscode/settings.json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.testing.pytestEnabled": true,
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true
  }
}
```

---

## 팀원 온보딩 방법

### 방법 1: 구글 드라이브 공유 (가장 간단)

```bash
# 팀원 A, B, C가 해야 할 일

# 1. 구글 드라이브 동기화 활성화
# (이미 되어 있음)

# 2. 터미널에서 이동
cd "/Users/[팀원이름]/Library/CloudStorage/.../projection_helper"

# 3. 가상환경 설치
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. 사용
python cli.py chat
```

**requirements.txt 생성:**
```bash
# 현재 환경 내보내기
cd "/Users/boram/Library/CloudStorage/.../projection_helper"
source venv/bin/activate
pip freeze > requirements.txt
```

### 방법 2: pip 패키지 설치 (배포 후)

```bash
# 팀원들이 어디서든 실행
pip install vc-investment-agent

# 프로젝트 폴더로 이동 필요 없음
cd ~/Downloads
vc-agent analyze "투자검토.xlsx"
```

---

## 클라우드 배포 옵션

### Option 1: Streamlit Cloud (웹 인터페이스)

**장점:**
- 무료 배포
- 비개발자도 브라우저에서 사용
- 팀원들과 URL 공유

**구현:**
```python
# streamlit_app.py
import streamlit as st
from vc_investment_agent import ConversationalVCAgent

st.title("VC 투자 분석 에이전트")

uploaded_file = st.file_uploader("엑셀 파일 업로드")

if uploaded_file:
    agent = ConversationalVCAgent()

    with st.chat_message("user"):
        st.write("파일이 업로드되었습니다.")

    prompt = st.chat_input("분석 요청을 입력하세요")

    if prompt:
        with st.chat_message("assistant"):
            response = st.write_stream(agent.chat(prompt))
```

**배포:**
```bash
# GitHub 연동 후
https://share.streamlit.io/yourteam/vc-investment-agent

# 팀원들 접속
https://vc-agent.streamlit.app
```

### Option 2: Render/Railway (API 서버)

**FastAPI 서버:**
```python
# api.py
from fastapi import FastAPI, UploadFile
from vc_investment_agent import ConversationalVCAgent

app = FastAPI()
agent = ConversationalVCAgent()

@app.post("/analyze")
async def analyze(file: UploadFile):
    result = await agent.analyze(file.filename)
    return result

@app.post("/chat")
async def chat(message: str):
    response = await agent.chat(message)
    return {"response": response}
```

**배포:**
```bash
# Render.com에 배포 (무료)
https://vc-agent.onrender.com/analyze

# Slack에서 호출
/invest-analyze https://drive.google.com/file/d/.../
```

---

## 권장 로드맵

### Phase 1: 현재 위치 (구글 드라이브)에서 시작 ✅
```
기간: 1주일
목표: Agent 코드 작성 및 팀 내부 테스트
위치: Google Drive/projection_helper/agent/
사용: python cli.py chat
```

### Phase 2: Git 저장소 + 심볼릭 링크 ✅
```
기간: 1주일
목표: 버전 관리 시작, 팀원 협업
위치: ~/Projects/vc-investment-agent (Git)
     + Google Drive (심볼릭 링크)
사용: git으로 개발, 구글 드라이브로 공유
```

### Phase 3: pip 패키지 배포 ✅
```
기간: 2주일
목표: 독립 패키지, 팀 전체 배포
설치: pip install vc-investment-agent
사용: vc-agent chat (어디서나)
```

### Phase 4: 웹 인터페이스 배포 🎯
```
기간: 2주일
목표: 비개발자도 사용 가능
접속: https://vc-agent.streamlit.app
사용: 브라우저에서 파일 업로드 → 분석
```

---

## 즉시 시작하는 방법 (오늘 당장)

```bash
# 1. 현재 위치에서 Agent 폴더 생성
mkdir -p agent
cd agent

# 2. 필수 파일 생성
touch __init__.py agent.py tools.py

# 3. requirements.txt 생성
cat > requirements.txt << EOF
anthropic>=0.40.0
openpyxl>=3.1.0
click>=8.1.0
EOF

# 4. 가상환경 설치
cd ..
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. CLI 스크립트 생성
cat > cli.py << 'EOF'
#!/usr/bin/env python3
import click
from agent.agent import ConversationalVCAgent

@click.group()
def cli():
    """VC 투자 분석 에이전트"""
    pass

@cli.command()
def chat():
    """대화형 모드"""
    agent = ConversationalVCAgent()

    click.echo("VC 투자 분석 에이전트 시작 (종료: exit)")

    while True:
        user_input = click.prompt("You", type=str)

        if user_input.lower() in ["exit", "quit"]:
            break

        click.echo("Agent: ", nl=False)
        # TODO: agent.chat() 구현 후 연결
        click.echo("(Agent 응답)")

if __name__ == "__main__":
    cli()
EOF

chmod +x cli.py

# 6. 실행 테스트
python cli.py chat
```

---

## 결론

**Q: "VSCode로 열어서 사용하겠 될까?"**

**A: 3단계 답변**

1. **지금 당장 (Phase 1)**: ✅ 됩니다
   - 구글 드라이브 폴더를 VSCode로 열기
   - agent/ 폴더 추가하고 개발
   - 팀원들과 구글 드라이브로 공유

2. **더 나은 방법 (Phase 2)**: ✅ Git + 심볼릭 링크
   - Git으로 버전 관리
   - 구글 드라이브는 배포용으로만
   - VSCode에서 Git 저장소 작업

3. **최종 목표 (Phase 3-4)**: 🎯 독립 배포
   - pip 패키지: `pip install vc-investment-agent`
   - 웹 인터페이스: URL 접속만으로 사용
   - API 서버: Slack/다른 시스템 연동

**추천: Phase 1 → Phase 2 → Phase 3 순차 진행**

필요하시면 지금 바로 Phase 1 구현을 시작해드릴까요?
