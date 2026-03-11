# RALPH 상용화 실행 플랜

작성일: 2026-03-09  
대상: 제품/엔지니어링/운영 공통  
범위: `condition_check`, `parse`, fan-out batch processing, reviewer workflow

## 1. 목적

RALPH를 "기술 데모"가 아니라 실제 심사팀이 반복적으로 사용할 수 있는 상용 제품으로 전환한다.

이번 계획의 기준은 세 가지다.

1. 결과가 맞아야 한다.
2. 700-800개 파일 배치를 안정적으로 처리해야 한다.
3. 사람이 결과를 신뢰하고 검토할 수 있어야 한다.

## 1.1 실행 보드

현재 문서는 논의 메모가 아니라 실행 플랜으로 관리한다.

### 완료

- [x] 기업 그룹/alias 보정 관찰성 구현
- [x] `800` 파일 fake infra e2e 기준 확보
- [x] alias encoder 도입
- [x] 상용화 실행 플랜 문서화
- [x] 골드셋 스키마 초안 추가
- [x] 정확도 evaluator 초안 추가
- [x] condition soak runner 초안 추가
- [x] reviewer queue 상태 정의 초안 추가

### 이번 주 필수

- [ ] `main` 기준 stacked PR 정리
- [ ] 골드셋 샘플 30건 입력
- [ ] evaluator로 정책 5개 baseline 측정
- [ ] staging 50파일 soak run 1회 실행
- [ ] reviewer queue API/화면 skeleton 추가

### 출시 전 필수

- [ ] 골드셋 100-200건 구축
- [ ] 정책 20-30개 accuracy report 확보
- [ ] staging 800파일 soak run 3회 연속 성공
- [ ] reviewer queue와 기업 워크스페이스 배포
- [ ] quota / audit / retention / alerting 배포

## 2. 현재 상태 요약

이미 구현된 것:

- 자연어 조건 검사 fan-out 처리
- `800` 파일 기준 fake infra e2e 테스트
- `parse_warning`, cache hit, rule/LLM count, company grouping 관찰성
- truncated company alias merge encoder
- history/check 화면에서 기업 그룹 및 alias 보정 observability

아직 부족한 것:

- staging/prod 수준의 대용량 soak run 검증
- 정책별 정확도 기준과 골드셋
- reviewer가 쓰는 검토 필요 큐와 기업 단위 워크스페이스
- quota, audit log, retention, alerting 같은 운영 통제
- 실제 파일럿 운영 문서와 장애 runbook

## 3. 상용화 기준

출시는 아래 항목이 모두 충족되어야 한다.

### 3.1 정확도 기준

- 핵심 정책 20-30개에 대해 골드셋이 존재한다.
- 핵심 정책군의 precision이 팀 합의 기준 이상이다.
- false positive 상위 케이스가 정리되어 있다.
- reviewer disagreement 사례가 별도로 기록된다.

### 3.2 배치 처리 기준

- staging에서 `50 -> 200 -> 800` 파일 soak run이 반복 성공한다.
- silent failure가 없다.
- stuck job이 없다.
- retry 이후 상태 불일치가 없다.
- cache hit, parse warning, alias merge가 job metric으로 남는다.

### 3.3 제품 신뢰 기준

- 각 판정에 근거가 남는다.
- parse warning과 alias correction 여부가 노출된다.
- 기업 단위로 문서를 묶어 볼 수 있다.
- 애매함/충돌 건은 reviewer queue로 분리된다.

### 3.4 운영 기준

- 팀별 quota와 rate limit이 적용된다.
- audit log가 남는다.
- artifact retention/deletion 정책이 문서화되어 있다.
- DLQ/알람/장애 대응 runbook이 준비되어 있다.

## 4. 출시 전 필수 트랙

## 4.1 트랙 A: 정확도 계약 만들기

목표:

- 자연어 정책을 "측정 가능한 제품 기능"으로 바꾼다.

구현 항목:

- `policy_templates` 개념 추가
  - 예: `업력 3년 미만`, `매출 10억 미만`, `중소기업 인증 보유`, `벤처기업 확인서 보유`
  - 자유 입력만 두지 말고 템플릿/버전 관리가 가능해야 한다.
- 골드셋 구축
  - 파일 100-200개
  - 기업별 문서 묶음
  - 정책별 expected result와 evidence span
- evaluator 스크립트 추가
  - 후보 파일: `scripts/eval_condition_accuracy.py`
  - 입력: 골드셋 manifest + 정책 템플릿
  - 출력: precision, recall, false positive 목록, ambiguous 사례
