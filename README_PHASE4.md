# Phase 4: 파인튜닝 데이터 수집 파이프라인

## 빠른 시작

### 1. 데이터 수집 활성화

```bash
# .env 파일에 추가
echo "ENABLE_TRAINING_COLLECTION=true" >> .env
```

### 2. 앱 실행

```bash
streamlit run app.py
```

### 3. 통계 확인

```bash
python scripts/training_cli.py stats
```

---

## 📖 전체 문서

**[docs/TRAINING_DATA_COLLECTION.md](docs/TRAINING_DATA_COLLECTION.md)** 참조

주요 내용:
- 데이터 수집 활성화 방법
- CLI 도구 사용법 (stats, list, export, validate)
- PII 자동 제거 메커니즘
- AWS S3 마이그레이션 계획
- 워크플로우 예시

---

## 주요 기능

### ✅ 완료된 기능

1. **스토리지 추상화** (`shared/storage_backend.py`)
   - LocalStorageBackend (현재)
   - S3StorageBackend (설계 완료, 구현 예정)

2. **PII 자동 제거** (`shared/pii_scrubber.py`)
   - 전화번호, 이메일, 주민번호 등 8개 패턴
   - 필드명 기반 PII 감지
   - Strict 모드 지원

3. **데이터 수집 데코레이터** (`shared/training_logger.py`)
   - `@log_training_data(task_type, model_name)` 데코레이터
   - 비침투적 로깅 (기존 코드 최소 변경)
   - 환경 변수로 활성화/비활성화

4. **합성 데이터 생성** (`shared/synthetic_korean_numbers.py`)
   - 한국어 숫자 파싱 2029 샘플
   - Edge case 29 샘플
   - JSONL 포맷

5. **CLI 관리 도구** (`scripts/training_cli.py`)
   - `stats`: 수집 통계
   - `list`: 파일 목록
   - `export`: JSONL 통합
   - `validate`: PII 검증

### 🔜 향후 작업

- **Phase 4-B**: S3 백엔드 구현 (boto3)
- **Phase 5**: UI/UX 개선 (프로그레시브 로딩)
- **파인튜닝 실행**: Anthropic API 연동

---

## 적용된 도구

| 도구 | 파일 | 작업 타입 |
|------|------|----------|
| `process_pdf_with_claude()` | `dolphin_service/processor.py` | `pdf_extraction` |
| `execute_analyze_excel()` | `agent/tools/extraction_tools.py` | `text_parsing` |

---

## 데이터 저장 경로

```
data/training/
├── pdf_extraction/
│   └── 20260209.jsonl
├── text_parsing/
│   └── 20260209.jsonl
└── synthetic/
    ├── korean_numbers.jsonl (2000 samples)
    └── korean_numbers_edge_cases.jsonl (29 samples)
```

---

## CLI 예시

```bash
# 전체 통계
python scripts/training_cli.py stats

# 특정 작업 통계
python scripts/training_cli.py stats --task-type pdf_extraction

# 데이터 내보내기
python scripts/training_cli.py export pdf_extraction output.jsonl

# PII 검증
python scripts/training_cli.py validate pdf_extraction --verbose
```

---

## 보안: 이중 방어

1. **1차 방어**: PII 스크러버 (자동 마스킹)
2. **2차 방어**: AWS S3 (암호화 + IAM 역할)

> 기존 Streamlit → API 직배송 방식에서 S3 이관으로 보안 강화

---

## 문의 및 기여

질문이나 버그 리포트는 이슈로 등록해주세요.
