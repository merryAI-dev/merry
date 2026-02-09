# 파인튜닝 데이터 수집 파이프라인

Phase 4에서 구현된 파인튜닝 데이터 수집 파이프라인 사용 가이드입니다.

## 목차

- [개요](#개요)
- [데이터 수집 활성화](#데이터-수집-활성화)
- [수집 대상 작업](#수집-대상-작업)
- [CLI 도구 사용법](#cli-도구-사용법)
- [PII 보안](#pii-보안)
- [스토리지 백엔드](#스토리지-백엔드)
- [AWS S3 마이그레이션 계획](#aws-s3-마이그레이션-계획)

---

## 개요

메리 프로젝트는 VC 투자 심사 작업을 자동화하기 위해 Claude API를 사용합니다.
Phase 4 파이프라인은 **실제 사용 데이터를 자동 수집**하여 향후 파인튜닝에 활용할 수 있도록 합니다.

### 주요 기능

1. **비침투적 데이터 수집**: Python 데코레이터로 기존 코드 수정 최소화
2. **자동 PII 제거**: 개인정보(전화번호, 이메일, 주민번호 등) 자동 스크러빙
3. **JSONL 포맷**: Anthropic Fine-tuning API 호환 형식
4. **스토리지 추상화**: 로컬 파일 시스템 → AWS S3 마이그레이션 경로 제공
5. **CLI 관리 도구**: 통계 조회, 데이터 내보내기, PII 검증

### 보안 강화

기존에는 Streamlit에서 API로 직접 전송하던 방식에서, **AWS S3로 이관하여 이중 보안 방어**를 구현합니다:

- **1차 방어**: PII 스크러버가 자동으로 민감 정보 제거
- **2차 방어**: S3 버킷 암호화 + IAM 역할 기반 접근 제어 (Phase 4 완료 후)

---

## 데이터 수집 활성화

### 1. 환경 변수 설정

데이터 수집은 **기본적으로 비활성화**되어 있습니다. 활성화하려면:

```bash
# .env 파일에 추가
ENABLE_TRAINING_COLLECTION=true

# PII 검증 strict 모드 (PII 감지 시 로그 저장 차단)
TRAINING_PII_STRICT=false  # 기본값: false (경고만 로그)

# 스토리지 백엔드 선택 (현재는 local만 지원)
TRAINING_STORAGE_BACKEND=local  # 기본값
# TRAINING_STORAGE_BACKEND=s3  # 향후 S3 마이그레이션 시
```

### 2. 로컬 스토리지 경로

기본 저장 경로: `data/training/{task_type}/{YYYYMMDD}.jsonl`

예시:
```
data/training/
├── pdf_extraction/
│   ├── 20260209.jsonl
│   └── 20260210.jsonl
├── text_parsing/
│   └── 20260209.jsonl
└── table_classification/
    └── 20260209.jsonl
```

---

## 수집 대상 작업

| 작업 타입 | 설명 | 적용 함수 | 타겟 모델 |
|----------|------|----------|-----------|
| `pdf_extraction` | PDF → 구조화 JSON | `dolphin_service/processor.py::process_pdf_with_claude()` | Sonnet 파인튜닝 |
| `text_parsing` | 텍스트 입력 → JSON | `agent/tools/extraction_tools.py::execute_analyze_excel()` | Haiku 파인튜닝 |
| `table_classification` | 재무제표 분류 | `dolphin_service/table_extractor.py::extract_financial_tables()` (향후) | Haiku 파인튜닝 |
| `json_repair` | 깨진 JSON 수리 | (향후 적용) | Haiku 파인튜닝 |
| `korean_number_parsing` | 한국어 숫자 정규화 | 합성 데이터 생성됨 | 규칙 기반 (LLM 불필요) |

---

## CLI 도구 사용법

### 통계 조회

전체 통계:
```bash
python scripts/training_cli.py stats
```

출력 예시:
```
Training Data Collection Status
  Enabled: True
  Total tasks: 3

  pdf_extraction:
    Samples: 1,234
    Files: 15
    Size: 45.67 MB
    Date range: 2026-02-01 ~ 2026-02-09

  text_parsing:
    Samples: 456
    Files: 8
    Size: 12.34 MB
    Date range: 2026-02-05 ~ 2026-02-09
```

특정 작업 타입만:
```bash
python scripts/training_cli.py stats --task-type pdf_extraction
```

### 파일 목록 조회

```bash
python scripts/training_cli.py list pdf_extraction
```

출력:
```
Training samples for pdf_extraction:
  data/training/pdf_extraction/20260209.jsonl
  data/training/pdf_extraction/20260208.jsonl
  ...
Total: 15 files
```

### 데이터 내보내기

단일 JSONL 파일로 통합:
```bash
python scripts/training_cli.py export pdf_extraction output.jsonl
```

출력:
```
Exported 1,234 samples to output.jsonl
Size: 45.67 MB
```

### PII 검증

수집된 데이터에 개인정보가 남아있는지 확인:

```bash
# 요약만 표시
python scripts/training_cli.py validate pdf_extraction

# 상세 경고 표시
python scripts/training_cli.py validate pdf_extraction --verbose
```

출력 예시:
```
Validation Summary:
  Total samples: 1,234
  PII warnings: 3
  ⚠ 3 potential PII issues found
  Run with --verbose to see details
```

`--verbose` 시:
```
data/training/pdf_extraction/20260209.jsonl (sample 45):
  - root.input.company_info.representative_name: Field name indicates PII
  - root.output.structured_content.pages[2].text: Detected phone pattern in value
```

---

## PII 보안

### 자동 스크러빙 패턴

`shared/pii_scrubber.py`가 다음 패턴을 자동 감지 및 마스킹:

| 유형 | 정규식 | 예시 |
|------|--------|------|
| 전화번호 | `\b0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}\b` | `010-1234-5678` → `010************` |
| 이메일 | `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z\|a-z]{2,}` | `user@example.com` → `use************` |
| 주민번호 | `\d{6}[-\s]?[1-4]\d{6}` | `123456-1234567` → `123************` |
| 사업자등록번호 | `\d{3}[-\s]?\d{2}[-\s]?\d{5}` | `123-45-67890` → `123************` |
| 법인등록번호 | `\d{6}[-\s]?\d{7}` | `110111-1234567` → `110************` |
| 신용카드 | `\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}` | `1234-5678-9012-3456` → `123****************` |
| 주소 | `[가-힣]+[시도]\s+[가-힣]+[구군]\s+[가-힣]+[동읍면리로길]\s+\d+` | `서울시 강남구 테헤란로 123` → 마스킹 |
| 계좌번호 | `\d{2,4}[-\s]?\d{2,6}[-\s]?\d{2,8}` | `123-456-789012` → `123************` |

### PII 필드명 감지

다음 필드명은 자동으로 `[REDACTED_PII]`로 치환:

```python
PII_FIELD_NAMES = {
    "email", "phone", "tel", "mobile",
    "resident_id", "주민번호", "주민등록번호",
    "business_registration_number", "사업자등록번호",
    "corporate_registration_number", "법인등록번호",
    "representative_name", "대표자", "대표이사",
    "name", "이름", "성명",
    "address", "주소", "소재지",
    "bank_account", "계좌번호",
    "credit_card", "카드번호",
}
```

### Strict 모드

```bash
# .env에 추가
TRAINING_PII_STRICT=true
```

- PII 감지 시 해당 샘플 저장하지 않음
- 기본값 `false`: 경고만 로그하고 저장은 진행

---

## 스토리지 백엔드

### LocalStorageBackend (현재)

**경로**: `data/training/{task_type}/{YYYYMMDD}.jsonl`

**특징**:
- JSONL append 모드로 thread-safe 저장
- 파일 시스템 기반 (개발/테스트 환경)
- 날짜별 파일 자동 생성

**사용 예시**:
```python
from shared.storage_backend import get_default_storage

storage = get_default_storage()
path = storage.write_training_sample(
    task_type="pdf_extraction",
    sample={"input": {...}, "output": {...}},
    metadata={"model": "claude-sonnet-4-5-20250929"}
)
print(f"Saved to: {path}")
```

### S3StorageBackend (향후)

**설계 (구현 예정)**:

```python
# .env 설정
TRAINING_STORAGE_BACKEND=s3
AWS_S3_BUCKET=merry-training-data
AWS_REGION=ap-northeast-2

# boto3 사용
import boto3
s3 = boto3.client('s3')
```

**S3 Key 구조**:
```
{task_type}/{YYYY}/{MM}/{DD}/{uuid}.jsonl

예시:
pdf_extraction/2026/02/09/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jsonl
```

**보안 설정**:
- 암호화: AES-256 (SSE-S3 or SSE-KMS)
- IAM 역할 기반 접근 제어
- Lifecycle: 90일 후 Glacier 아카이브

---

## AWS S3 마이그레이션 계획

### Phase 4-B: S3 백엔드 구현 (예정)

1. **boto3 설치**
   ```bash
   pip install boto3
   ```

2. **S3StorageBackend 구현**
   - `shared/storage_backend.py`의 stub 완성
   - `write_training_sample()`, `read_sample()`, `list_samples()` 메서드 구현

3. **IAM 설정**
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:PutObject",
           "s3:GetObject",
           "s3:ListBucket"
         ],
         "Resource": [
           "arn:aws:s3:::merry-training-data",
           "arn:aws:s3:::merry-training-data/*"
         ]
       }
     ]
   }
   ```

4. **환경 변수 전환**
   ```bash
   # .env
   TRAINING_STORAGE_BACKEND=s3
   AWS_S3_BUCKET=merry-training-data
   AWS_REGION=ap-northeast-2
   # AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY는 IAM Role 권장
   ```

5. **Lifecycle 정책**
   ```json
   {
     "Rules": [
       {
         "Id": "ArchiveOldTrainingData",
         "Status": "Enabled",
         "Transitions": [
           {
             "Days": 90,
             "StorageClass": "GLACIER"
           }
         ]
       }
     ]
   }
   ```

### 마이그레이션 검증

```bash
# 1. 로컬 데이터 백업
cp -r data/training data/training.backup

# 2. S3 백엔드로 전환
export TRAINING_STORAGE_BACKEND=s3

# 3. 샘플 데이터 업로드 테스트
python scripts/test_s3_upload.py

# 4. CLI로 S3 데이터 조회 확인
python scripts/training_cli.py stats

# 5. 실제 작업 수행 및 S3 저장 확인
aws s3 ls s3://merry-training-data/pdf_extraction/2026/02/09/
```

---

## 워크플로우 예시

### 1. 개발 환경에서 데이터 수집

```bash
# 1. 데이터 수집 활성화
echo "ENABLE_TRAINING_COLLECTION=true" >> .env

# 2. Streamlit 앱 실행
streamlit run app.py

# 3. 사용자가 투자 검토 파일 업로드 → 자동 수집
# (백그라운드에서 data/training/에 JSONL 저장)

# 4. 통계 확인
python scripts/training_cli.py stats
```

### 2. PII 검증 및 내보내기

```bash
# 1. PII 검증
python scripts/training_cli.py validate pdf_extraction --verbose

# 2. 문제 있는 샘플 수동 제거 (필요시)
vi data/training/pdf_extraction/20260209.jsonl

# 3. 통합 JSONL 내보내기
python scripts/training_cli.py export pdf_extraction pdf_extraction_dataset.jsonl

# 4. 파일 업로드 준비
# Anthropic Fine-tuning API에 업로드 또는
# 로컬 파인튜닝 파이프라인에 투입
```

### 3. 합성 데이터 생성 (한국어 숫자)

```bash
# 이미 생성됨:
# data/training/synthetic/korean_numbers.jsonl (2000 samples)
# data/training/synthetic/korean_numbers_edge_cases.jsonl (29 samples)

# 재생성이 필요하면:
python shared/synthetic_korean_numbers.py
```

출력:
```
Generating synthetic Korean number dataset...
✓ Generated 2000 samples

Generating edge cases...
✓ Generated 29 edge cases

Dataset saved to: data/training/synthetic
  - korean_numbers.jsonl: 2000 samples
  - korean_numbers_edge_cases.jsonl: 29 edge cases

Sample data:
  5억2천만 → 520,000,000
  1조3천억 → 1,300,000,000,000
  32억4500만 → 3,245,000,000
  3천억 → 300,000,000,000
  5천만 → 50,000,000
```

---

## 데코레이터 적용 예시

### PDF 추출 (pdf_extraction)

```python
# dolphin_service/processor.py
from shared.training_logger import log_training_data

@log_training_data(task_type="pdf_extraction", model_name="claude-sonnet-4-5-20250929")
def process_pdf_with_claude(
    pdf_path: str,
    max_pages: int = None,
    output_mode: str = "structured",
    progress_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
    """PDF를 Claude Vision으로 처리하는 편의 함수"""
    processor = ClaudeVisionProcessor()
    return processor.process_pdf(...)
```

### 텍스트 파싱 (text_parsing)

```python
# agent/tools/extraction_tools.py
from shared.training_logger import log_training_data

@log_training_data(task_type="text_parsing", model_name=None)
def execute_analyze_excel(excel_path: str) -> Dict[str, Any]:
    """엑셀 파일 분석 실행 - openpyxl로 직접 읽기"""
    # ... 파싱 로직 ...
    return result
```

### 재무제표 분류 (table_classification) - 향후 적용

```python
# dolphin_service/table_extractor.py
from shared.training_logger import log_training_data

class FinancialTableExtractor:
    @log_training_data(task_type="table_classification", model_name="claude-haiku-4-5-20251001")
    def extract_financial_tables(self, dolphin_output: Dict[str, Any]) -> Dict[str, Any]:
        """Dolphin 출력에서 재무제표 추출"""
        # ... 분류 로직 ...
        return result
```

---

## 로그 샘플

### 수집 성공 로그

```
INFO:training_logger:Logged training sample: pdf_extraction (process_pdf_with_claude) -> data/training/pdf_extraction/20260209.jsonl
```

### PII 경고 로그

```
WARNING:training_logger:PII detected in training sample for process_pdf_with_claude: 2 issues
WARNING:training_logger:  - root.input.pdf_path: Field name indicates PII (파일 경로에 사용자명 포함)
WARNING:training_logger:  - root.output.company_info.phone: Detected phone pattern in value
```

### Strict 모드 차단 로그

```
ERROR:training_logger:Skipping training sample due to PII detection (strict mode)
```

---

## 문제 해결

### Q: 데이터가 저장되지 않습니다.

**A**: 환경 변수 확인
```bash
# .env 파일 확인
cat .env | grep ENABLE_TRAINING_COLLECTION

# 출력이 없으면 추가:
echo "ENABLE_TRAINING_COLLECTION=true" >> .env

# Streamlit 재시작
```

### Q: PII 경고가 계속 나옵니다.

**A**: PII 스크러버 패턴 확장 필요
```python
# shared/pii_scrubber.py
# PII_PATTERNS에 새 패턴 추가
```

또는 strict 모드 활성화:
```bash
echo "TRAINING_PII_STRICT=true" >> .env
```

### Q: S3 업로드가 실패합니다.

**A**: IAM 권한 확인
```bash
# AWS CLI로 권한 테스트
aws s3 ls s3://merry-training-data/

# IAM Role 확인
aws iam get-role --role-name MerryTrainingDataRole

# 버킷 암호화 확인
aws s3api get-bucket-encryption --bucket merry-training-data
```

### Q: JSONL 파일이 너무 큽니다.

**A**: 날짜별 자동 분할 + 압축
```bash
# gzip 압축
gzip data/training/pdf_extraction/20260209.jsonl

# S3 Lifecycle로 자동 아카이브
aws s3api put-bucket-lifecycle-configuration ...
```

---

## 참고 자료

- [Anthropic Fine-tuning API](https://docs.anthropic.com/claude/docs/fine-tuning)
- [AWS S3 암호화](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingEncryption.html)
- [IAM 역할 기반 접근 제어](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles.html)
- [JSONL 포맷 스펙](https://jsonlines.org/)

---

## 다음 단계

1. **Phase 4-B**: S3StorageBackend 구현 (boto3)
2. **Phase 5**: UI/UX 개선 (프로그레시브 로딩, 에러 복구)
3. **파인튜닝 실행**: Anthropic API로 Haiku/Sonnet 모델 파인튜닝
4. **비용 비교**: 파인튜닝 모델 vs Opus 출력 품질 및 비용 측정
