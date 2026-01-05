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

## Claude Vision PDF 파싱 기능

### 개요

Claude Vision API를 사용하여 PDF에서 테이블 구조를 보존하며 파싱합니다.
기존 PyMuPDF보다 테이블/재무제표 추출 정확도가 높고, 별도 모델 다운로드 없이 바로 사용 가능합니다.

### 모듈 구조
```
dolphin_service/
├── __init__.py
├── config.py              # 설정 (이미지 DPI, 페이지 제한 등)
├── processor.py           # Claude Vision PDF 처리 핵심 로직
├── table_extractor.py     # 재무제표 테이블 분류/파싱
└── output_converter.py    # 출력 포맷 변환
```

### 도구 (agent/tools.py)

| 도구명 | 설명 | 입력 |
|--------|------|------|
| `read_pdf_as_text` | Claude Vision으로 PDF 파싱 (실패시 PyMuPDF 폴백) | `pdf_path`, `max_pages`, `output_mode` |
| `parse_pdf_dolphin` | Claude Vision PDF 파싱 (동일 기능) | `pdf_path`, `max_pages`, `output_mode` |
| `extract_pdf_tables` | PDF에서 테이블만 추출 | `pdf_path`, `max_pages` |

### 출력 모드

| 모드 | 설명 |
|------|------|
| `text_only` | 페이지별 텍스트만 반환 |
| `structured` | 텍스트 + 구조화된 테이블/요소 + 재무제표 반환 |
| `tables_only` | 테이블과 재무제표만 추출하여 반환 |

### 처리 흐름

```
PDF 업로드
    ↓
PyMuPDF로 이미지 변환 (페이지별 PNG)
    ↓
Claude Vision API 호출
    ↓
구조화된 JSON 응답 파싱
    ↓
재무제표 자동 추출 (IS/BS/CF/Cap Table)
    ↓
캐시 저장 (7일 TTL)
```

### 재무제표 자동 추출

`output_mode="structured"` 사용 시 다음 테이블을 자동 감지:
- **손익계산서 (IS)**: 매출, 영업이익, 당기순이익
- **재무상태표 (BS)**: 총자산, 총부채, 자본
- **현금흐름표 (CF)**: 영업/투자/재무활동 현금흐름
- **Cap Table**: 주주현황, 지분율

### 사용 예시

```python
# 기본 사용 (Claude Vision)
result = execute_read_pdf_as_text(
    pdf_path="temp/user123/company_ir.pdf",
    max_pages=30,
    output_mode="structured"
)

# 결과 구조
{
    "success": True,
    "content": "페이지별 텍스트...",  # 레거시 호환
    "structured_content": {...},         # 구조화된 요소
    "financial_tables": {
        "income_statement": {
            "found": True,
            "page": 15,
            "years": ["2024E", "2025E"],
            "metrics": {
                "revenue": [100, 150],
                "net_income": [8, 16]
            }
        },
        "cap_table": {
            "found": True,
            "shareholders": [...],
            "total_shares": 100000
        }
    },
    "processing_method": "claude_opus",
    "processing_time_seconds": 12.5
}
```

### 모델 및 프롬프트

- **Claude Opus 4** 사용 (최고 성능)
- 10년+ 경력 VC 투자심사역 페르소나 적용
- 재무제표/투자조건 추출 특화 시스템 프롬프트

### 추출 가능 데이터

1. **회사 정보**: 회사명, 산업, 설립연도, 직원수, 비즈니스 모델
2. **투자 조건**: Pre/Post-money, 투자금액, 주당가격, 지분율, 투자유형
3. **손익계산서**: 매출, 매출총이익, 영업이익, EBITDA, 당기순이익 (연도별)
4. **재무상태표**: 총자산, 부채, 자본, 현금, 차입금
5. **현금흐름표**: 영업/투자/재무활동 CF, FCF
6. **Cap Table**: 주주현황, 지분율, 스톡옵션 풀
7. **밸류에이션 지표**: PER, PSR, EV/EBITDA

### 비용 고려사항

- Claude Opus 4 사용
- 30페이지 PDF 기준 약 $0.50-1.00 예상
- 캐싱으로 반복 처리 비용 절감 (7일 TTL)

## 대화형 투자 분석 세션

### 개요

대화 중에 부족한 데이터를 점진적으로 수집하여 완전한 투자 분석을 완성합니다.
PDF 파일, 텍스트 입력 등을 자유롭게 추가할 수 있습니다.

### 워크플로우

```
사용자: IR자료 업로드
    ↓
에이전트: 분석 세션 시작 (start_analysis_session)
    ↓
에이전트: "손익계산서와 Cap Table이 필요합니다"
    ↓
사용자: 재무제표 PDF 업로드 또는 텍스트 입력
    ↓
에이전트: 추가 데이터 입력 (add_supplementary_data)
    ↓
에이전트: 상태 확인 후 필요시 추가 요청
    ↓
모든 데이터 수집 완료
    ↓
에이전트: 최종 분석 반환 (complete_analysis)
```

### 도구 (agent/tools.py)

| 도구명 | 설명 | 주요 입력 |
|--------|------|-----------|
| `start_analysis_session` | 새 분석 세션 시작 | `initial_pdf_path` (선택) |
| `add_supplementary_data` | 세션에 데이터 추가 | `session_id`, `pdf_path` 또는 `text_input`, `data_type` |
| `get_analysis_status` | 현재 수집 상태 확인 | `session_id` |
| `complete_analysis` | 최종 분석 결과 반환 | `session_id` |

### 텍스트 입력 data_type

| 유형 | 설명 | 예시 |
|------|------|------|
| `financial` | 손익계산서 데이터 | "2024년 매출 100억, 영업이익 20억, 순이익 15억" |
| `cap_table` | 주주 현황 | "대표이사 60%, 투자자A 20%, 스톡옵션풀 20%" |
| `investment_terms` | 투자 조건 | "투자금액 30억, Pre-money 100억, 주당가격 10,000원" |
| `general` | 기타 정보 | 회사 설명, 비즈니스 모델 등 |

### 사용 예시

```python
# 1. 세션 시작 (PDF 포함 가능)
result = execute_start_analysis_session(initial_pdf_path="temp/user123/ir.pdf")
session_id = result["session_id"]
# -> missing_data: ["손익계산서", "Cap Table"]

# 2. 텍스트로 재무 데이터 추가
result = execute_add_supplementary_data(
    session_id=session_id,
    text_input="2024년 매출 100억, 영업이익 15억, 순이익 10억\n2025년E 매출 150억, 순이익 20억",
    data_type="financial"
)
# -> missing_data: ["Cap Table"]

# 3. Cap Table PDF 추가
result = execute_add_supplementary_data(
    session_id=session_id,
    pdf_path="temp/user123/cap_table.pdf"
)
# -> status: "complete"

# 4. 최종 분석
result = execute_complete_analysis(session_id)
# -> 전체 분석 결과 반환
```

## 의존성

- **openpyxl**: 엑셀 읽기/쓰기 (`.xlsx` 파일 처리)
  - `load_workbook()`: 엑셀 읽기 (`data_only=True`로 수식 계산값 로드)
  - `Workbook()`: 엑셀 생성
  - 스타일링: `Font`, `PatternFill`, `Alignment`, `Border`
- **yfinance**: Yahoo Finance API (Peer PER 분석)
- **PyMuPDF (fitz)**: PDF → 이미지 변환, 텍스트 추출 (폴백)
- **anthropic**: Claude API 클라이언트
