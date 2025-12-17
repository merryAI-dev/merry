# 템플릿 없이 “기업현황 진단시트”를 대화로 완성하는 빌더

## 목적

기존에는 사용자가 `기업현황 진단시트.xlsx` 템플릿을 업로드해야만 분석/보고서 작성이 가능했습니다.  
이번 구현의 목표는 **템플릿 파일이 없는 상황을 가정**하고, 대표자(사용자)가 에이전트와 **대화(질문→응답)** 하면서 내용을 단계적으로 채워 **최종적으로 엑셀을 생성/다운로드**할 수 있게 하는 것입니다.

---

## 사용자 UX (Streamlit)

### 1) 템플릿 업로드가 없는 경우

- 진단시트 페이지(`pages/3_Company_Diagnosis.py`)에서 업로드가 없으면:
  - “템플릿 없이 작성 시작” 버튼이 노출됩니다.
  - 버튼 클릭 시, 사용자 입력 없이도 대화가 시작되도록 quick command를 넣어 에이전트가 드래프트 생성을 시작합니다.

### 2) 대화로 작성 진행

- 에이전트는 “한 번에 1개 질문(필드)” 또는 “체크리스트 5~6개 배치”만 제시합니다.
- 사용자가 답하면, 에이전트가 즉시 드래프트에 반영하고 다음 질문으로 진행합니다.
- 페이지 상단에 진행률(progress bar)과 “다음 질문” 힌트가 표시됩니다.

### 3) 완료 및 엑셀 생성

- 모든 항목이 채워지면 에이전트가 “엑셀로 저장할까요?”를 묻습니다.
- 사용자가 “저장해줘/엑셀로 만들어줘/반영해줘” 등으로 긍정 응답하면, 드래프트를 기반으로 `diagnosis_sheet_*.xlsx`를 생성합니다.
- 생성된 파일은 페이지 하단 “최근 생성된 파일”에서 다운로드할 수 있습니다.

---

## 아키텍처 개요

### 핵심 아이디어: “드래프트(JSON) → 엑셀 생성” 2단계

1) **드래프트 생성**: `temp/<user_id>/diagnosis_draft_*.json`  
2) **드래프트 업데이트(대화 반복)**: 매 턴 사용자 답변을 구조화해 드래프트에 누적  
3) **엑셀 생성**: `temp/<user_id>/diagnosis_sheet_*.xlsx`

이렇게 하면 “템플릿이 없는 상황”에서도 동일한 결과물(엑셀)을 만들 수 있고, 이후 기존 파이프라인(분석/보고서 반영)으로 자연스럽게 이어갈 수 있습니다.

---

## 템플릿 정의(리소스)

### `shared/resources/company_diagnosis_template_2025.json`

템플릿이 “파일”이 아니라 “스키마/문항 정의”로 코드에 내장됩니다.

- `categories`: 점수 카테고리(문제/솔루션/사업화/자금조달/팀/조직/임팩트)
- `weights`: 카테고리별 가중치
- `company_info_fields`, `employees_financial_fields`, `investment_fields`, `kpi_fields`: 대화로 수집할 필드 정의
- `checklist_items`: 체크리스트 문항 정의(각 문항에 `id` 부여)
  - 예: `문제_01`, `팀_조직_07` 같은 형태로 안정적인 식별자를 사용
- `optional: true`: 필수 수집에서 제외되는 필드(예: 지점/연구소 소재지)

---

## 도구(TOOLS) 설계

도구는 `agent/tools.py`에 추가되며, 모든 파일 I/O는 기존 보안 정책대로 **`temp/` 하위 경로만 허용**합니다.

### 1) `create_company_diagnosis_draft`

- 입력: `user_id`, `template_version(=2025)`
- 출력:
  - `draft_path`: 생성된 드래프트 경로(`temp/<user_id>/diagnosis_draft_*.json`)
  - `progress`: 진행률/다음 질문 정보

### 2) `update_company_diagnosis_draft`

