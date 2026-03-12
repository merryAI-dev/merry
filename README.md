# MERRY — AI 투자심사 플랫폼

> 사람을 대체하는 게 아니라, 함께 더 잘하는 것.

MERRY는 VC 심사역을 위한 AI 투자심사 동료입니다. PDF 서류를 업로드하면 자동 추출·분류하고, 의사결정 트리로 분기 심사를 진행한 뒤, 두 관점의 메리가 토론하며 보고서를 합본으로 생성합니다.

<!-- TODO: 스크린샷/GIF 자리 -->

---

## 목차

- [사용법](#사용법)
  - [1. 문서 추출 (RALPH)](#1-문서-추출-ralph)
  - [2. 투자심사 보고서](#2-투자심사-보고서)
  - [3. 팀 허브](#3-팀-허브)
  - [4. 펀드 · 기업 관리](#4-펀드--기업-관리)
  - [5. Exit 프로젝션](#5-exit-프로젝션)
  - [6. 배치 추출](#6-배치-추출)
  - [7. 보고서 초안 · 리뷰](#7-보고서-초안--리뷰)
  - [8. 관리자](#8-관리자)
- [기술 구현](#기술-구현)
- [차별점](#차별점)
- [프로젝트 구조](#프로젝트-구조)
- [API 엔드포인트 전체 목록](#api-엔드포인트-전체-목록)
- [로컬 개발](#로컬-개발)
- [배포](#배포)
- [팀](#팀)

---

## 사용법

### 1. 문서 추출 (RALPH)

PDF를 업로드하면 자동으로 문서 종류를 판별하고 내용을 추출합니다.

<!-- TODO: 문서추출 GIF -->

**워크플로우:**

1. `/documents` 페이지에서 PDF 드래그 & 드롭 (다중 파일 지원)
2. RALPH 엔진이 1차 PyMuPDF 추출 → 품질 자동 평가
3. 품질이 낮으면 (fragmented, 구조 파손) Amazon Nova Pro로 자동 재분석
4. 두 소스 중 **실질 콘텐츠가 더 풍부한 쪽**을 자동 선택
5. 추출 결과를 3가지 뷰로 확인:
   - **마크다운 뷰**: 정규화된 읽기 편한 형태
   - **Raw JSON**: 원본 추출 데이터 전체
   - **조건 검사**: 문서별 필수 항목 체크 결과
6. 메타데이터 요약 바에서 페이지 수, 추출 방법, 품질 점수, 구조 유형 확인
7. "투자심사 시작" 버튼으로 바로 보고서 세션 생성

**지원 문서 종류** (9종):

| 문서 | 추출 항목 |
|------|-----------|
| 사업자등록증 | 상호, 대표자, 사업자번호, 업종, 개업일 |
| 재무제표 | 연도별 매출, 영업이익, 당기순이익, 자산/부채 |
| 주주명부 | 주주명, 지분율, 주식수, 주식 종류 |
| 투자검토서 | 투자조건, IS요약, Cap Table, 밸류에이션 |
| 임직원명부 | 직원 수, 직급 분포, 핵심 인력 정보 |
| 벤처확인서 | 확인 유형, 유효기간, 확인기관 |
| 인증서 | 인증 종류, 발급일, 유효기간 |
| 정관 | 목적사업, 주식 총수, 이사회 구성 |
| 법인등기부등본 | 법인명, 설립일, 자본금, 이사/감사 현황 |

**텍스트 정규화 로직:**
- `hasMeaningfulContent()` — 공백·제로폭 문자 제거 후 20자 이상인지 판별
- `text` vs `visual_description.readable_text` 중 실질 콘텐츠가 풍부한 소스 자동 선택
- `[LLM ERROR]` 접두어 콘텐츠 자동 필터링

---

### 2. 투자심사 보고서

대화형으로 투자심사 보고서를 작성합니다. 분기 심사 → 이중 관점 토론 → 섹션 생성 → 합본의 엔드투엔드 워크플로우.

<!-- TODO: 분기심사 + 토론 GIF -->

#### 2-1. 세션 생성

`/report/new`에서 새 세션을 만듭니다.

- 기업명, 펀드, 작성자 입력
- 추출된 문서가 있으면 자동 연결 (컨텍스트 주입)
- 세션별 고유 slug → `/report/[slug]`에서 작업

#### 2-2. 분기 심사 (Decision Tree)

의사결정 트리 형태로 투자 판단의 분기점을 하나씩 점검합니다.

1. **기본 질문 6개** — 투자 적격성, 시장성, 팀, 재무, 리스크, 임팩트
2. **AI 자동 분기 (최대 5개)** — 이전 답변을 기반으로 LLM이 autoregressive하게 다음 질문 생성
3. 5개 자동 분기 도달 시 **자동으로 대화 모드 전환** (무한 생성 방지)
4. 커스텀 분기를 수동으로 추가 가능
5. 트리 전체를 SVG/PNG로 내보내기

모든 의사결정 기록은 후속 보고서 생성 시 컨텍스트로 자동 주입됩니다.

#### 2-3. 이중 관점 투자 토론 (Dual-Perspective Debate)

분기 심사 완료 후 동일 LLM에 다른 시스템 프롬프트를 주입하여 **두 관점이 자동 토론**합니다.

| 라운드 | 역할 | 내용 |
|--------|------|------|
| 1 | 🟢 긍정 메리 | 투자 매력, 성장 동력, 기회 분석 |
| 2 | 🔴 비관 메리 | 리스크, 경쟁 위협, 최악 시나리오 반론 |
| 3 | 🟢 긍정 메리 | 비관 논점에 대한 재반박 |

- 토론 메시지는 관점별 색상으로 구분 (초록/빨강 테두리)
- 토론 완료 후 유저가 관점을 선택 → 해당 톤으로 보고서 작성
- `[토론]` 접두어로 일반 메시지와 구분

#### 2-4. 섹션별 보고서 작성

9개 목차 버튼으로 개별 섹션을 생성합니다. 채팅 인터페이스에서 AI와 대화하며 내용을 다듬을 수 있습니다.

**보고서 목차** (9개 섹션):

| # | 섹션 | 주요 내용 |
|---|------|-----------|
| 1 | Executive Summary | 투자 개요, 핵심 포인트, 투자 추천 요약 |
| 2 | 회사 개요 | 설립 연혁, 비전·미션, 주요 제품/서비스 |
| 3 | 시장/경쟁 | TAM/SAM/SOM, 경쟁사 분석, 진입장벽 |
| 4 | 사업 모델 및 재무 | 수익 구조, 재무 실적/전망, Unit Economics |
| 5 | 팀 및 조직 | 창업자 배경, 핵심 인력, 조직 구조 |
| 6 | 리스크 및 이슈 | 사업·시장·규제·기술 리스크, 이슈 대응 |
| 7 | 밸류에이션 | PER/PSR/EV 기반 적정가치, Peer 비교 |
| 8 | 임팩트 분석 | SDGs 매핑, 이해관계자 분석, IRIS+ 지표 |
| 9 | 투자 의견 | 최종 투자 추천, 조건, 후속 조치 |

- 시스템 프롬프트에 **오늘 날짜가 자동 주입**되어 생성 시점이 항상 정확함
- `[확인 필요]` 마커 — 근거 없는 숫자는 placeholder로 남기고 사실 확인 유도
- 선택한 관점(긍정/비관)의 톤이 전체 보고서에 반영

#### 2-5. 합본 생성 (Report Compilation)

모든 섹션을 하나의 보고서로 합칩니다.

- **전체 생성** — 미작성 섹션을 순차적 스트리밍으로 일괄 생성 (진행률 실시간 표시)
- **개별 생성** — 특정 섹션만 선택하여 생성/재생성
- **인라인 편집** — 각 섹션을 마크다운 에디터로 직접 수정
- **내보내기** — Word (.doc) / Markdown (.md) / 클립보드 복사
- 의사결정 기록 + 토론 내용이 **부록으로 자동 포함**

#### 2-6. 실시간 협업

- **프레즌스 바** — 현재 보고서를 보고 있는 팀원이 아바타로 표시
- DynamoDB 기반 프레즌스 트래킹 (`TEAM#{teamId}#PRESENCE#REPORT#{sessionId}`)
- 세션별 메시지 히스토리 전체 공유

---

### 3. 팀 허브

`/hub` — 팀 전체의 투자심사 현황을 한눈에 관리하는 대시보드.

- **칸반 보드** — 드래그 & 드롭으로 딜 파이프라인 관리 (DnD Kit)
- **문서 체크리스트** — 기업별 필수 서류 제출 현황
- **캘린더** — 심사 일정, 마감일 관리
- **댓글** — 딜별 팀 코멘트
- **활동 로그** — 팀원별 최근 작업 이력
- **AI 브리프** — `/api/ai/collab-brief`로 딜 요약 자동 생성
- Airtable 연동으로 태스크 동기화 (`/api/tasks`)

---

### 4. 펀드 · 기업 관리

**펀드 관리** (`/funds`):
- 운용 중인 펀드 목록, 수익률/성과 지표
- 펀드별 상세 정보 (`/funds/[fundId]`)
- Airtable 연동 데이터

**기업 관리** (`/companies/[companyId]`):
- 투자 대상/포트폴리오 기업 프로필
- 투자 이력, 관련 보고서 연결

---

### 5. Exit 프로젝션

`/exit-projection` — PER/EV 기반 시나리오별 수익률을 계산하고 전문 엑셀을 생성합니다.

**워크플로우:**

1. 투자 조건 입력 (투자금액, 투자단가, 주식수, 순이익 전망 등)
2. **Assumption Pack 생성** — AI가 가정 세트를 자동 구성
3. **AI 자동 검증** — 가정의 합리성을 LLM이 검증, 이상치 경고
4. PER 멀티플별 IRR/Multiple 매트릭스 계산
5. 엑셀 파일 자동 생성 및 다운로드

**3-Tier 프로젝션:**

| 레벨 | 시나리오 | 분석 내용 |
|------|----------|-----------|
| 기본 | 회사제시/심사역제시 | 단순 IRR/멀티플 계산 |
| 고급 | 전체매각 + 부분매각 + NPV | 2단계 Exit 전략, 할인율 적용 |
| 완전 | 기본 + SAFE전환 + 콜옵션 + 부분매각 + NPV | 희석 효과, 옵션 조건 포함 복합 분석 |

**Stash 시스템:**
- `/api/report/[sessionId]/stash` — 가정/계산 결과를 임시 저장
- 여러 시나리오를 비교하며 commit/discard
- 팩트(Facts)와 가정(Assumptions)을 명확히 분리

---

### 6. 배치 추출

`/extract` — 여러 기업의 재무 데이터를 한 번에 추출합니다.

1. PDF 여러 개 업로드 (최대 청크 단위 처리)
2. 비동기 Job으로 백그라운드 처리 (SQS 큐)
3. SSE(Server-Sent Events)로 진행률 실시간 스트리밍
4. 기업별 재무제표·Cap Table 자동 추출
5. 통합 엑셀 / ZIP / Markdown 다운로드

---

### 7. 보고서 초안 · 리뷰

**초안 관리** (`/drafts`):
- 투자심사 보고서 초안 생성/편집/저장
- 마크다운 에디터로 자유 작성
- 채팅 세션의 evidence를 초안에 import (`/api/drafts/[draftId]/import-evidence`)
- 초안별 댓글 (`/api/drafts/[draftId]/comment`)
- 댓글 상태 관리 (해결/미해결)

**리뷰 큐** (`/review`):
- 파싱 경고, 누락 데이터, 기업 alias 불일치 등 플래그 자동 생성
- 건별 claim → resolve/suppress 워크플로우
- 팀원이 리뷰 항목을 가져가서 처리

**이력 관리** (`/history`):
- 팀 전체 활동의 감사 로그
- 페이지네이션으로 시간순 조회

---

### 8. 관리자

`/admin` — 시스템 상태 모니터링.

- SQS 큐 상태 (대기/처리 중 메시지 수)
- AWS 서비스 헬스체크
- Job 처리 현황 (대기/실행/완료/실패)
- `/api/admin/status` — 시스템 전체 상태 JSON
- `/api/health` — Liveness 체크

`/analysis` — Job 분석 및 진단.
- 큐잉된/실행 중/완료된 Job 상세 보기
- 실패 원인 분석, 개별 task retry

---

## 기술 구현

### 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (Client)                      │
│   Next.js 16 App Router · React 19 · Tailwind CSS 4     │
│   Zustand (상태) · TanStack Query (서버 상태) · DnD Kit  │
└────────────────────────┬────────────────────────────────┘
                         │ HTTPS
┌────────────────────────▼────────────────────────────────┐
│              Vercel Serverless (Node.js)                  │
│   Next.js API Routes · NextAuth.js 5 · Zod 4 검증        │
│   59개 API 엔드포인트 · SSE 스트리밍                       │
└───┬──────────┬──────────┬──────────┬───────────────┬────┘
    │          │          │          │               │
    ▼          ▼          ▼          ▼               ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌─────────┐  ┌────────────┐
│Bedrock│ │Dynamo │ │  S3   │ │  SQS    │  │  Firebase  │
│Claude │ │  DB   │ │파일   │ │Job 큐   │  │워크스페이스│
│Sonnet │ │세션   │ │저장   │ │비동기   │  │격리/인증  │
│ 4.5   │ │메시지 │ │       │ │처리     │  │           │
└───────┘ └───────┘ └───────┘ └─────────┘  └────────────┘
```

### 기술 스택

| 레이어 | 기술 | 버전 |
|--------|------|------|
| **프레임워크** | Next.js (App Router, Turbopack) | 16.1.6 |
| **런타임** | React + React DOM | 19.2.3 |
| **언어** | TypeScript | 5.x |
| **스타일** | Tailwind CSS + Typography 플러그인 | 4.x |
| **상태 관리** | Zustand (클라이언트), TanStack Query (서버) | 5.0 / 5.90 |
| **검증** | Zod | 4.3 |
| **인증** | NextAuth.js (Beta) + Google OAuth | 5.0-beta.30 |
| **AI** | AWS Bedrock (Claude Sonnet 4.5) + Anthropic SDK | 3.887 / 0.74 |
| **DB** | AWS DynamoDB (lib-dynamodb) | 3.887 |
| **파일** | AWS S3 + Presigned URLs | 3.887 |
| **큐** | AWS SQS | 3.887 |
| **차트** | Recharts | 3.7 |
| **3D** | Three.js + React Three Fiber + Drei | 0.182 |
| **엑셀** | xlsx (SheetJS) | 0.18 |
| **압축** | archiver (ZIP) | 7.0 |
| **마크다운** | react-markdown + remark-gfm | 10.1 |
| **JWT** | jose | 6.1 |
| **아이콘** | lucide-react | 0.563 |
| **드래그&드롭** | @dnd-kit (core/sortable/utilities) | — |

### 핵심 기술 구현

#### 의사결정 트리 (Decision Tree)

```
[기본 질문 1] → 답변 → [기본 질문 2] → ... → [기본 질문 6]
                                                    ↓
                                          [AI 자동 질문 1] → 답변
                                                    ↓
                                          [AI 자동 질문 2] → ... (최대 5개)
                                                    ↓
                                          MAX_AUTO_BRANCHES 도달
                                                    ↓
                                          🟢🔴 이중 관점 토론 시작
```

- `/api/report/next-branch` — 이전 답변 기반 autoregressive 다음 질문 생성
- `MAX_AUTO_BRANCHES = 5` — 자동 분기 상한, 초과 시 대화 모드 전환
- 트리 시각화: SVG 렌더링, PNG/SVG 내보내기 지원
- `DecisionTree.tsx` — 인터랙티브 트리 컴포넌트 (확장/축소, 편집, 추가)

#### 이중 관점 투자 토론 (Dual-Perspective Debate)

동일 LLM에 다른 시스템 프롬프트를 주입하여 두 캐릭터를 생성:

- **🟢 긍정 메리** — `perspective: "optimistic"` — 투자 매력, 성장 동력, 기회 분석
- **🔴 비관 메리** — `perspective: "pessimistic"` — devil's advocate, 리스크 심층 분석

시스템 프롬프트 주입 방식:
```
[역할: 긍정 메리 🟢]
- 투자건의 긍정적 관점을 대변
- 성장 기회와 투자 매력 강조

[역할: 비관 메리 🔴]
- devil's advocate로 위험 요소 심층 분석
- 경쟁 위협, 최악 시나리오 제시
```

- 3라운드 자동 진행 (긍정 → 비관 반론 → 긍정 재반박)
- `perspective` 필드가 DynamoDB 메시지 메타데이터에 저장
- 토론 완료 후 유저가 관점 선택 → 선택된 톤으로 이후 보고서 전체 생성

#### 합본 생성 (Report Compilation)

```
[전체 생성] 클릭
    ↓
미작성 섹션 탐지 (9개 중 비어있는 것)
    ↓
섹션 1 → 스트리밍 생성 → 완료
    ↓
섹션 2 → 스트리밍 생성 → 완료
    ↓
... (순차 진행, 실시간 진행률 표시)
    ↓
전체 합본 완성 → 편집 → 내보내기
```

- `generateAll()` — 미작성 섹션을 순차적으로 스트리밍 생성
- `generateOne()` — 특정 섹션만 개별 생성/재생성
- 각 섹션은 `/api/report/chat`을 통해 스트리밍, `section` 메타데이터로 구분
- `buildSectionPrompt()` — 오늘 날짜 + 의사결정 기록 + 토론 컨텍스트 자동 주입
- 인라인 마크다운 에디터로 AI 생성물을 즉시 편집 가능
- Word / Markdown / 클립보드로 내보내기

#### 스트리밍 LLM 응답

```
Client (fetch) ←── ReadableStream ←── Bedrock InvokeModelWithResponseStream
                                           ↓
                                      [청크 1][청크 2]...[stop_reason: max_tokens]
                                           ↓
                                      자동 continuation (최대 4회)
                                           ↓
                                      [이어서 생성]...[stop_reason: end_turn]
```

- `InvokeModelWithResponseStreamCommand` — Bedrock 실시간 청크 전송
- `max_tokens` 도달 시 `stop_reason: "max_tokens"` 감지 → 자동 continuation
- 최대 4회 continuation으로 긴 보고서도 끊김 없이 생성
- 클라이언트 disconnect 시 `AbortSignal` 전파 → 불필요한 토큰 소비 방지
- LLM Provider 추상화 (`lib/llm.ts`) — Bedrock/Anthropic 양쪽 지원

#### 문서 파싱 파이프라인 (RALPH)

```
PDF 업로드
    ↓
┌─────────────────────────────────────┐
│ 1차: PyMuPDF 텍스트 추출 (빠름)       │
│   → text_quality 평가               │
│   → is_fragmented 체크              │
│   → text_structure 분석             │
└─────────────┬───────────────────────┘
              │
    품질 OK?──┤── Yes → 결과 반환
              │
              No
              ↓
┌─────────────────────────────────────┐
│ 2차: Amazon Nova Pro 재분석 (정확)    │
│   → Claude Vision API 기반          │
│   → 테이블 구조 보존                  │
│   → 재무제표 자동 감지                │
└─────────────┬───────────────────────┘
              │
    두 소스 비교 → 풍부한 쪽 선택
              ↓
          최종 결과
```

- `/api/ralph/parse` — 문서 파싱
- `/api/ralph/classify` — 문서 종류 자동 분류 (9종)
- `/api/ralph/check` — 문서별 필수 항목 조건 검사
- 품질 지표: `text_quality` (점수), `is_fragmented` (조각화), `text_structure` (구조 유형)

#### 비동기 Job 시스템

대용량 처리를 위한 SQS 기반 비동기 작업 큐.

```
Job 생성 (POST /api/jobs)
    ↓
SQS 큐 등록
    ↓
Worker 처리 (백그라운드)
    ↓
진행률 → SSE 스트리밍 (GET /api/jobs/[jobId]/stream)
    ↓
결과물 → S3 저장 (GET /api/jobs/[jobId]/artifact)
```

- **8가지 Job 유형**: 문서 파싱, 배치 추출, 재무 분석, 보고서 생성 등
- Job당 여러 Task 분할 가능 → 개별 Task retry 지원
- Bulk retry (`/api/jobs/bulk-retry`) — 실패 Job 일괄 재시도
- Artifact 다운로드: 개별 파일 / ZIP 묶음 / Markdown 변환

#### 인증 및 워크스페이스 격리

```
Google OAuth (NextAuth.js 5)
    ↓
Firebase 워크스페이스 매핑
    ↓
팀별 데이터 완전 격리
```

- NextAuth.js 5 (Beta) + Google OAuth Provider
- Firebase `FIREBASE_PROJECT_ID`로 워크스페이스 구분
- DynamoDB 키에 `TEAM#{teamId}` 포함 → 팀 간 데이터 완전 격리
- 세션 기반 API 인가: 모든 API Route에서 세션 검증

#### 실시간 프레즌스

- `/api/presence` — 현재 보고서를 보고 있는 팀원 정보
- `PresenceBar.tsx` — 아바타 + 이름으로 실시간 표시
- DynamoDB TTL 기반 자동 만료
- 키 구조: `TEAM#{teamId}#PRESENCE#REPORT#{sessionId}` → `MEMBER#{memberKey}`

---

## 차별점

### AI를 동료로, 도구가 아닌 관계

MERRY는 "AI가 다 해준다"가 아니라 **"AI와 함께 더 잘한다"**를 추구합니다.

- **의사결정은 사람이**: AI가 질문하고, 사람이 판단. 그 판단이 보고서에 반영됨
- **두 관점 제시**: 결론을 내려주지 않고, 긍정/비관 양면을 보여줘서 사람이 선택
- **편집 가능**: AI 생성물을 그대로 쓰지 않고 편집할 수 있는 구조
- **[확인 필요] 마커**: 근거 없는 숫자는 placeholder로 남기고, 사실 확인을 유도
- **투명한 프로세스**: 의사결정 트리 → 토론 → 보고서 순서로 사고 과정이 추적 가능

### 임팩트 투자에 특화

일반 VC 심사 도구와 달리 **임팩트 투자 프레임워크**가 내장되어 있습니다.

| 프레임워크 | 적용 방식 |
|------------|-----------|
| **UN SDGs** (1~17) | 투자 대상의 SDGs 매핑 및 기여도 분석 |
| **이해관계자 분석** | 수혜자, 고객, 지역사회, 투자자별 영향 평가 |
| **IRIS+** (GIIN) | 글로벌 임팩트 지표 카탈로그 기반 측정 |
| **IMP 5 Dimensions** | What, Who, How Much, Contribution, Risk |

보고서 8번 섹션 "임팩트 분석"에서 이 프레임워크들이 종합적으로 적용됩니다.

### 엔드투엔드 워크플로우 통합

```
📄 문서 업로드 → 🔍 자동 추출/분류 → 🌳 분기 심사 → 🟢🔴 토론
     ↓                                                    ↓
  RALPH 파싱              의사결정이 컨텍스트로 주입 →     📝 섹션 생성
     ↓                                                    ↓
  품질 자동 평가                                        📋 합본 생성
     ↓                                                    ↓
  조건 검사                                     Word/MD 내보내기
```

- 추출된 데이터가 심사에, 심사 결과가 보고서에, 보고서가 합본에 자동 반영
- 하나의 플랫폼에서 문서 수집부터 최종 보고서까지 완결
- 팀 허브에서 전체 딜 파이프라인을 칸반으로 관리

### 팀 협업 내장

- 실시간 프레즌스 — 누가 어떤 보고서를 보고 있는지
- 딜별 댓글·코멘트 시스템
- 리뷰 큐 — 파싱 이상치, 누락 데이터 자동 플래깅
- 활동 로그 — 팀 전체 작업 이력 감사
- AI 브리프 — 딜 요약을 AI가 자동 생성

---

## 프로젝트 구조

```
merry/
├── web/                                # Next.js 웹 애플리케이션
│   ├── src/
│   │   ├── app/
│   │   │   ├── (app)/                  # 인증 필요 페이지들 (18개)
│   │   │   │   ├── report/             # 투자심사 보고서
│   │   │   │   │   ├── page.tsx        #   세션 목록
│   │   │   │   │   ├── new/            #   새 세션 생성
│   │   │   │   │   └── [slug]/         #   보고서 워크스페이스 (채팅+트리+합본)
│   │   │   │   ├── documents/          # RALPH 문서 추출
│   │   │   │   ├── extract/            # 배치 재무 추출
│   │   │   │   ├── exit-projection/    # Exit 프로젝션
│   │   │   │   ├── hub/               # 팀 허브 (칸반+캘린더+댓글)
│   │   │   │   ├── funds/             # 펀드 관리
│   │   │   │   │   └── [fundId]/      #   펀드 상세
│   │   │   │   ├── companies/
│   │   │   │   │   └── [companyId]/   # 기업 프로필
│   │   │   │   ├── drafts/            # 보고서 초안
│   │   │   │   │   └── [draftId]/     #   초안 편집
│   │   │   │   ├── review/            # 리뷰 큐
│   │   │   │   ├── check/             # 문서 조건 검사
│   │   │   │   ├── history/           # 활동 이력
│   │   │   │   ├── analysis/          # Job 분석/진단
│   │   │   │   ├── admin/             # 시스템 관리
│   │   │   │   └── playground/        # 실험 기능
│   │   │   ├── api/                    # API Routes (59개 엔드포인트)
│   │   │   │   ├── auth/              #   인증 (NextAuth, 워크스페이스, 로그아웃)
│   │   │   │   ├── report/            #   보고서 (채팅, 분기, 세션, 메시지, 팩트, 가정, Stash)
│   │   │   │   ├── jobs/              #   비동기 Job (CRUD, 스트리밍, artifact, task retry)
│   │   │   │   ├── ralph/             #   문서 파싱 (parse, classify, check)
│   │   │   │   ├── drafts/            #   초안 (CRUD, 댓글, evidence import)
│   │   │   │   ├── funds/             #   펀드 관리
│   │   │   │   ├── companies/         #   기업 관리
│   │   │   │   ├── review-queue/      #   리뷰 큐 (claim, resolve, suppress)
│   │   │   │   ├── uploads/           #   파일 업로드 (S3 presign, complete)
│   │   │   │   ├── ai/               #   AI 기능 (collab-brief)
│   │   │   │   ├── presence/          #   실시간 프레즌스
│   │   │   │   ├── activity/          #   활동 로그
│   │   │   │   ├── calendar/          #   캘린더
│   │   │   │   ├── comments/          #   댓글
│   │   │   │   ├── tasks/             #   Airtable 태스크
│   │   │   │   ├── docs/              #   팀 문서 인덱스
│   │   │   │   ├── cost/              #   비용 추정
│   │   │   │   ├── admin/             #   시스템 상태
│   │   │   │   └── health/            #   헬스체크
│   │   │   ├── page.tsx               # 로그인 페이지
│   │   │   ├── layout.tsx             # 루트 레이아웃
│   │   │   └── globals.css            # 전역 스타일 (CSS 변수)
│   │   ├── components/
│   │   │   ├── report/
│   │   │   │   ├── DecisionTree.tsx   # 의사결정 트리 (인터랙티브)
│   │   │   │   ├── FactsAssumptionsPanel.tsx  # 팩트/가정 에디터
│   │   │   │   └── PresenceBar.tsx    # 실시간 프레즌스 바
│   │   │   ├── ui/                    # 디자인 시스템
│   │   │   │   ├── Button.tsx
│   │   │   │   ├── Card.tsx
│   │   │   │   ├── Badge.tsx
│   │   │   │   ├── Input.tsx
│   │   │   │   └── Textarea.tsx
│   │   │   ├── Sidebar.tsx            # 메인 사이드바 (240px/68px)
│   │   │   ├── MobileNav.tsx          # 모바일 네비게이션
│   │   │   └── LoginPanel.tsx         # 로그인 패널
│   │   └── lib/
│   │       ├── llm.ts                 # LLM 추상화 (Bedrock/Anthropic)
│   │       ├── reportChat.ts          # 보고서 채팅 저장소 (DynamoDB)
│   │       ├── presenceStore.ts       # 프레즌스 저장소
│   │       └── aws/                   # AWS SDK 클라이언트
│   │           ├── dynamodb.ts
│   │           ├── s3.ts
│   │           └── sqs.ts
│   ├── package.json
│   └── next.config.ts
├── scripts/                            # Exit 프로젝션 Python 스크립트
│   ├── analyze_valuation.py           #   투자검토 엑셀 파싱
│   ├── generate_exit_projection.py    #   기본 Exit 프로젝션
│   ├── generate_advanced_exit_projection.py   #   고급 (부분매각, NPV)
│   └── generate_complete_exit_projection.py   #   완전판 (SAFE, 콜옵션)
├── ralph/                              # 문서 파싱 엔진 (Python)
├── CLAUDE.md                           # Claude Code 가이드
└── README.md
```

---

## API 엔드포인트 전체 목록

### 인증 (Auth)
| Method | 경로 | 설명 |
|--------|------|------|
| `*` | `/api/auth/[...nextauth]` | NextAuth 핸들러 (Google OAuth) |
| `GET/POST` | `/api/auth/workspace` | 워크스페이스 세션 관리 |
| `POST` | `/api/auth/logout` | 로그아웃 |

### 보고서 (Report)
| Method | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/report` | 세션 목록 |
| `POST` | `/api/report/sessions` | 새 세션 생성 |
| `POST` | `/api/report/chat` | LLM 스트리밍 채팅 (perspective 지원) |
| `POST` | `/api/report/next-branch` | Autoregressive 다음 분기 생성 |
| `GET/PATCH` | `/api/report/[sessionId]/meta` | 세션 메타데이터 |
| `GET` | `/api/report/[sessionId]/messages` | 채팅 메시지 목록 |
| `GET` | `/api/report/[sessionId]/facts/latest` | 최신 팩트 |
| `POST` | `/api/report/[sessionId]/facts/build` | 팩트 빌드 |
| `GET` | `/api/report/[sessionId]/assumptions/latest` | 최신 가정 |
| `POST` | `/api/report/[sessionId]/assumptions/save` | 가정 저장 |
| `POST` | `/api/report/[sessionId]/assumptions/suggest` | AI 가정 제안 |
| `POST` | `/api/report/[sessionId]/assumptions/validate` | 가정 검증 |
| `POST` | `/api/report/[sessionId]/assumptions/lock` | 가정 확정 |
| `GET/POST` | `/api/report/[sessionId]/stash` | Stash 목록/생성 |
| `GET/DELETE` | `/api/report/[sessionId]/stash/[itemId]` | Stash 항목 |
| `POST` | `/api/report/[sessionId]/stash/commit` | Stash 커밋 |
| `GET` | `/api/report/[sessionId]/compute/latest` | 최신 계산 결과 |
| `POST` | `/api/report/[sessionId]/compute/exit-projection` | Exit 프로젝션 계산 |

### Job 시스템
| Method | 경로 | 설명 |
|--------|------|------|
| `GET/POST` | `/api/jobs` | Job 목록/생성 |
| `GET/PATCH` | `/api/jobs/[jobId]` | Job 상세/수정 |
| `GET` | `/api/jobs/[jobId]/stream` | SSE 스트리밍 |
| `POST` | `/api/jobs/[jobId]/cancel` | Job 취소 |
| `POST` | `/api/jobs/[jobId]/retry` | Job 재시도 |
| `GET` | `/api/jobs/[jobId]/artifact` | Artifact 다운로드 |
| `GET` | `/api/jobs/[jobId]/artifact/zip` | ZIP 다운로드 |
| `GET` | `/api/jobs/[jobId]/artifact/markdown` | Markdown 변환 |
| `GET` | `/api/jobs/[jobId]/tasks` | Task 목록 |
| `POST` | `/api/jobs/[jobId]/tasks/[taskId]/retry` | Task 재시도 |
| `POST` | `/api/jobs/bulk-retry` | 일괄 재시도 |

### RALPH (문서 파싱)
| Method | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/ralph/parse` | PDF 파싱 |
| `POST` | `/api/ralph/classify` | 문서 분류 |
| `POST` | `/api/ralph/check` | 조건 검사 |

### 초안/리뷰
| Method | 경로 | 설명 |
|--------|------|------|
| `GET/POST` | `/api/drafts` | 초안 목록/생성 |
| `GET/PATCH/DELETE` | `/api/drafts/[draftId]` | 초안 CRUD |
| `POST` | `/api/drafts/[draftId]/comment` | 댓글 추가 |
| `PATCH` | `/api/drafts/[draftId]/comment-status` | 댓글 상태 변경 |
| `POST` | `/api/drafts/[draftId]/apply` | 초안 적용 |
| `POST` | `/api/drafts/[draftId]/import-evidence` | Evidence 임포트 |

### 리뷰 큐
| Method | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/review-queue` | 리뷰 대기열 |
| `POST` | `/api/review-queue/[queueId]/claim` | 리뷰 가져가기 |
| `POST` | `/api/review-queue/[queueId]/resolve` | 해결 완료 |
| `POST` | `/api/review-queue/[queueId]/suppress` | 무시 처리 |

### 기타
| Method | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/funds` | 펀드 목록 |
| `GET` | `/api/funds/[fundId]` | 펀드 상세 |
| `GET` | `/api/companies/[companyId]` | 기업 상세 |
| `POST` | `/api/uploads/presign` | S3 Presigned URL |
| `POST` | `/api/uploads/complete` | 업로드 완료 |
| `POST` | `/api/ai/collab-brief` | AI 협업 브리프 |
| `GET/POST` | `/api/presence` | 프레즌스 |
| `GET` | `/api/activity` | 활동 로그 |
| `GET/POST` | `/api/calendar` | 캘린더 |
| `GET/POST` | `/api/comments` | 댓글 |
| `GET` | `/api/tasks` | Airtable 태스크 |
| `GET` | `/api/docs` | 문서 인덱스 |
| `POST` | `/api/cost/estimate` | 비용 추정 |
| `GET` | `/api/admin/status` | 시스템 상태 |
| `GET` | `/api/health` | 헬스체크 |

---

## 로컬 개발

```bash
# 의존성 설치
cd web && npm install

# 환경변수 설정
cp .env.example .env.local
# .env.local에 필요한 값 채우기

# 개발 서버 시작
npm run dev
# http://localhost:3500
```

### 필수 환경변수

| 변수 | 설명 | 예시 |
|------|------|------|
| `LLM_PROVIDER` | LLM 제공자 | `bedrock` 또는 `anthropic` |
| `BEDROCK_MODEL_ID` | Bedrock 모델 ID | `global.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| `AWS_ACCESS_KEY_ID` | AWS 인증 키 | — |
| `AWS_SECRET_ACCESS_KEY` | AWS 시크릿 키 | — |
| `AWS_REGION` | AWS 리전 | `ap-northeast-2` |
| `MERRY_DDB_TABLE` | DynamoDB 테이블명 | `merry-prod` |
| `MERRY_S3_BUCKET` | S3 버킷명 | `merry-files` |
| `FIREBASE_PROJECT_ID` | Firebase 프로젝트 ID | — |
| `AUTH_SECRET` | NextAuth 시크릿 | (임의 문자열) |
| `GOOGLE_CLIENT_ID` | Google OAuth 클라이언트 ID | — |
| `GOOGLE_CLIENT_SECRET` | Google OAuth 시크릿 | — |

---

## 배포

```bash
# 프로젝트 루트에서 실행 (web/ 아닌 merry/)
cd /path/to/merry

# Vercel 프로덕션 배포
npx vercel --prod --archive=tgz

# 프로덕션 URL alias
npx vercel alias set <deployment-url> mysc-merry-inv.vercel.app
```

> **주의**: `web/` 디렉토리가 아닌 **프로젝트 루트**에서 `vercel` 명령을 실행해야 합니다.

---

## 팀

**MYSC AX솔루션** — MERRY는 MYSC의 AX(AI Transformation) 챔피언들이 만든 투자심사 AI 동료입니다.

MERRY라는 이름은 실제 투자심사역 선배 메리에서 따왔어요. 선배의 경험과 판단력을 AI로 증강하여, 심사역들이 더 깊이 있는 투자 판단을 할 수 있도록 돕는 것이 목표입니다.

---

## 라이선스

Proprietary — MYSC AX솔루션

**문의**: mwbyun1220@mysc.co.kr
