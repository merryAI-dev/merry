# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

VC 투자 분석 및 Exit 프로젝션 자동화 도구. 투자 검토 엑셀 파일을 분석하여 PER 기반 시나리오별 수익률을 계산하고 전문적인 Exit 프로젝션 엑셀을 생성한다.

## 핵심 명령어

### 엑셀 파일 분석 (데이터 추출)
```bash
python scripts/analyze_valuation.py <엑셀파일경로>
python scripts/analyze_valuation.py input.xlsx -o output.json
```

### Exit 프로젝션 생성 (3가지 레벨)

**기본판**: 회사제시/심사역제시 기준 단순 Exit 분석
```bash
python scripts/generate_exit_projection.py \
  --investment_amount 300000000 \
  --price_per_share 32808 \
  --shares 9145 \
  --total_shares 28624 \
  --net_income_company 2800000000 \
  --net_income_reviewer 1400000000 \
  --target_year 2028 \
  --company_name "회사명" \
  --per_multiples "7,8,10" \
  --output result.xlsx
```

**고급판**: 부분 매각 + NPV 할인 분석
```bash
python scripts/generate_advanced_exit_projection.py \
  --investment_amount 300000000 \
  --price_per_share 32808 \
  --shares 9145 \
  --total_shares 28624 \
  --net_income_2029 2800000000 \
  --net_income_2030 3500000000 \
  --company_name "회사명" \
  --per_multiples "10,15,20" \
  --partial_exit_ratio 0.5 \
  --discount_rate 0.10 \
  --output advanced.xlsx
```

**완전판**: SAFE 전환 + 콜옵션 + 희석 효과 분석
```bash
python scripts/generate_complete_exit_projection.py \
  --investment_amount 300000000 \
  --price_per_share 32808 \
  --shares 9145 \
  --total_shares_before_safe 28624 \
  --net_income_2029 2800000000 \
  --net_income_2030 3500000000 \
  --company_name "회사명" \
  --per_multiples "10,15,20" \
  --safe_amount 100000000 \
  --safe_valuation_cap 5000000000 \
  --call_option_price_multiplier 1.5 \
  --output complete.xlsx
```

## 아키텍처

### 스크립트 구조
```
scripts/
├── analyze_valuation.py                   # 투자검토 엑셀 파싱
├── generate_exit_projection.py             # 기본 Exit 프로젝션
├── generate_advanced_exit_projection.py    # 고급 분석 (부분매각, NPV)
└── generate_complete_exit_projection.py    # 완전판 (SAFE, 콜옵션)
```

### 데이터 흐름
```
투자검토 엑셀
    ↓
analyze_valuation.py (파싱)
    ↓
JSON 데이터 (투자조건, IS요약, Cap Table)
    ↓
generate_*_exit_projection.py (선택)
    ↓
Exit 프로젝션 엑셀
```

### 3-Tier 프로젝션 아키텍처

| 레벨 | 스크립트 | 시나리오 | 사용 시점 |
|------|----------|----------|-----------|
| **기본** | `generate_exit_projection.py` | 회사제시/심사역제시 Exit | 단순 IRR/멀티플 계산 |
| **고급** | `generate_advanced_exit_projection.py` | (1) 전체매각 (2) 부분매각 (3) NPV할인 | 2단계 Exit 전략 검토 |
| **완전** | `generate_complete_exit_projection.py` | (1) 기본 (2) SAFE전환후 (3) 콜옵션 (4) 부분매각 (5) NPV | SAFE/옵션 조건 포함 복합 분석 |

## Exit 계산 공식

### 기본 공식 (모든 스크립트 공통)
```
기업가치 = 당기순이익 × PER
주당가치 = 기업가치 / 총발행주식수
회수금액 = 주당가치 × 투자주식수
멀티플 = 회수금액 / 투자원금
IRR = (멀티플)^(1/투자기간) - 1
```

### 고급 공식 (고급판/완전판)

**SAFE 전환 (완전판)**
```
SAFE 전환 주식수 = (SAFE 투자금액 / 밸류에이션 캡) × 총발행주식수
총 발행주식수 (전환 후) = 기존 총주식수 + SAFE 전환 주식수
희석 후 지분율 = 투자주식수 / 총발행주식수(전환 후)
```

**콜옵션 (완전판)**
```
콜옵션 행사가 = 투자단가 × 행사가 배수 (예: 1.5x)
콜옵션 회수금액 = 행사가 × 투자주식수
```

**부분 매각 (고급판/완전판)**
```
1차 회수액 = 2029년 주당가치 × 투자주식수 × 매각비율
2차 회수액 = 2030년 주당가치 × 투자주식수 × (1 - 매각비율)
총 회수액 = 1차 회수액 + 2차 회수액
복합 IRR ≈ (총회수액/투자액)^(1/평균보유기간) - 1
  (평균보유기간 = 4년 × 50% + 5년 × 50% = 4.5년)
```

