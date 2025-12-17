# Production Level 개선 계획

## 개요

MVP에서 상용 프로덕트로 전환을 위한 개선 계획입니다.
우선순위는 P0 (필수) > P1 (신뢰성) > P2 (유지보수) 순서입니다.

---

## P0: 상용 서비스 필수 (즉시 수정)

### 1. 파일 업로드 보안 강화

**문제점:**
- `temp/<원본파일명>`에 저장 → 경로 조작, 동명이인 덮어쓰기, 세션 간 유출 위험
- 위치: `shared/sidebar.py:34`, `pages/2_Peer_PER_Analysis.py:60`

**해결 방안:**
```python
# shared/file_utils.py (신규)
import uuid
import re
from pathlib import Path

def sanitize_filename(filename: str) -> str:
    """파일명에서 위험한 문자 제거"""
    # 경로 구분자 제거
    filename = filename.replace("/", "_").replace("\\", "_")
    # 허용: 알파벳, 숫자, 한글, 언더스코어, 하이픈, 점
    sanitized = re.sub(r'[^\w\s가-힣.\-]', '_', filename, flags=re.UNICODE)
    return sanitized.strip('_') or "unnamed"

def get_secure_upload_path(user_id: str, original_filename: str) -> Path:
    """사용자별 격리된 업로드 경로 생성"""
    safe_filename = sanitize_filename(original_filename)
    unique_id = uuid.uuid4().hex[:8]

    # temp/<user_id>/<unique_id>_<safe_filename>
    upload_dir = Path("temp") / user_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    return upload_dir / f"{unique_id}_{safe_filename}"
```

**수정 파일:**
- `shared/sidebar.py` - `get_secure_upload_path()` 사용
- `pages/2_Peer_PER_Analysis.py` - 동일 적용

---

### 2. 로컬 저장 실패 로깅

**문제점:**
- `except: pass`로 실패 무시 → 장애 은닉, 데이터 유실
- 위치: `agent/memory.py:147`, `agent/feedback.py:100`

**해결 방안:**
```python
# agent/memory.py
from shared.logging_config import get_logger
logger = get_logger("memory")

def _save_session(self):
    try:
        with open(self.current_session_file, 'w', encoding='utf-8') as f:
            json.dump(self.session_metadata, f, ensure_ascii=False, indent=2)
    except PermissionError as e:
        logger.error(f"Permission denied saving session: {e}")
    except OSError as e:
        logger.error(f"OS error saving session: {e}")
    except Exception as e:
        logger.error(f"Unexpected error saving session: {e}", exc_info=True)
```

**수정 파일:**
- `agent/memory.py` - `_save_session()` 로깅 추가
- `agent/feedback.py` - `add_feedback()` 로깅 추가

---

### 3. logging_config.py Git 추적

**문제점:**
- `shared/logging_config.py`가 Git 미추적 상태
- 배포 시 ImportError 발생 가능

**해결 방안:**
```bash
git add shared/logging_config.py
git commit -m "Add production logging configuration"
```

**추가 개선:**
- 로그 디렉토리 `.gitignore`에 추가
- 로그 보관 정책 문서화 (7일 보관 등)

---

### 4. UI 문구 정리

**문제점:**
- "Streamlit Cloud SSO 인증" 문구가 실제 구현(API Key 인증)과 불일치
- 위치: `shared/sidebar.py:17`

**해결 방안:**
```python
# 변경 전
st.caption("Streamlit Cloud SSO 인증")

# 변경 후
st.caption("Claude API Key 인증")
```

---

## P1: 신뢰성/확장성 (단기 개선)

### 5. subprocess 스크립트 → 라이브러리 함수화

**문제점:**
- 툴이 스크립트를 subprocess로 호출 → 오류 핸들링, 테스트, 성능 저하
- 위치: `agent/tools.py:631`

**해결 방안:**
```python
# scripts/exit_projection_lib.py (신규)
def generate_basic_exit_projection(
    investment_amount: int,
    price_per_share: int,
    shares: int,
    total_shares: int,
    net_income_company: int,
    net_income_reviewer: int,
    target_year: int,
    company_name: str,
    per_multiples: List[float],
    output_path: str
) -> Dict[str, Any]:
    """Exit 프로젝션 생성 (라이브러리 버전)"""
    # 기존 스크립트 로직을 함수로 이동
    ...
    return {"success": True, "output_file": output_path}

# agent/tools.py
def execute_generate_exit_projection(...):
    from scripts.exit_projection_lib import generate_basic_exit_projection
    return generate_basic_exit_projection(...)
```

