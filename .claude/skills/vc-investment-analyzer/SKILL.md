---
name: vc-investment-analyzer
description: "VC 투자 분석 및 Exit 프로젝션 자동화 스킬. 투자 검토 엑셀 파일을 분석하여 IS요약, Cap Table, 투자조건을 파싱하고 PER 기반 Exit 프로젝션을 생성합니다. 사용 시점: (1) 투자 검토 엑셀 파일 분석 요청, (2) Exit 프로젝션/밸류에이션 요청, (3) PER 멀티플 기반 수익률 분석, (4) 투자 수익률/IRR 계산, (5) 스타트업 재무제표 분석"
---

# VC Investment Analyzer

스타트업 투자 검토 엑셀 파일을 분석하여 Exit 프로젝션을 자동 생성하는 스킬.

## 워크플로우

### 1. 엑셀 파일 분석
업로드된 투자 검토 엑셀에서 다음 시트 자동 파싱:
- **투자조건체크**: 투자금액, 투자단가, 투자주식수, 투자유형(RCPS 등)
- **IS요약/손익추정**: 연도별 매출, 영업이익, 당기순이익 (회사제시/심사역제시)
- **Cap Table**: 주주현황, 발행주식수, 지분율

### 2. Exit 프로젝션 생성
```
Exit 가치 = 당기순이익 × PER 멀티플
주당가치 = Exit 가치 / 총 발행주식수
회수금액 = 주당가치 × 투자주식수
멀티플 = 회수금액 / 투자원금
IRR = (멀티플)^(1/투자기간) - 1
```

### 3. 엑셀 출력
`scripts/generate_exit_projection.py` 실행하여 전문적인 Exit 프로젝션 엑셀 생성.

## 사용법

### Step 1: 엑셀 파일에서 데이터 추출
```bash
python scripts/analyze_valuation.py <업로드된_엑셀_경로>
```
출력: JSON 형태의 파싱된 투자 데이터

### Step 2: Exit 프로젝션 생성
```bash
python scripts/generate_exit_projection.py \
  --investment_amount <투자금액> \
  --price_per_share <투자단가> \
  --shares <투자주식수> \
  --total_shares <총발행주식수> \
  --net_income_company <회사제시_순이익> \
  --net_income_reviewer <심사역제시_순이익> \
  --target_year <목표연도> \
  --company_name <회사명> \
  --per_multiples "7,8,10" \
  --output <출력파일명>
```

## 핵심 파라미터

| 파라미터 | 설명 | 예시 |
|---------|------|------|
| `investment_amount` | 투자금액 (원) | 300000000 |
| `price_per_share` | 투자단가 (원/주) | 32808 |
| `shares` | 투자주식수 | 9145 |
| `total_shares` | 총 발행주식수 (투자 후) | 28624 |
| `net_income_company` | 회사제시 당기순이익 | 2800000000 |
| `net_income_reviewer` | 심사역제시 당기순이익 | 1400000000 |
| `per_multiples` | 적용할 PER 배수들 | "7,8,10" |

## 출력 엑셀 구조

1. **투자 조건**: 투자금액, 단가, 주식수, 투자일/회수예정일
2. **순이익 가정**: 회사제시/심사역제시 당기순이익
3. **Exit 분석 테이블**: PER별 기업가치, 주당가치, 회수금액, 멀티플, IRR
4. **요약 비교**: 시나리오별 핵심 지표

## 색상 규칙 (업계 표준)
- 파란색 텍스트: 입력값 (수정 가능)
- 노란색 배경: 핵심 가정
- 녹색 배경: 결과값 (멀티플, IRR)
