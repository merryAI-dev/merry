# Streamlit → Vercel Migration Plan

## 1. 현재 구조 요약

- **Streamlit UI (`app.py` + `pages/`):** 다수의 페이지(Exit Projection, Startup Discovery 등)를 Streamlit 멀티페이지로 구성하고, `shared/`와 `agent/`에서 Claude/Anthropic 기반 에이전트, Airtable/CSV 검색 및 Supabase 세션 로깅을 사용하는 올인원 앱.
- **Next.js + FastAPI Proof-of-concept:** `web/`에 이미 Next.js 클라이언트를, `backend/`에 FastAPI/`ai_agent` 브리지(DiscoveryAgent + Airtable 검색) API가 존재. Next.js는 `/api/chat` 및 `/api/portfolio`로 FastAPI를 호출하는 구조.
- **공통 로직:** `agent/`과 `shared/` 폴더 안에 Claude Agent, 도구 실행, Airtable 검색 등이 캡슐화되어 있어 재사용 가능.

## 2. 목표 아키텍처

1. **Next.js 프론트엔드(`web/`):** Vercel App Router를 채택하고, Streamlit 페이지 하나하나를 내비게이션 가능한 섹션/페이지로 분리한다 (Discovery, Exit Projection, Peer PER 등).
   - `web/app/layout.tsx`에서 전역 레이아웃 + 네비게이션 구성
   - 각 Streamlit 페이지는 Next의 `app/(page)` 섹션 또는 재사용 가능한 React `Panel` 컴포넌트로 매핑
   - 채팅/검색 대화 인터페이스는 현재 `page.tsx`를 확장하여 Claude Agent와 멀티턴 상태를 유지하도록 보완

2. **백엔드 로직(Claude Agent + Airtable):** `packages/ai_agent`를 중심으로 FastAPI를 유지하되, Vercel 배포를 위해 아래 두 가지 중 하나로 정리
   - FastAPI 앱(`backend/app.py`)을 Vercel의 Python serverless 함수(또는 별도 Vercel 프로젝트)로 배치하여 `/chat`, `/portfolio-search` 엔드포인트를 그대로 유지
   - 혹은 FastAPI를 Vercel 내부 `api/python` 폴더로 옮겨 Next API에서 직접 호출하도록 구성 (필요 시 Uvicorn 실행 엔트리 포함)
   - `ai_agent`가 내부적으로 `agent/discovery_agent.py`, `shared/airtable_portfolio.py`를 불러 사용하게 하고, 로컬 파일(`투자겁-Grid view.csv`)은 서버리스 파일로 번들되거나 Airtable API 우선 호출로 전환

3. **Next API 룯:** 기존 TypeScript API (`web/app/api/chat/route.ts` 등)는 유지하되, `BACKEND_URL` 환경변수를 통해 Vercel에 배포된 FastAPI 엔드포인트를 가리키도록 한다. 필요 시 직접 Python 함수로 통합하여 프록시를 제거하고 캐시/로깅을 강화.

4. **Secrets와 환경 변수:**
   - Vercel에서는 `AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE_NAME`, `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY` 등을 환경 변수로 설정
   - Next.js 환경(`.env.local`)과 Vercel 대시보드(Production/Preview)에서 동일한 키를 유지
   - 클라이언트에는 민감 정보가 넘어가지 않도록 `BACKEND_URL`만 전달하고, 실제 키는 Python 백엔드에서 `os.getenv` 또는 `st.secrets` 대체 구조로 사용

5. **데이터 접근:**
   - Airtable 연결 실패 시 현재 CSV fallback을 사용하므로 해당 CSV를 Vercel 배포 아티팩트에 포함하거나, 운영에서는 Airtable에 정상 연결되도록 한다.
   - Supabase 연동(세션/메시지 저장)은 FastAPI에서 처리하며, Vercel 서버리스 환경에서 `SUPABASE_URL`/`SUPABASE_KEY`를 이용한다.

## 3. 기능 매핑

| Streamlit 페이지 | Next.js 구성 | 비고 |
| --- | --- | --- |
| `pages/8_Startup_Discovery.py` | `app/(pages)/discovery` + `DiscoveryChatPanel` + `PortfolioResultPanel` | Claude 기반 대화, Airtable 검색 결과, Supabase 세션 기록을 프론트에서 폴링 없이 API로 호출
| `pages/1_Exit_Projection.py` 등 | 별도 `Panel` 컴포넌트 + shared agent 호출 버튼 | `DiscoveryAgent` 기반 로직을 `agent/`에서 분기하도록 `web`과 공유

## 4. 배포/운영 순서 (1~4 단계)

1. **현재 Next.js 앱 안정화:**
   - `web/app/page.tsx`를 다듬어 승계 UI/UX 구성
   - 글로벌 스타일 및 상태 관리(예: Zustand, React Context)로 채팅 로그, 포트폴리오 캐시 유지
2. **FastAPI → Vercel:**
   - `backend/app.py`를 `api/chat.py`/`api/portfolio.py` 같은 Vercel 함수로 패키징하거나, FastAPI 서버를 별도 Vercel 프로젝트로 배포
   - `packages/ai_agent`가 `agent`/`shared` 모듈을 로드할 수 있도록 `PYTHONPATH` 설정
3. **Secrets/Env 구성:**
   - `.env.local` (로컬)과 Vercel 환경 변수에 동일한 값을 설정 (`AIRTABLE_*`, `ANTHROPIC_*`, `SUPABASE_*`, `BACKEND_URL`)
   - Next API는 클라이언트로부터 받은 데이터를 그대로 백엔드로 프록시하면서 상태/로깅 추가
4. **CI/배포 문서화:**
   - `README`/`DEPLOYMENT.md`에 Vercel 배포 과정 (환경 변수 설정, `vercel --prod`)을 기록
   - 테스트 명령(`pnpm dev`, `uvicorn backend.app`)을 정리하고, `vercel.json`/`next.config.js`에서 rewrites(예: `/api/(.*)` → external API) 정의

## 5. 다음 작업 (Step 3: 프로토타입 구현)

1. Next.js UI에서 Discovery chat + portfolio result를 완전하게 표현하도록 컴포넌트를 분리
2. FastAPI backend에서 `/chat` `/portfolio-search`를 Vercel-compatible Python handler로 포장
3. `web/app/api`와 `backend` 사이의 `BACKEND_URL`을 설정하고, 필요 시 `fetch` 요청에 대한 예외 처리를 강화

