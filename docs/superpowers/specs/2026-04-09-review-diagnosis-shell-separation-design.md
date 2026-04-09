# 투자심사 · 현황진단 제품 쉘 및 DynamoDB 분리 설계

- 날짜: 2026-04-09
- 상태: 승인된 설계
- 범위: `web` 앱의 제품 UX 경계, API 경계, DynamoDB 경계 재설계

## 1. 문제 정의

현재 Merry는 로그인 이후 공용 앱 쉘 아래에서 `투자심사(report)`와 `현황진단(diagnosis)`이 섞여 보인다.

- 사용자 관점에서는 서로 다른 업무가 같은 제품의 하위 탭처럼 느껴진다.
- 현황진단은 범용 `analysis` 화면의 job type 중 하나로 노출되어 제품 정체성이 약하다.
- 저장소 관점에서는 단일 DynamoDB 테이블과 prefix 기반 구분에 의존해, 기능 경계가 UI보다 더 약하다.

이 구조는 UX 혼선과 데이터 경계 오염 가능성을 동시에 만든다.

## 2. 목표

- 로그인과 팀 선택까지만 공유하고, 진입 후에는 `투자심사`와 `현황진단`을 완전히 다른 제품처럼 보이게 만든다.
- 두 제품은 서로 다른 홈, 내비게이션, 세션 모델, 활동 흐름을 가진다.
- DynamoDB는 prefix 분리가 아니라 별도 테이블로 물리 분리한다.
- Bedrock, 인증, 공통 업로드/파싱 유틸은 공유 인프라로 유지한다.

## 3. 비목표

- Bedrock 클라이언트 또는 모델 구성을 제품별로 분리하지 않는다.
- 로그인 시스템과 팀/워크스페이스 모델은 분리하지 않는다.
- 이번 설계에서 서브도메인 기반 멀티앱 구조로 확대하지 않는다.
- 기존 데이터를 한 번에 전량 마이그레이션하지 않는다.

## 4. 선택한 접근

채택안은 `한 앱, 두 제품 쉘`이다.

- 공유 구간
  - `/` 로그인
  - `/workspace/select` 팀/워크스페이스 선택
  - `/products` 제품 선택
- 투자심사 제품 쉘
  - `/review`
  - `/review/new`
  - `/review/[slug]`
  - `/review/queue`
  - `/review/history`
- 현황진단 제품 쉘
  - `/diagnosis`
  - `/diagnosis/upload`
  - `/diagnosis/sessions`
  - `/diagnosis/[sessionId]`
  - `/diagnosis/history`

이 접근은 사용자에게는 제품 분리를 강하게 전달하면서, 운영 측면에서는 인증과 공통 인프라를 계속 공유할 수 있다.

## 5. UX 설계

### 5.1 공통 진입 경험

- 로그인 성공 후 팀/워크스페이스를 선택한다.
- 이후 `/products`에서 `투자심사` 또는 `현황진단` 중 하나를 선택한다.
- 제품 선택 이후에는 선택한 제품의 전용 쉘로 진입한다.

### 5.2 투자심사 UX

투자심사는 분석 워크벤치 성격으로 설계한다.

- 핵심 목적: 딜 검토, 시장 근거 수집, 가정 관리, 계산 검증, 초안 작성
- 핵심 내비게이션: `세션`, `새 보고서`, `검토 큐`, `히스토리`
- 시각 톤: 정보 밀도가 높고 비교가 쉬운 작업형 레이아웃
- 기본 단위: 채팅과 문서 근거가 결합된 세션

### 5.3 현황진단 UX

현황진단은 단계형 진단 스튜디오 성격으로 설계한다.

- 핵심 목적: 진단시트 업로드, 항목 점검, 초안 생성, 엑셀 반영
- 핵심 내비게이션: `진단 시작`, `진단 세션`, `업로드 이력`, `히스토리`
- 시각 톤: 진행 상태와 다음 액션이 명확한 워크플로 중심 레이아웃
- 기본 단위: 업로드/초안/산출물 상태가 중심인 작업 세션

### 5.4 UI/UX 원칙

- 한 화면에는 하나의 주 액션만 둔다.
- 모바일 top-level navigation은 제품별 4개 이내로 제한한다.
- `analysis` 같은 범용 작업장 개념은 사용자에게 노출하지 않는다.
- 투자심사는 탐색과 비교 중심, 현황진단은 업로드와 진행률 중심으로 레이아웃을 구분한다.

## 6. 세션 모델

### 6.1 투자심사 세션

투자심사 세션은 현재 `report` 흐름을 기반으로 유지하되, 제품명과 라우트를 `review`로 정렬한다.

- 세션 ID: 초기 전환 단계에서는 기존 `report_` 세션 ID를 내부 호환 키로 유지한다. 다만 신규 웹 표면, URL, 버튼 라벨, API namespace에서는 모두 `review`만 노출한다.
- 저장 대상
  - 메시지
  - 파일 컨텍스트
  - assumption pack
  - fact pack
  - stash
  - compute snapshot
  - presence
  - activity log
- 흐름: `세션 생성 → 업로드 → 대화/가정 정리 → 계산/검토 → 초안 확정`

### 6.2 현황진단 세션

현황진단은 범용 job 실행이 아니라 진단 전용 작업 세션 모델로 전환한다.

- 저장 대상
  - 세션 메타데이터
  - 업로드된 진단 엑셀 정보
  - 드래프트 메타데이터
  - 진행 단계와 상태
  - 생성된 산출물 메타데이터
  - activity log
- 흐름: `엑셀 업로드 또는 드래프트 시작 → 항목 점검 → 진단 생성/수정 → 결과 엑셀 반영`
- 사용자가 보는 모델은 워크플로 세션이며, 내부적으로 LLM이 사용되더라도 채팅 제품처럼 보이지 않게 한다.