- 규칙 우선 판정 강화
  - `ralph/condition_checker.py`
  - 숫자/기간/날짜 기반 조건을 rule-first로 처리
- 회사명 인식 개선
  - `ralph/company_encoder.py`
  - alias 사전 저장
  - filename, nearby field, registration field를 함께 사용하는 resolver 추가

완료 기준:

- 정책별 성능 리포트가 재현 가능하다.
- false positive top 10이 문서화되어 있다.
- reviewer가 "이 정책은 어느 수준까지 믿어도 되는지" 알 수 있다.

## 4.2 트랙 B: 800파일 운영 안정화

목표:

- 실제 운영 환경에서 대량 배치를 안전하게 소화한다.

구현 항목:

- staging soak runner 추가
  - 후보 파일: `scripts/run_condition_soak.py`
  - 기능:
    - 파일 업로드
    - job 생성
    - job polling
    - artifact 수집
    - metrics snapshot 저장
- soak test 단계화
  - Stage 1: 50 files
  - Stage 2: 200 files
  - Stage 3: 800 files
- worker throughput 계측
  - `worker/main.py`
  - 저장할 메트릭:
    - wall time
    - queue latency
    - rule hit ratio
    - result cache hit
    - parse cache hit
    - alias merge count
    - parse warning count
    - retry count
- retry / stuck monitoring
  - assembly timeout
  - task orphan detection
  - dead letter queue 연결
- artifact integrity 검사
  - CSV, JSON, XLSX row count consistency
  - missing file detection

완료 기준:

- 800파일 soak run 3회 연속 성공
- 결과 row count mismatch 0건
- 재시도 후 stuck job 0건
- 실패 시 원인 파악 가능한 로그와 메트릭 존재

## 4.3 트랙 C: Reviewer workflow 완성

목표:

- 사람이 결과를 소비하고 수정할 수 있는 제품으로 만든다.

구현 항목:

- 검토 필요 큐 추가
  - 조건:
    - parse warning 존재
    - rule/LLM 충돌
    - evidence 부족
    - company recognition 실패
    - alias correction 발생
  - 후보 화면: `web/src/app/(app)/review/page.tsx`
- 기업 단위 워크스페이스 추가
  - 한 기업의 문서 묶음, 조건 결과, parse facts를 한 화면에 모아 본다.
  - 후보 화면: `web/src/app/(app)/companies/[groupKey]/page.tsx`
- delta rerun
  - 문서가 변경되었거나 정책 버전이 바뀐 건만 다시 돌린다.
  - `web/src/lib/jobStore.ts`, `worker/main.py`
- reviewer feedback capture
  - `맞음 / 틀림 / 애매함`
  - 다음 evaluator와 rule 개선 입력으로 축적
- 정책 템플릿 UI
  - 자유 입력은 남기되, 운영 정책은 템플릿으로 고정한다.

완료 기준:

- reviewer가 파일이 아니라 기업 단위로 판단할 수 있다.
- 검토 대상만 별도로 볼 수 있다.
- feedback이 데이터로 축적된다.

## 4.4 트랙 D: 보안/운영/사업화 가드레일

목표:

- 실제 팀이 써도 비용과 데이터가 통제되는 상태를 만든다.

구현 항목:

- quota / budget mode
  - 팀별 일일 파일 수
  - 동시 실행 job 수
  - 월간 토큰 예산
- audit log
  - 누가 어떤 파일로 어떤 정책을 실행했는지
  - 누가 다운로드/재시도/삭제했는지
- retention policy
  - 원본 문서 보관 기간
  - artifact 보관 기간
  - 삭제 요청 처리 절차
- auth hardening
  - workspace 인증 미통과 route 재점검
  - admin-only route 정리
- 운영 알람
  - queue backlog
  - failed batch ratio
  - parse failure surge
  - S3 artifact write failure

완료 기준:

- 팀 단위 사용량 제한이 작동한다.
- 모든 상용 이벤트가 audit 가능하다.
- 장애/비용 폭주 시 운영자가 개입할 수 있다.

## 5. 6주 실행 순서

## Week 1: main 정리와 정확도 기반 만들기

- stacked PR merge 완료
- `main` 기준 lint/typecheck/test baseline 고정
- 골드셋 스키마 설계
- 정책 템플릿 초안 작성
- evaluator 스크립트 뼈대 추가

산출물:

- `main` green
- 골드셋 manifest 초안
- 정책 템플릿 v0
- `scripts/eval_condition_accuracy.py`
- `scripts/run_condition_soak.py`
- reviewer queue state spec

