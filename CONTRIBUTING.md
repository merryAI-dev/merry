# Contributing

## Branch 전략
- 기본 브랜치: `main`
- 기능/수정은 `feat/*`, `fix/*`, `chore/*` 형태의 브랜치에서 작업
- `main` 직접 푸시 대신 PR 권장

## PR 규칙
- 작은 단위로 분리: 기능/리팩터/문서/운영설정 PR 분리
- 제목은 명확하게: 예) `fix(report): stash 500 on zod record parse`
- 본문에 `목적`, `변경 내용`, `영향 범위`, `검증`을 포함

## 로컬 검증
```bash
cd web
npm run lint
npm run build
```

## 보안
- 키/토큰/개인정보/고객 파일은 절대 커밋 금지
- 환경변수는 Vercel/AWS 콘솔에서 관리

## 운영 체크
- API 변경 시 `/api/health` 확인
- 워커 작업 영향이 있으면 SQS 소비 경로도 같이 점검