**장점:**
- 오류 핸들링 일관성
- 단위 테스트 가능
- subprocess 오버헤드 제거
- 리소스 관리 용이

---

### 6. 도구 호출 무한 루프 방지

**문제점:**
- 스트리밍 중 tool 호출이 재귀적으로 이어질 수 있음
- 위치: `agent/vc_agent.py:500`

**해결 방안:**
```python
# agent/vc_agent.py

MAX_TOOL_STEPS = 10  # 최대 도구 호출 횟수
TOOL_TIMEOUT_SECONDS = 300  # 5분 타임아웃

class VCAgent:
    def __init__(self, ...):
        ...
        self._tool_step_count = 0

    async def _continue_conversation(self) -> AsyncIterator[str]:
        self._tool_step_count += 1

        if self._tool_step_count > MAX_TOOL_STEPS:
            logger.warning(f"Tool step limit reached: {MAX_TOOL_STEPS}")
            yield "\n\n[시스템] 도구 호출 횟수 제한에 도달했습니다. 대화를 계속하려면 새로운 메시지를 입력하세요."
            return

        # 기존 로직...

    async def chat(self, user_message: str, mode: str = "exit"):
        self._tool_step_count = 0  # 새 메시지마다 초기화
        # 기존 로직...
```

---

### 7. 외부 API 타임아웃/재시도

**문제점:**
- yfinance, Claude API 호출에 타임아웃/재시도 없음
- 위치: `agent/tools.py:910`, `agent/vc_agent.py:55`

**해결 방안:**
```python
# agent/tools.py
import time
from functools import wraps

def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """지수 백오프 재시도 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Retry {attempt + 1}/{max_retries} after {delay}s: {e}")
                    time.sleep(delay)
        return wrapper
    return decorator

@retry_with_backoff(max_retries=3)
def execute_get_stock_financials(ticker: str) -> Dict[str, Any]:
    import yfinance as yf
    stock = yf.Ticker(ticker)
    # timeout은 yfinance 내부에서 처리
    ...
```

---

## P2: 유지보수/품질 (중기 개선)

### 8. CLI asyncio 패턴 수정

**문제점:**
- `asyncio.get_event_loop()` 사용 → Python 3.12에서 deprecated
- 위치: `cli.py:48`

**해결 방안:**
```python
# cli.py
import asyncio

@cli.command()
def chat():
    """대화형 분석 모드"""
    ...

    async def run_chat():
        while True:
            user_input = click.prompt("You", type=str)
            if user_input.lower() in ["exit", "quit"]:
                break

            async for chunk in agent.chat(user_input):
                click.echo(chunk, nl=False)
            click.echo()

    asyncio.run(run_chat())  # Python 3.10+ 표준
```

---

## 구현 우선순위

| 순서 | 항목 | 예상 시간 | 위험도 |
|------|------|----------|--------|
| 1 | logging_config.py Git 추적 | 5분 | 높음 (배포 실패) |
| 2 | UI 문구 정리 | 5분 | 중간 (사용자 혼란) |
| 3 | 파일 업로드 보안 | 30분 | 높음 (보안) |
| 4 | 로컬 저장 실패 로깅 | 15분 | 중간 (장애 감지) |
| 5 | 도구 호출 무한 루프 방지 | 20분 | 중간 (서비스 안정성) |
| 6 | 외부 API 타임아웃/재시도 | 30분 | 중간 (안정성) |
| 7 | subprocess → 라이브러리 | 2시간 | 낮음 (리팩토링) |
| 8 | CLI asyncio 수정 | 10분 | 낮음 (CLI 전용) |

---

## 향후 고려사항 (P3)

1. **데이터 거버넌스**
   - 개인정보/투자자료 보관 정책
   - 삭제 요청 처리 메커니즘
   - Supabase RLS/암호화/감사로그

2. **패키징/빌드 표준화**
   - `pyproject.toml` 도입
   - dev 의존성 분리
   - CI/CD 파이프라인 (테스트/린트/타입체크)

3. **인증 체계 개선**
   - 서버측 API 키 관리 (사용자 키 수집 회피)
   - SSO/OAuth 통합
   - 사용량 추적/과금 체계