## Week 2: 정확도 계측과 rule 강화

- 골드셋 1차 수집
- 핵심 정책 10개 평가 실행
- false positive top cases 정리
- alias resolver 보강
- evidence normalization 개선

산출물:

- accuracy report v1
- false positive backlog

## Week 3: soak run과 운영 계측

- staging soak runner 구현
- 50/200/800 파일 실행
- job/task/worker metrics 정리
- CSV/JSON/XLSX consistency checker 추가

산출물:

- soak report v1
- 병목 구간 목록

## Week 4: reviewer workflow

- 검토 필요 큐 구현
- 기업 단위 워크스페이스 구현
- alias correction / parse warning / evidence 부족 배지 노출
- reviewer feedback 저장

산출물:

- reviewer workflow v1
- ambiguous case triage 화면

## Week 5: 운영 가드레일

- quota, rate limit, audit log
- retention policy 구현
- DLQ/알람/runbook 정리
- staging disaster drill 1회

산출물:

- ops runbook
- security/retention checklist

## Week 6: closed beta

- 내부 또는 파일럿 고객 1-2팀 온보딩
- 실제 문서 배치 운영
- error review, UX friction review
- go/no-go 판단

산출물:

- beta report
- launch decision memo

## 6. 구현 단위 백로그

우선순위는 `P0 -> P1 -> P2` 순이다.

### P0

- 골드셋 manifest와 evaluator 추가
- staging 800파일 soak runner 추가
- reviewer queue 추가
- quota / audit log 추가
- runbook 작성

### P1

- 기업 워크스페이스 추가
- delta rerun 추가
- alias dictionary persistence
- evidence span normalization

### P2

- 정책 추천
- 고급 문서 중복 클러스터링
- 운영 대시보드 고도화

## 7. 파일 단위 구현 제안

신규 또는 주요 변경 후보 파일:

- `scripts/eval_condition_accuracy.py`
- `scripts/run_condition_soak.py`
- `data/ralph_goldset/manifest.jsonl`
- `ralph/company_encoder.py`
- `ralph/condition_checker.py`
- `worker/main.py`
- `web/src/app/(app)/review/page.tsx`
- `web/src/app/(app)/companies/[groupKey]/page.tsx`
- `web/src/app/(app)/policies/page.tsx`
- `web/src/lib/jobStore.ts`
- `docs/ralph-ops-runbook.md`

## 8. 의사결정이 필요한 항목

- 상용화 1차 정책 범위를 어디까지 가져갈지
- 원본 문서 보관 기간을 몇 일로 둘지
- reviewer correction을 product truth로 바로 반영할지, 큐레이션 후 반영할지
- closed beta를 내부팀 먼저 할지, 외부 파일럿 고객부터 할지

## 9. 바로 시작할 일

이번 주에 바로 해야 할 일은 아래 다섯 개다.

1. `main` 기준 stacked PR 정리와 baseline 고정
2. 골드셋 manifest 스키마 정의
3. `scripts/eval_condition_accuracy.py` 초안 작성
4. `scripts/run_condition_soak.py` 초안 작성
5. reviewer queue의 상태 정의서 작성

현재 저장소 기준 산출물:

- [docs/2026-03-09-ralph-commercialization-plan.md](/Users/boram/merry/docs/2026-03-09-ralph-commercialization-plan.md)
- [data/ralph_goldset/README.md](/Users/boram/merry/data/ralph_goldset/README.md)
- [data/ralph_goldset/manifest.schema.json](/Users/boram/merry/data/ralph_goldset/manifest.schema.json)
- [data/ralph_goldset/manifest.sample.jsonl](/Users/boram/merry/data/ralph_goldset/manifest.sample.jsonl)
- [scripts/eval_condition_accuracy.py](/Users/boram/merry/scripts/eval_condition_accuracy.py)
- [scripts/run_condition_soak.py](/Users/boram/merry/scripts/run_condition_soak.py)
- [docs/2026-03-09-reviewer-queue-state.md](/Users/boram/merry/docs/2026-03-09-reviewer-queue-state.md)

## 10. 최종 판단 기준

다음 질문에 모두 "예"라고 답할 수 있어야 상용화한다.

- 이 정책 결과를 reviewer가 수치로 신뢰할 수 있는가?
- 800파일 배치를 운영자가 불안 없이 돌릴 수 있는가?
- 실패했을 때 원인을 바로 찾을 수 있는가?
- 고객 데이터를 다루는 데 필요한 통제가 준비되었는가?
- 팀이 다음 분기 동안 유지보수 가능한 구조인가?