**NPV 할인 (고급판/완전판)**
```
NPV = 회수금액 / (1 + 할인율)^기간
NPV 멀티플 = NPV / 투자원금
NPV IRR = (NPV 멀티플)^(1/투자기간) - 1
```

## 엑셀 파싱 로직 (`analyze_valuation.py`)

### 파싱 대상 시트 및 탐색 방식

`analyze_valuation.py`는 **유연한 시트명 탐색**을 사용하여 다양한 포맷의 투자검토 엑셀을 처리한다:

| 시트 카테고리 | 검색 키워드 | 추출 데이터 |
|--------------|-------------|-------------|
| **투자조건** | `투자조건체크`, `투자조건`, `Investment Terms`, `조건` | 투자금액, 투자단가, 투자주식수, 투자유형, 투자일, 회수예정일 |
| **IS요약** | `IS요약`, `손익추정`, `IS`, `Income Statement`, `5. IS요약` | 연도별 당기순이익 (회사제시/심사역제시) |
| **Cap Table** | `Cap Table`, `CapTable`, `주주현황`, `지분구조` | 총발행주식수, 주주현황 |

### 파싱 알고리즘 특징

- **`find_cell_value()`**: 키워드 기반 셀 탐색 → 오른쪽/아래 셀 값 반환
- **연도별 데이터**: 헤더 행에서 연도 감지 → 해당 열의 당기순이익 추출
- **회사제시/심사역제시**: "심사역" 키워드로 섹션 구분하여 별도 파싱
- **`data_only=True`**: 수식이 아닌 계산된 값만 추출

## 엑셀 생성 스타일 규칙

모든 `generate_*_exit_projection.py` 스크립트는 동일한 색상 코드를 사용한다:

| 스타일 | 의미 | 용도 |
|--------|------|------|
| 파란색 텍스트 (`BLUE_FONT`) | 입력값 | 사용자가 수정 가능한 가정 (PER, 투자조건 등) |
| 노란색 배경 (`INPUT_FILL`) | 핵심 가정 | 시나리오 분석의 기준값 |
| 녹색 배경 (`RESULT_FILL`) | 결과값 | 계산된 IRR, 멀티플 (읽기 전용) |
| 주황색 배경 (`SAFE_FILL`) | SAFE 관련 | SAFE 전환 관련 셀 (완전판만) |
| 회색 배경 (`CALL_FILL`) | 콜옵션 관련 | 콜옵션 행사 관련 셀 (완전판만) |

## Peer PER 분석 기능 (신규)

### 개요

유사 상장 기업의 PER을 조회하여 투자 대상 기업의 적정 밸류에이션을 산정한다.

### 워크플로우
```
PDF 업로드 (기업 소개서)
    ↓
Claude가 비즈니스 모델/산업 분석
    ↓
유사 상장 기업 검색 (WebSearch)
    ↓
yfinance로 PER/매출/영업이익률 조회
    ↓
Peer 기업 PER 비교표 + 평균/중간값 계산
    ↓
대화형 재무 프로젝션 지원
```

### 새로운 도구 (agent/tools.py)

| 도구명 | 설명 | 입력 |
|--------|------|------|
| `read_pdf_as_text` | PDF → 텍스트 변환 | `pdf_path`, `max_pages` |
| `get_stock_financials` | 개별 기업 재무 지표 조회 | `ticker` (예: AAPL, 005930.KS) |
| `analyze_peer_per` | 여러 Peer 기업 PER 일괄 조회 | `tickers`, `include_forward_per` |

### 티커 형식
- 미국: `AAPL`, `MSFT`, `GOOGL`
- 한국 KOSPI: `005930.KS` (삼성전자)
- 한국 KOSDAQ: `035720.KQ` (카카오)

### 사용 예시
```python
# 개별 기업 조회
result = execute_get_stock_financials("AAPL")
# -> trailing_per, forward_per, revenue, operating_margin 등

# 여러 기업 비교
result = execute_analyze_peer_per(["CRM", "NOW", "WDAY"])
# -> peers: [...], statistics: {trailing_per: {mean, median, min, max}}
```

## 의존성

- **openpyxl**: 엑셀 읽기/쓰기 (`.xlsx` 파일 처리)
  - `load_workbook()`: 엑셀 읽기 (`data_only=True`로 수식 계산값 로드)
  - `Workbook()`: 엑셀 생성
  - 스타일링: `Font`, `PatternFill`, `Alignment`, `Border`
- **yfinance**: Yahoo Finance API (Peer PER 분석)
- **PyMuPDF (fitz)**: PDF 텍스트 추출