## 7. DynamoDB 및 저장소 설계

### 7.1 테이블 분리

- 투자심사 전용 테이블: `MERRY_REVIEW_DDB_TABLE`
- 현황진단 전용 테이블: `MERRY_DIAGNOSIS_DDB_TABLE`

원칙:

- `review` 제품의 모든 세션성 데이터는 review 테이블만 사용한다.
- `diagnosis` 제품의 모든 세션성 데이터는 diagnosis 테이블만 사용한다.
- 같은 워크스페이스를 공유하더라도 제품 간 테이블 공유는 없다.

### 7.2 Store 계층 분리

공용 `getDdbTableName()` 의존 구조를 제품별 resolver로 바꾼다.

- `getReviewDdbTableName()`
- `getDiagnosisDdbTableName()`

Store도 제품별로 분리한다.

- review stores
  - review session store
  - review chat store
  - review assumptions/facts/compute/stash store
  - review activity/presence store
- diagnosis stores
  - diagnosis session store
  - diagnosis upload/result store
  - diagnosis workflow state store
  - diagnosis activity store

## 8. API 경계

API는 제품 namespace를 명시적으로 나눈다.

- 투자심사: `/api/review/...`
- 현황진단: `/api/diagnosis/...`

공유 API는 제품 비중립적일 때만 유지한다.

- 공유 유지 대상
  - 인증
  - 워크스페이스 컨텍스트
  - 파일 업로드 presign/complete
  - 공통 파싱 유틸
- 단계적 정리 대상
  - 기존 `/api/report/...`
  - 기존 `/api/jobs` 내부의 `diagnosis_analysis`

현황진단은 더 이상 `analysis` 내부 `jobType` 하나로 노출하지 않는다.

## 9. 공통 인프라 경계

공유를 유지하는 것은 다음뿐이다.

- AWS 계정/기본 인증
- Bedrock service layer
- S3 업로드 파일 저장소
- 공통 문서 파싱 유틸
- 워크스페이스/팀 컨텍스트

즉, 인프라는 공유하지만 제품 세션과 제품 상태는 공유하지 않는다.

## 10. 라우팅 및 레이아웃 구조

현재 공용 `(app)` 레이아웃에서 모든 제품을 한 내비게이션으로 노출하는 구조를 해체한다.

목표 구조:

- 공용 앱 레이아웃
  - 인증 확인
  - 워크스페이스 주입
  - 제품 선택 진입
- review 전용 레이아웃
  - review sidebar
  - review mobile nav
  - review page chrome
- diagnosis 전용 레이아웃
  - diagnosis sidebar
  - diagnosis mobile nav
  - diagnosis page chrome

이렇게 하면 제품별 정보구조와 톤을 공용 메뉴 제약 없이 설계할 수 있다.

## 11. 마이그레이션 전략

점진 이전을 기본 전략으로 한다.

### 11.1 신규 쓰기 우선 분리

- 신규 `review` 경로는 review 테이블에만 기록한다.
- 신규 `diagnosis` 경로는 diagnosis 테이블에만 기록한다.

### 11.2 기존 경로 호환

- 기존 `/report`는 1차 전환 단계에서 전부 `/review`로 리다이렉트한다. 필요한 경우 내부에서만 legacy handler를 호출하는 얇은 호환 레이어를 유지하되, 사용자에게는 `/report`를 더 이상 노출하지 않는다.
- 기존 `analysis`의 `diagnosis_analysis`는 신규 진단 UX 오픈 후 사용자 노출을 제거하고, 내부 fallback만 잠시 유지한다.

### 11.3 레거시 데이터

- 기존 단일 테이블 데이터를 일괄 이관하지 않는다.
- 기존 단일 테이블 데이터는 즉시 일괄 이전하지 않는다. review에서 필요한 기록만 선택 이관하고, 미이관 기록은 read-only legacy adapter로만 조회한다. 신규 쓰기는 절대 legacy 테이블로 보내지 않는다.
- diagnosis는 신규 진입분부터 새 테이블에만 쓰도록 하여 경계를 먼저 깨끗하게 만든다.

## 12. 구현 순서 제안

1. 제품 선택 화면과 제품별 레이아웃 도입
2. 공용 내비에서 제품별 내비로 분리
3. review/diagnosis DDB env 및 store resolver 분리
4. review API namespace 정렬
5. diagnosis 전용 session/API/store 도입
6. 기존 `analysis`의 diagnosis 경로 숨김 및 fallback 축소
7. 레거시 `/report` 호환 정리

## 13. 테스트 전략

- 라우팅 테스트
  - 로그인 후 제품 선택 진입 확인
  - `/review/*`, `/diagnosis/*`의 전용 레이아웃 적용 확인
- 저장소 테스트
  - review API가 review 테이블만 조회/쓰기 하는지 확인
  - diagnosis API가 diagnosis 테이블만 조회/쓰기 하는지 확인
- 회귀 테스트
  - 기존 투자심사 세션 열기/생성/저장 흐름 확인
  - 현황진단 엑셀 업로드/초안/산출물 흐름 확인
- UX 테스트
  - 모바일에서 제품별 nav가 4개 이내인지 확인
  - 제품 전환 시 용어와 빈 상태가 섞이지 않는지 확인

## 14. 성공 기준

- 로그인 이후 사용자가 `투자심사`와 `현황진단`을 다른 제품처럼 인지한다.
- 현황진단이 더 이상 범용 분석 잡 화면에 종속되지 않는다.
- review 데이터와 diagnosis 데이터가 서로 다른 DynamoDB 테이블에만 기록된다.
- Bedrock과 공통 유틸은 공유되지만 제품 세션 상태는 섞이지 않는다.
