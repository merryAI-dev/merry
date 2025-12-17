# Security FAQ

VC 투자 분석 에이전트의 보안 관련 자주 묻는 질문입니다.

---

## 목차

1. [인증 및 접근 제어](#1-인증-및-접근-제어)
2. [파일 업로드 보안](#2-파일-업로드-보안)
3. [데이터 저장 및 격리](#3-데이터-저장-및-격리)
4. [도구 실행 보안](#4-도구-실행-보안)
5. [외부 서비스 연동](#5-외부-서비스-연동)
6. [로깅 및 감사](#6-로깅-및-감사)
7. [배포 보안](#7-배포-보안)
8. [보안 체크리스트](#8-보안-체크리스트)
9. [알려진 제한사항](#9-알려진-제한사항)

---

## 1. 인증 및 접근 제어

### Q: 인증 방식은 무엇인가요?

**A:** Claude API 키 기반 인증을 사용합니다.

- 사용자가 본인의 Anthropic API 키를 입력하여 인증
- API 키 유효성 검증: 실제 API 호출로 확인 (최소 비용의 Haiku 모델 사용)
- 인증 성공 시 세션 유지

```python
# shared/auth.py
def validate_api_key(api_key: str) -> bool:
    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=10,
        messages=[{"role": "user", "content": "Hi"}]
    )
    return True  # 예외 없으면 유효
```

### Q: 사용자 식별은 어떻게 하나요?

**A:** API 키의 SHA-256 해시값 앞 12자리를 고유 ID로 사용합니다.

```python
# shared/auth.py
def get_user_id_from_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()[:12]
```

**장점:**
- 동일 API 키 사용자는 동일한 `user_id` → 세션/피드백 공유 가능
- 원본 API 키는 저장되지 않음 (해시만 사용)

### Q: API 키는 어디에 저장되나요?

**A:** Streamlit 세션 상태에만 저장되며, 서버 파일시스템이나 데이터베이스에는 저장하지 않습니다.

| 저장 위치 | 내용 | 지속성 |
|----------|------|--------|
| `st.session_state.user_api_key` | API 키 원문 | 세션 종료 시 삭제 |
| `st.session_state.user_id` | API 키 해시 | 세션 종료 시 삭제 |
| Supabase/로컬 | `user_id` (해시) | 영구 저장 |

- 브라우저 세션 종료 시 API 키 자동 삭제
- 로그에 API 키를 출력하지 않음

### Q: 세션 격리는 어떻게 되나요?

**A:** 각 사용자는 `user_id` 기반으로 완전히 격리된 환경을 갖습니다.

| 항목 | 격리 방식 |
|------|----------|
| 파일 업로드 | `temp/<user_id>/` 디렉토리에 저장 |
| 채팅 히스토리 | `chat_history/<user_id>/` 디렉토리에 저장 |
| 피드백 데이터 | Supabase `user_id` 컬럼 필터 |
| 생성 파일 | `temp/<user_id>/` 디렉토리에 생성 |

---

## 2. 파일 업로드 보안

### Q: 업로드 가능한 파일 형식은?

**A:** 화이트리스트 방식으로 엄격하게 제한합니다.

```python
# shared/file_utils.py
ALLOWED_EXTENSIONS_EXCEL = ['.xlsx', '.xls']
ALLOWED_EXTENSIONS_PDF = ['.pdf']
MAX_FILE_SIZE_MB = 50
```

| 검증 항목 | 조건 |
|----------|------|
| 엑셀 파일 | `.xlsx`, `.xls` |
| PDF 파일 | `.pdf` |
| 최대 크기 | 50MB |
| 빈 파일 | 업로드 차단 (0 bytes) |

### Q: Path Traversal 공격은 어떻게 방어하나요?

**A:** 다중 레이어 방어를 적용합니다.

**1단계: 파일명 정화** (`sanitize_filename`)

```python
def sanitize_filename(filename: str) -> str:
    # 경로 구분자 제거
    filename = filename.replace("/", "_").replace("\\", "_")
    # 특수문자 제거 (알파벳, 숫자, 한글, 기본 문자만 허용)
    sanitized = re.sub(r'[^\w\s가-힣.\-]', '_', filename, flags=re.UNICODE)
    return sanitized
```

**2단계: 고유 ID 접두사**

```python
# temp/<user_id>/<uuid>_<safe_filename>
unique_id = uuid.uuid4().hex[:8]
final_path = upload_dir / f"{unique_id}_{safe_filename}"
```

**3단계: 다운로드 경로 검증** (`shared/sidebar.py`)

```python
# temp 디렉토리 외부 접근 차단
try:
    resolved_path = latest_path.resolve()
    resolved_path.relative_to(temp_root)  # ValueError 발생 시 차단
except Exception:
    is_in_temp = False
```

**차단되는 공격 예시:**
- `../../../etc/passwd` → `_______etc_passwd`
- `<script>alert(1)</script>.xlsx` → `_script_alert_1___script_.xlsx`

### Q: 업로드된 파일은 언제 삭제되나요?

**A:** TTL + 개수 기반 자동 정리 정책을 적용합니다.

```python
# shared/file_utils.py
DEFAULT_TTL_DAYS = 7      # 7일 후 자동 삭제
max_files = 10            # 사용자당 최대 10개 파일 유지
```

| 정리 조건 | 동작 |
|----------|------|
| 7일 경과 | 자동 삭제 |
| 10개 초과 | 오래된 파일부터 삭제 |
| 빈 디렉토리 | 자동 삭제 |

---

## 3. 데이터 저장 및 격리

### Q: 채팅 히스토리는 어디에 저장되나요?

**A:** 2-tier 저장 방식을 사용합니다.

| 우선순위 | 저장소 | 용도 | 설정 |
|----------|--------|------|------|
| 1 | Supabase | 영구 저장 (프로덕션) | `SUPABASE_URL`, `SUPABASE_KEY` |
| 2 | 로컬 파일 | Fallback (개발/오프라인) | `chat_history/<user_id>/` |

```python
# agent/memory.py
if SUPABASE_AVAILABLE:
    self.db = SupabaseStorage(user_id=self.user_id)
else:
    # 로컬 파일 fallback
    self.storage_dir = Path(storage_dir) / self.user_id
```

### Q: Supabase에서 사용자 데이터 격리는?

**A:** 모든 쿼리에 `user_id` 필터를 적용합니다.

```python
# agent/supabase_storage.py
response = self.client.table("chat_sessions").select("*").eq(
    "user_id", self.user_id  # 본인 데이터만 조회
).execute()
```

**테이블 구조:**
- `chat_sessions`: 세션 메타데이터 (session_id, user_id, user_info, ...)
- `chat_messages`: 개별 메시지 (session_id, user_id, role, content, ...)
- `feedback`: 피드백 데이터 (session_id, user_id, feedback_type, ...)

### Q: 세션 ID는 안전한가요?

**A:** 세션 ID도 정화 처리됩니다.

```python
# agent/memory.py
def _sanitize_session_id(session_id: str, max_length: int = 100) -> str:
    # 경로 구분자 제거
    sanitized = session_id.replace("/", "_").replace("\\", "_").replace("..", "_")
    # 특수문자 제거
    sanitized = re.sub(r'[^\w가-힣\-]', '_', sanitized, flags=re.UNICODE)
    # 길이 제한
    return sanitized[:max_length] or "unnamed"
```

---

## 4. 도구 실행 보안

### Q: 외부 스크립트 실행 시 보안은?

**A:** 화이트리스트 + subprocess 안전 호출을 적용합니다.

**스크립트 화이트리스트:**

```python
# agent/tools.py
script_map = {
    "basic": "generate_exit_projection.py",
    "advanced": "generate_advanced_exit_projection.py",
    "complete": "generate_complete_exit_projection.py"
}
```

**안전한 subprocess 호출:**

```python
result = subprocess.run(
    [
        sys.executable,  # Python 실행 파일
        str(script_path),
        "--investment_amount", str(investment_amount),
        # ... 리스트 형태로 인자 전달 (셸 해석 없음)
    ],
    capture_output=True,
    text=True,
    cwd=str(PROJECT_ROOT)  # 작업 디렉토리 고정
)
```

**보안 포인트:**
- `shell=False` (기본값): 셸 인젝션 방지
- 리스트 형태 인자: 공백/특수문자 안전 처리
- 모든 값은 `str()` 변환 후 전달

### Q: 도구 호출 무한 루프는 어떻게 방지하나요?

**A:** 최대 도구 호출 횟수를 제한합니다.

```python
# agent/vc_agent.py
MAX_TOOL_STEPS = 15

if self._tool_step_count > MAX_TOOL_STEPS:
    yield "[시스템] 도구 호출 횟수 제한에 도달했습니다."
    return
```

---

## 5. 외부 서비스 연동

### Q: yfinance API 호출은 안전한가요?

**A:** Rate Limit 대응 및 에러 처리가 구현되어 있습니다.

```python
# agent/tools.py
def _fetch_stock_info(ticker: str) -> dict:
    # Rate Limit 방지 딜레이 (5~10초)
    delay = random.uniform(5.0, 10.0)
    time.sleep(delay)

    # 최대 3회 재시도
    for attempt in range(3):
        try:
            stock = yf.Ticker(ticker)
            return stock.info
        except Exception:
            # 실패 시 30초 대기 후 재시도
            time.sleep(30 + random.uniform(0, 10))
```

**보안 고려사항:**
- yfinance는 읽기 전용 API (데이터 조회만)
- 공개 정보만 조회 (민감 정보 아님)
- 사용자 입력 티커는 yfinance 라이브러리가 처리

### Q: Supabase 연결은 안전한가요?

**A:** HTTPS 및 API 키 인증을 사용합니다.

```python
# agent/supabase_storage.py
def get_supabase_client() -> Optional["Client"]:
    # Streamlit secrets에서 먼저 시도
    url = st.secrets.get("supabase", {}).get("url")
    key = st.secrets.get("supabase", {}).get("key")

    # 환경변수 fallback
    if not url:
        url = os.getenv("SUPABASE_URL")
    if not key:
        key = os.getenv("SUPABASE_KEY")

    return create_client(url, key)
```

**보안 권장사항:**
- `anon` 키 사용 (제한된 접근)
- Row Level Security (RLS) 정책 설정 권장

---

## 6. 로깅 및 감사

### Q: 로그에는 어떤 정보가 기록되나요?

**A:** 민감 정보를 제외한 운영 정보만 기록됩니다.

```python
# shared/logging_config.py
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
```

| 기록되는 정보 | 기록되지 않는 정보 |
|--------------|-------------------|
| 파일 업로드/삭제 (파일명) | API 키 원문 |
| 세션 생성/로드 | 파일 내용 |
| 도구 실행 결과 (성공/실패) | 채팅 내용 (별도 저장) |
| 에러 스택 트레이스 | 투자 금액 등 재무 데이터 |

### Q: 로그 파일은 어디에 저장되나요?

**A:** `logs/` 디렉토리에 일별로 저장됩니다.

```
logs/
├── app_20241217.log
├── app_20241218.log
└── ...
```

| 출력 대상 | 로그 레벨 |
|----------|----------|
| 파일 | DEBUG 이상 |
| 콘솔 | WARNING 이상 |

---

## 7. 배포 보안

### Q: 민감 정보 관리는 어떻게 하나요?

**A:** 환경 변수 또는 Streamlit secrets를 사용합니다.

**로컬 개발:**

```bash
# .env (Git에 커밋하지 않음)
ANTHROPIC_API_KEY=sk-ant-api03-...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
```

**Streamlit Cloud:**

```toml
# .streamlit/secrets.toml
[supabase]
url = "https://xxx.supabase.co"
key = "eyJ..."
```

### Q: .gitignore에 포함된 파일은?

**A:** 민감 정보 및 임시 파일이 제외됩니다.

```gitignore
# 환경변수
.env
!.env.example

# Streamlit secrets
.streamlit/secrets.toml

# 임시 파일
temp/
logs/
chat_history/
feedback/

# 출력 파일
*.xlsx
!example/*.xlsx
```

---

## 8. 보안 체크리스트

### 배포 전 확인사항

- [ ] `.env` 파일이 `.gitignore`에 포함됨
- [ ] `.streamlit/secrets.toml`이 `.gitignore`에 포함됨
- [ ] `temp/`, `logs/`, `chat_history/`가 `.gitignore`에 포함됨
- [ ] API 키가 코드에 하드코딩되지 않음
- [ ] 로그에 민감 정보가 출력되지 않음
- [ ] Supabase RLS 정책 설정됨 (프로덕션)

### 운영 중 모니터링

- [ ] `logs/` 디렉토리에서 `WARNING`/`ERROR` 로그 확인
- [ ] `temp/` 디렉토리 크기 모니터링
- [ ] 비정상적인 API 사용량 모니터링

---

## 9. 알려진 제한사항

### 현재 구현되지 않은 보안 기능

| 기능 | 상태 | 비고 |
|------|------|------|
| IP 기반 접근 제어 | 미구현 | Streamlit Cloud에서 제한적 |
| Rate Limiting (사용자별) | 미구현 | API 키 비용으로 간접 제한 |
| 파일 내용 악성코드 검사 | 미구현 | 엑셀/PDF 파싱만 수행 |
| 데이터 암호화 at rest | 미구현 | Supabase 의존 |
| 감사 로그 (Audit Log) | 부분 구현 | 도구 호출만 로깅 |

### 권장 보안 강화 방안

**프로덕션 환경:**
- Supabase Row Level Security (RLS) 정책 설정
- 파일 스토리지를 S3/GCS로 이전
- WAF(Web Application Firewall) 적용

**엔터프라이즈 환경:**
- SSO/SAML 인증 연동
- VPC 내부 배포
- 감사 로그 중앙 수집 (ELK, Datadog 등)

---

## 관련 파일

| 파일 | 역할 |
|------|------|
| [shared/auth.py](shared/auth.py) | API 키 인증 |
| [shared/file_utils.py](shared/file_utils.py) | 파일 업로드 보안 |
| [agent/memory.py](agent/memory.py) | 세션 관리 |
| [agent/supabase_storage.py](agent/supabase_storage.py) | 영구 저장 |
| [shared/logging_config.py](shared/logging_config.py) | 로깅 설정 |
| [.gitignore](.gitignore) | 민감 파일 제외 |

---

## 보안 취약점 신고

보안 취약점을 발견하셨다면 다음 채널로 신고해주세요:

- GitHub Issues (공개 가능한 경우)
- 담당자 이메일 (민감한 취약점)

신고된 취약점은 24시간 내 확인하고, 수정 계획을 공유합니다.

---

*최종 업데이트: 2025-12-17*
*버전: v0.3.0*
