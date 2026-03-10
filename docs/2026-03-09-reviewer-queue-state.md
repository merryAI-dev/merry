# Reviewer Queue State 정의

작성일: 2026-03-09

## 목적

Reviewer queue는 "자동 판정 결과를 바로 믿기 어려운 건"만 사람이 검토하게 만드는 장치다.

## Queue 진입 조건

아래 중 하나라도 만족하면 queue에 들어간다.

- `parse_warning` 존재
- `company_group_alias_from` 존재
- `company_group_key` 미인식
- `error` 존재
- evidence가 비어 있거나 너무 짧음
- rule 기반 결과와 LLM 결과가 충돌
- reviewer가 이전에 `ambiguous` 또는 `incorrect`로 표시한 정책/문서 조합

## 상태

### `queued`

- 시스템이 검토 필요로 분류했지만 사람이 아직 열어보지 않음

### `in_review`

- reviewer가 열람 중
- 다른 reviewer가 중복 수정하지 않도록 soft lock 가능

### `resolved_correct`

- 자동 판정이 맞다고 reviewer가 확인
- goldset / evaluator 입력으로 재사용 가능

### `resolved_incorrect`

- 자동 판정이 틀렸다고 reviewer가 확인
- policy false positive / false negative backlog에 반영

### `resolved_ambiguous`

- 문서 근거만으로 단정하기 어렵거나 정책 해석이 애매함
- rule 개선보다 policy definition 정리가 먼저 필요한 상태

### `suppressed`

- 같은 유형의 반복 경고를 운영자가 일시적으로 무시
- suppression reason과 만료일 필요

## 우선순위

우선순위는 아래 순서로 정한다.

1. 고객 제출 문서
2. `error` 또는 no-result 케이스
3. `company recognition` 실패
4. `alias correction` 발생
5. `parse_warning`
6. evidence 부족

## 저장 필드 초안

- `queueId`
- `teamId`
- `jobId`
- `taskId`
- `fileId`
- `filename`
- `companyGroupKey`
- `policyId`
- `policyText`
- `queueReason`
- `severity`
- `status`
- `autoResult`
- `reviewedResult`
- `reviewComment`
- `assignedTo`
- `createdAt`
- `updatedAt`
- `resolvedAt`

## API / 화면 초안

### API

- `GET /api/review-queue`
- `POST /api/review-queue/[queueId]/claim`
- `POST /api/review-queue/[queueId]/resolve`
- `POST /api/review-queue/[queueId]/suppress`

### 화면

- `web/src/app/(app)/review/page.tsx`
- 필터:
  - reason
  - severity
  - assignedTo
  - policyId
  - companyGroupKey

## SLA 초안

- `error`: 영업일 기준 4시간
- `company recognition` 실패: 1일
- `parse_warning`: 2일
- `alias correction`: 2일
- evidence 부족: 2일

## 출시 전 최소 구현

- queue 생성 규칙
- 목록 화면
- resolve correct / incorrect / ambiguous
- reviewer comment 저장
- goldset export 연결