- 입력: `draft_path` + (선택) `company_info`, `employees_financials`, `investment`, `kpi`, `checklist_answers`
- 동작:
  - 전달된 payload만 드래프트에 merge (빈 값/None은 무시)
  - 체크리스트는 `id` 기반으로 `예/아니오` 및 `detail` 저장
- 출력:
  - `progress`: completion%, 현재 점수(부분 응답 기준), 다음 질문(next)

`progress.next.type` 종류:
- `field`: 단일 필드 질문
- `kpi_items`: KPI 1~5개 입력 요청
- `checklist_batch`: 같은 모듈 내 문항 5~6개 배치 질문
- `complete`: 작성 완료(엑셀 생성 여부 확인 단계)

### 3) `generate_company_diagnosis_sheet_from_draft`

- 입력: `draft_path`, (선택) `output_filename`
- 출력: `output_file` (생성된 엑셀 경로)
- 생성되는 시트(최소 구조):
  - `내보내기 요약`
  - `(기업&컨설턴트용) EXIT 체크리스트` (placeholder)
  - `(기업용) 1. 기업정보`
  - `(기업용) 2. 체크리스트`
  - `(기업용) 3. KPI기대사항`
  - `(컨설턴트용) 분석보고서` (최소 헤더/가중치/본문 영역만 구성)

---

## 에이전트(System Prompt) 동작 규칙

`agent/vc_agent.py`의 diagnosis mode 시스템 프롬프트를 확장했습니다.

- 템플릿(엑셀 파일)이 있는 경우:
  - `analyze_company_diagnosis_sheet` → 초안 → 사용자 확인 후 `write_company_diagnosis_report`
- 템플릿(엑셀 파일)이 없는 경우:
  - 최초 1회 `create_company_diagnosis_draft(user_id=...)`
  - 매 턴 `update_company_diagnosis_draft`로 반영하면서 `progress.next`를 따라 질문
  - 완료 시 `generate_company_diagnosis_sheet_from_draft`
  - (선택) 생성된 엑셀을 다시 `analyze_company_diagnosis_sheet`로 분석하고, 보고서까지 이어갈 수 있음

---

## Streamlit 연동 (상태 동기화)

### Session State 키 추가

`shared/config.py`에 아래 키를 추가하여 페이지 리로드/세션 이동에서도 안전하게 동작하도록 했습니다.

- `diagnosis_draft_path`
- `diagnosis_draft_progress`

### Tool 결과 동기화

`pages/3_Company_Diagnosis.py`에서 tool 메시지를 읽어:
- `create_company_diagnosis_draft`
- `update_company_diagnosis_draft`

결과의 `draft_path/progress`를 `st.session_state`에 저장해 진행률 UI를 렌더링합니다.

---

## 보안/운영 고려사항

- 드래프트/생성 엑셀은 모두 `temp/<user_id>/` 아래에 생성됩니다.
- 파일 접근은 `_validate_file_path(require_temp_dir=True)` 정책을 따릅니다.
- `user_id`는 경로 안전을 위해 정규화(`_sanitize_user_id`)합니다.

---

## 빠른 테스트 방법

### Streamlit

```bash
streamlit run app.py
```

1) “기업현황 진단시트” 페이지로 이동  
2) “템플릿 없이 작성 시작” 클릭  
3) 질문에 순서대로 응답  
4) 완료 후 “저장해줘”라고 입력 → 생성 파일 다운로드

### CLI (대화 모드)

```bash
python cli.py chat --mode diagnosis
```

대화 중에 “템플릿 없이 대화로 작성 시작해줘”라고 요청하면 빌더 흐름으로 유도됩니다.

---

## 다음 개선 아이디어 (옵션)

- 체크리스트 배치 응답을 자연어에서 더 강건하게 파싱(예: “문제_01 예, 문제_02 아니오(…)” 자동 구조화)
- KPI 입력을 표준 포맷으로 정규화(단위/기간/원화 표기)
- 완료 전 “미입력 항목 요약” 및 “중요도 기반 우선 질문” 지원
- 생성 엑셀에 기본 서식(테두리/색/데이터 유효성 검사) 추가

