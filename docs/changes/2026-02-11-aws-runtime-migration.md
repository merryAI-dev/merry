# AWS 런타임 전환 변경 보고 (Vercel + Worker)

## 목적
- Supabase 중심 저장/처리 경로를 AWS 기반(S3, DynamoDB, SQS, Bedrock)으로 전환한 변경을 운영 관점에서 정리합니다.
- 장애 원인 파악 시 필요한 환경변수/권한/실행 경로를 한 곳에서 확인할 수 있게 합니다.

## 적용 범위
- 웹 런타임(Next.js on Vercel)
- 비동기 워커(Python worker)
- 공통 데이터 경로(단일 DynamoDB 테이블)

## 핵심 변경

### 1) 스토리지/큐/DB 전환
- 업로드: 브라우저 -> S3 presigned URL 직접 업로드
- 상태/히스토리: DynamoDB 단일 테이블 사용
- 장시간 작업: SQS 큐 기반 비동기 처리(`jobs`)
- 생성형 AI: Bedrock 모델 호출(웹은 스트리밍/요약, 워커는 분석)

### 2) 리포트 세션 데이터 저장 표준화
- 세션별 메시지 스냅샷을 DynamoDB에 저장
- 세션 prefix(`report_`, `tasks_`, `docs_` 등)로 조회/격리
- `Facts/Assumptions/ComputeSnapshot/Validation`을 세션 메시지 메타데이터로 적재

### 3) Exit Projection 결정론 실행 경로 정리
- AssumptionPack 값을 worker로 전달해 계산 입력 고정
- `investment_year`를 계산식에 직접 반영해 holding period 재현성 확보
- 동일 pack 기준 재실행 시 동일 결과를 보장하도록 파라미터 경로 통일

### 4) 권한/환경변수 기준선
- 웹(Vercel):
  - `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
  - `MERRY_S3_BUCKET`, `MERRY_DDB_TABLE`, `MERRY_SQS_QUEUE_URL`
  - `LLM_PROVIDER=bedrock`, `BEDROCK_MODEL_ID`
- 워커:
  - 웹과 동일한 AWS 접근 정보 + 큐 polling 권한
- IAM 최소 권한:
  - S3: Put/Get/List(버킷 범위)
  - DynamoDB: Get/Put/Query/Update(테이블 범위)
  - SQS: Send/Receive/Delete/GetQueueAttributes(큐 범위)
  - Bedrock: `InvokeModel`, `InvokeModelWithResponseStream`

### 5) 운영 이슈 및 조치
- 현상: `POST /api/report/{sessionId}/stash` 500
- 원인: `zod@4.3.6`에서 `z.record(z.unknown())` 파싱 오류
- 조치: `z.record(z.string(), z.unknown())`로 수정

## 운영 체크리스트
- [ ] Vercel 프로젝트가 올바른 repo/branch/main에 연결되어 있는가
- [ ] 프로덕션 env가 Preview와 분리되어 정확히 주입됐는가
- [ ] SQS 큐에 메시지가 적재/소비되고 worker가 running 상태인가
- [ ] Bedrock 모델 접근(Use case 제출 포함)과 IAM 권한이 활성화됐는가
- [ ] Airtable PAT/Base 권한이 실제 Base와 일치하는가

## 후속 권장
- 워커 ECS 상시 실행 + DLQ 운영
- DynamoDB TTL/보존정책 정리(임시 데이터)
- CloudWatch + Vercel 로그 상관 ID 통합
- API preflight health endpoint 강화(`/api/health`에 AWS 종합 점검 추가)
