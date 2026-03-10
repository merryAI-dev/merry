# RALPH 조건 Fan-out Soak 리포트

작성일: 2026-03-10
브랜치: `pr/web-ops-shell`
적용한 worker 수정: `799e377` `fix(worker): retry ddb transaction conflicts on fan-out completion`

## 범위

이 문서는 현재 브랜치 코드 기준으로, RALPH `condition_check` fan-out 흐름을 격리된 로컬 환경에서 soak 실행한 결과를 정리한 문서입니다.

- 데이터셋: `/Users/boram/merry/companyData`
- 검사 조건:
  - `업력 3년 미만`
  - `매출 10억 미만`
- 실행 환경:
  - 로컬 Next.js 앱
  - 로컬 현재 worker
  - 임시 격리 SQS queue
  - 공용 S3 / DynamoDB 백엔드

## 왜 격리 환경에서 실행했는가

공유 preview 환경에서는 `condition_check` job 생성 자체는 정상적으로 되었지만, 실제 배포된 worker가 구버전이라 아래 오류로 실패했습니다.

`RuntimeError: Unsupported job type: condition_check`

즉, web/API는 최신 코드였지만 queue consumer worker가 현재 브랜치와 맞지 않았습니다. 이 상태에서 공유 worker를 바로 바꾸기보다, 현재 브랜치 코드가 실제로 동작하는지 먼저 검증하기 위해 격리된 로컬 환경에서 soak를 다시 수행했습니다.

## 전체 요약

| 단계 | Job ID | 파일 수 | 상태 | Fan-out 상태 | 성공 | 실패 | Result Cache Hit | Parse Cache Hit | Rule Count | LLM Count | Saved Tokens |
| --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 50 | `711d210aa8b140e0` | 50 | `succeeded` | `succeeded` | 50 | 0 | 34 | 1 | 16 | 84 | 382,530 |
| 200 | `49fbf4db172d40af` | 200 | `succeeded` | `succeeded` | 200 | 0 | 183 | 0 | 78 | 322 | 2,107,790 |
| 800 | `a0a901d01bf142c4` | 800 | `succeeded` | `succeeded` | 800 | 0 | 784 | 0 | 309 | 1,291 | 9,180,232 |

## 상세 결과

### 50개 실행

- 리포트: `/Users/boram/merry/temp/soak/condition_soak_local_50_retryfix.json`
- Job 생성 시간: `820 ms`
- 업로드 시간:
  - presign 총합: `1,329 ms`
  - upload 총합: `17,916 ms`
  - complete 총합: `3,276 ms`
- 기업 인식 결과:
  - 인식됨: `46`
  - 인식 안 됨: `4`
  - 기업 그룹 수: `2`
- 산출물 크기:
  - XLSX: `11,230 bytes`
  - CSV: `15,787 bytes`
  - JSON: `97,969 bytes`

### 200개 실행

- 리포트: `/Users/boram/merry/temp/soak/condition_soak_local_200.json`
- Job 생성 시간: `2,980 ms`
- 업로드 시간:
  - presign 총합: `3,514 ms`
  - upload 총합: `70,076 ms`
  - complete 총합: `10,534 ms`
- 기업 인식 결과:
  - 인식됨: `200`
  - 인식 안 됨: `0`
  - 기업 그룹 수: `3`
- 산출물 크기:
  - XLSX: `22,551 bytes`
  - CSV: `75,273 bytes`
  - JSON: `449,612 bytes`

### 800개 실행

- 리포트: `/Users/boram/merry/temp/soak/condition_soak_local_800.json`
- Job 생성 시간: `13,320 ms`
- 업로드 시간:
  - presign 총합: `12,912 ms`
  - upload 총합: `285,056 ms`
  - complete 총합: `43,605 ms`
- 기업 인식 결과:
  - 인식됨: `800`
  - 인식 안 됨: `0`
  - 기업 그룹 수: `3`
- 산출물 크기:
  - XLSX: `64,300 bytes`
  - CSV: `299,476 bytes`
  - JSON: `1,687,286 bytes`

## 핵심 관찰

- 현재 브랜치 코드는 `50`, `200`, `800` 파일 fan-out을 모두 성공적으로 완료했습니다.
- 이번 worker retry 수정은 실제 효과가 있었습니다. 수정 전에는 DynamoDB transaction conflict 때문에 fan-out 완료 구간에서 일부 task가 실패했지만, 수정 후에는 같은 경로가 정상 완료됐습니다.
- 배치가 커질수록 result cache 재사용 효과가 크게 나타났습니다.
  - 200개 실행: `183/200` result cache hit
  - 800개 실행: `784/800` result cache hit
- 규칙 기반 판정은 일정 비중을 차지하지만, 여전히 많은 조건 판정은 LLM 경로를 탑니다.
- 이번 데이터셋 기준으로 기업 인식률은 200개와 800개 실행에서 `100%`였습니다.

## 이 리포트의 한계

- 이 결과는 공유 staging 또는 production worker 검증 결과가 아닙니다.
- 현재 브랜치 코드를 로컬 격리 실행 경로로 검증한 결과입니다.
- 공유 preview 환경은 worker가 현재 코드와 맞지 않기 때문에, 아직 이 결과를 그대로 대표값으로 보기는 어렵습니다.

## 남은 운영 작업

1. `condition_check` 지원과 DynamoDB transaction conflict retry fix가 포함된 worker 코드를 실제 배포 환경에 올려야 합니다.
2. 동일한 `50 -> 200 -> 800` 시나리오를 공유 배포 환경에서 다시 실행해야 합니다.
3. 그 결과를 이번 로컬 기준치와 비교해서 처리량, 실패율, cache hit, artifact 생성 성공 여부를 다시 확인해야 합니다.

