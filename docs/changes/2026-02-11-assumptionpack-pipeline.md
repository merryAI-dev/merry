# AssumptionPack/FactPack 파이프라인 적용 보고

## 배경
기존 투자심사 작성 흐름은 LLM 자유 생성 비중이 높아 숫자 드리프트, 근거 불일치, 재현성 저하 리스크가 있었습니다.
이에 따라 `Evidence -> FactPack -> AssumptionPack -> Validate/Lock -> Compute -> Section Draft` 흐름으로 고정했습니다.

## 적용 범위
- Report 세션 기반 파이프라인
- Exit Projection 계산 경로
- Draft 확정(stash) 안정화

## 핵심 변경

### 1) 중간표현 도입
- FactPack/AssumptionPack/ComputeSnapshot 타입 추가
- 세션 메시지 스냅샷 저장 방식 적용

### 2) API 확장
- Facts: build/latest
- Assumptions: suggest/save/validate/lock/latest
- Compute: exit-projection/latest

### 3) LLM 생성 게이트 강화
- locked AssumptionPack + compute snapshot 기반 숫자만 사용
- 근거 없는 숫자는 `[확인 필요]`로 처리

### 4) 결정론 계산 정합성 강화
- `investment_year`를 pack 기준으로 전달해 holding period 계산 고정
- worker/tool/script 인자 경로 통일

### 5) UI 통합
- `/report/[slug]`에 Facts/Assumptions 패널 통합
- Fact 생성 -> 가정 제안/검증/잠금 -> Exit Projection 실행 연결

### 6) 안정화 이슈
- stash 500 에러 수정
  - 원인: `zod@4.3.6` + `z.record(z.unknown())` 파싱 런타임 예외
  - 조치: `z.record(z.string(), z.unknown())`로 변경

## 검증
- `cd web && npm run lint` 통과
- `cd web && npm run build` 통과
- Vercel 배포 후 stash API 500 원인 로그 확인 및 패치 반영

## 후속 권장
- 리뷰 accepted 코멘트 기반 섹션 mutation 자동화
- Fact key 정규화(예: `net_income_YYYY`) 고도화
- Exit Projection 페이지에서 AssumptionPack save/lock UX 연결
