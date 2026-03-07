"""
Defensive batch PDF processor.

기업별로 폴더/파일명에서 회사명과 문서 종류를 추론하고,
파싱 실패 시에도 최대한 메타데이터를 보존하여 results/에 저장합니다.

사용법:
    python3 scripts/batch_process.py companyData/
    python3 scripts/batch_process.py companyData/ --workers 3 --output results/
    python3 scripts/batch_process.py companyData/ --dry-run   # API 호출 없이 분류만 확인
"""

import argparse
import json
import logging
import re
import sys
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional


def _nfc(s: str) -> str:
    """macOS APFS는 한글 파일명을 NFD로 저장 → NFC로 정규화해야 regex가 작동."""
    return unicodedata.normalize("NFC", s)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dolphin_service.processor import ClaudeVisionProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── 문서 종류 분류 패턴 (파일명 기반, 우선순위 순) ──────────────────────────

DOC_PURPOSE_PATTERNS = [
    (r"투자\s*검토", "investment_review"),
    (r"표준\s*재무제표|재무제표\s*증명|재무제표", "financial_statement"),
    (r"주주\s*명부|cap.?table", "shareholder_register"),
    (r"IR\s*자료|IR자료|사업계획서|사업\s*소개", "ir_deck"),
    (r"사업자\s*등록", "business_registration"),
    (r"법인\s*등기", "corporate_registry"),
    (r"정관", "articles_of_incorporation"),
    (r"임직원\s*명부|직원\s*명부|4대보험", "employee_list"),
    (r"인증서|벤처\s*기업|중소기업", "certificate"),
    (r"창업\s*기업\s*확인|확인서", "startup_certificate"),
    (r"계약서", "contract"),
]

# 회사명 추출 시 무시할 토큰 (법인 유형, 프로젝트 코드, generic 단어)
_IGNORE_TOKENS = {
    "주식회사", "유한회사", "합자회사", "사단법인", "재단법인",
    "MYSC", "mysc",
    # generic 단어 — 단독으로는 회사명이 될 수 없음
    "자료", "명부", "사본", "증명", "등본", "원본", "확인서", "보고서",
    "내역", "현황", "목록", "계획", "계획서", "신청서",
}

_DATE_PATTERN = re.compile(r"^\d{6,8}$")   # 251211, 20251211
_NUM_PREFIX = re.compile(r"^\d+[-\d]*\.\s*")  # "6-1. ", "10. "

# ─── 회사명 추론 ─────────────────────────────────────────────────────────────

def _extract_company_from_filename(filename: str) -> Optional[str]:
    """파일명에서 회사명 추출.

    패턴: {번호}. {PREFIX}_{문서종류}_{회사명}_{날짜}.pdf
    예: "1. MYSC_투자검토자료_스트레스솔루션_251211.pdf"
        "2. MYSC_주주명부('25.10.16)_주식회사 스트레스솔루션.pdf"
    """
    stem = _NUM_PREFIX.sub("", _nfc(Path(filename).stem))
    # 괄호와 그 내용 제거 — "('25.10.16)" 같은 날짜 괄호, "(말소사항포함)" 같은 설명 제거
    stem_clean = re.sub(r"\([^)]*\)", "", stem).strip()

    # "주식회사 X" or "X주식회사" 먼저 탐지 — 한글 단어만 캡처 (underscore 포함 방지)
    for s in (stem_clean, stem):
        corp_match = re.search(r"주식회사\s+([가-힣]+)|([가-힣]+)\s*주식회사", s)
        if corp_match:
            name = corp_match.group(1) or corp_match.group(2)
            if name and name not in _IGNORE_TOKENS:
                return name.strip()

    tokens = re.split(r"[_\s]+", stem_clean)
    candidates = []
    for tok in tokens:
        tok = tok.strip("().'\"-")
        if not tok:
            continue
        if tok in _IGNORE_TOKENS:
            continue
        if _DATE_PATTERN.match(tok):
            continue
        if re.match(r"^\d", tok):
            continue
        if any(re.search(p, tok) for p, _ in DOC_PURPOSE_PATTERNS):
            continue
        # 괄호 설명형 단어 제외 (예: "말소사항포함", "4대보험가입자")
        if re.search(r"포함|제외|사항|가입자|명부$", tok):
            continue
        if re.search(r"[가-힣]", tok) and len(tok) >= 2:
            candidates.append(tok)

    return candidates[-1] if candidates else None


def infer_company_name(
    pdf_path: Path,
    parsed_result: Optional[dict],
    folder_inferred: Optional[str] = None,
) -> tuple:
    """회사명 방어적 추론. (name, source) 반환.

    source:
      'content'  — 파싱 JSON에서 직접
      'filename' — 파일명 regex
      'sibling'  — 같은 폴더 다른 파일에서 추론
      'folder'   — 부모 폴더명
      'stem'     — 파일명 stem (최후 수단)
    """
    # L1: 파싱된 content
    if parsed_result and parsed_result.get("success"):
        sc = parsed_result.get("structured_content", {})
        info = sc.get("company_info", {}) if isinstance(sc, dict) else {}
        name = info.get("name") or info.get("company_name") or info.get("회사명")
        if name and len(str(name).strip()) >= 2:
            return str(name).strip(), "content"

    # L2: 파일명 regex
    name = _extract_company_from_filename(pdf_path.name)
    if name:
        return name, "filename"

    # L3: 같은 폴더의 sibling 파일에서 이미 추론된 회사명
    if folder_inferred:
        return folder_inferred, "sibling"

    # L4: 부모 폴더명 (generic 이름 제외)
    _generic = {"companyData", "data", "inputs", "docs", "pdfs", "files", "."}
    parent = pdf_path.parent.name
    if parent not in _generic and re.search(r"[가-힣A-Za-z]", parent):
        return parent, "folder"

    # L5: 파일명 stem
    return _NUM_PREFIX.sub("", pdf_path.stem).strip() or pdf_path.stem, "stem"


def classify_doc_purpose(filename: str) -> str:
    """파일명에서 문서 목적 분류 (API 없이)."""
    normalized = _nfc(filename)
    for pattern, purpose in DOC_PURPOSE_PATTERNS:
        if re.search(pattern, normalized):
            return purpose
    return "unknown"


# ─── 진행 상태 추적 ──────────────────────────────────────────────────────────

class ProgressTracker:
    """JSONL append-write 방식으로 처리 결과 저장 → resume 가능."""

    def __init__(self, progress_file: Path):
        self.path = progress_file
        self._lock = threading.Lock()
        self._done: set = set()
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get("status") in ("ok", "failed_permanent"):
                        self._done.add(rec["file"])
                except (json.JSONDecodeError, KeyError):
                    pass

    def is_done(self, file_path: str) -> bool:
        return file_path in self._done

    def record(self, record: dict):
        with self._lock:
            self._done.add(record["file"])
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ─── 핵심 처리 ───────────────────────────────────────────────────────────────

def process_one(
    pdf_path: Path,
    output_dir: Path,
    processor: ClaudeVisionProcessor,
    tracker: ProgressTracker,
    folder_company_cache: dict,
    dry_run: bool = False,
) -> dict:
    """단일 PDF 처리 후 결과를 output_dir/{company_name}/ 에 저장."""
    file_str = str(pdf_path)

    if tracker.is_done(file_str):
        logger.info(f"  SKIP: {pdf_path.name}")
        return {"file": file_str, "status": "skipped"}

    doc_purpose = classify_doc_purpose(pdf_path.name)

    result: Optional[dict] = None
    error: Optional[str] = None

    if not dry_run:
        try:
            result = processor.process_pdf(file_str, output_mode="structured")
        except Exception as e:
            error = str(e)
            logger.warning(f"  ERROR {pdf_path.name}: {e}")

    # 방어적 회사명 추론
    folder_key = str(pdf_path.parent)
    cached_company = folder_company_cache.get(folder_key)
    company_name, company_source = infer_company_name(pdf_path, result, cached_company)

    # 신뢰도 높은 소스면 폴더 내 공유
    if company_source in ("content", "filename"):
        folder_company_cache.setdefault(folder_key, company_name)

    record = {
        "file": file_str,
        "filename": pdf_path.name,
        "company_name": company_name,
        "company_name_source": company_source,
        "doc_purpose": doc_purpose,
        "processed_at": datetime.utcnow().isoformat(),
        "status": "ok" if error is None else "failed",
        "error": error,
        "dry_run": dry_run,
    }

    if result and result.get("success"):
        record.update({
            "doc_type": result.get("doc_type"),
            "total_pages": result.get("total_pages"),
            "processing_method": result.get("processing_method"),
            "processing_time_seconds": result.get("processing_time_seconds"),
            "cache_hit": result.get("cache_hit", False),
            "financial_tables": result.get("financial_tables", {}),
            "structured_content": result.get("structured_content", {}),
        })
        record["status"] = "ok"

    # 기업별 폴더에 결과 저장 (성공 + 실패 모두)
    safe_company = re.sub(r"[^\w가-힣-]", "_", company_name)
    company_dir = output_dir / safe_company
    company_dir.mkdir(parents=True, exist_ok=True)

    safe_stem = re.sub(r"[^\w가-힣-]", "_", pdf_path.stem)[:60]
    suffix = ".json" if record["status"] == "ok" else ".error.json"
    out_file = company_dir / f"{safe_stem}{suffix}"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    tracker.record(record)
    return record


# ─── 배치 실행 ───────────────────────────────────────────────────────────────

def _prescan_folder_companies(pdf_files: list) -> dict:
    """처리 전에 폴더별 회사명을 미리 확정.

    파일명 기반 추출이 가능한 파일들로 폴더 캐시를 채워두면
    병렬 처리 시 sibling 추론이 안정적으로 작동한다.
    """
    cache: dict = {}
    for pdf_path in pdf_files:
        folder_key = str(pdf_path.parent)
        if folder_key in cache:
            continue
        name = _extract_company_from_filename(pdf_path.name)
        if name:
            cache[folder_key] = name
    return cache


def run_batch(
    input_dir: Path,
    output_dir: Path,
    workers: int,
    dry_run: bool,
    rate_limit_rps: float,
):
    pdf_files = sorted(input_dir.rglob("*.pdf"))
    if not pdf_files:
        logger.error(f"No PDFs found in {input_dir}")
        sys.exit(1)

    logger.info(f"Found {len(pdf_files)} PDFs")

    output_dir.mkdir(parents=True, exist_ok=True)
    tracker = ProgressTracker(output_dir / "progress.jsonl")
    processor = ClaudeVisionProcessor()

    _min_interval = 1.0 / rate_limit_rps if rate_limit_rps > 0 else 0.0
    _last_call = [0.0]
    _time_lock = threading.Lock()

    # 병렬 처리 전에 폴더별 회사명 미리 확정
    folder_company_cache: dict = _prescan_folder_companies(pdf_files)
    logger.info(f"Pre-scanned {len(folder_company_cache)} folders: {list(folder_company_cache.values())}")

    def throttled_process(pdf_path: Path) -> dict:
        if _min_interval > 0:
            with _time_lock:
                wait = _min_interval - (time.time() - _last_call[0])
                if wait > 0:
                    time.sleep(wait)
                _last_call[0] = time.time()
        return process_one(
            pdf_path, output_dir, processor, tracker,
            folder_company_cache, dry_run=dry_run,
        )

    stats = {"ok": 0, "failed": 0, "skipped": 0}

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(throttled_process, p): p for p in pdf_files}
        for future in as_completed(futures):
            pdf_path = futures[future]
            try:
                rec = future.result()
                status = rec.get("status", "failed")
                stats[status] = stats.get(status, 0) + 1
                logger.info(
                    f"  [{status}] {pdf_path.name} "
                    f"-> {rec.get('company_name', '?')} ({rec.get('company_name_source', '?')}) "
                    f"/ {rec.get('doc_purpose', '?')}"
                )
            except Exception as e:
                stats["failed"] += 1
                logger.error(f"  [error] {pdf_path.name}: {e}")

    total = sum(stats.values())
    logger.info(
        f"\nDone: {total} files — "
        f"ok={stats.get('ok',0)}, failed={stats.get('failed',0)}, "
        f"skipped={stats.get('skipped',0)}"
    )
    logger.info(f"Results: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Defensive batch PDF processor")
    parser.add_argument("input_dir", help="PDF 폴더")
    parser.add_argument("--output", default="results", help="출력 폴더 (기본: results/)")
    parser.add_argument("--workers", type=int, default=3, help="동시 PDF 수 (기본: 3)")
    parser.add_argument(
        "--rate-limit", type=float, default=2.0,
        help="초당 최대 API 요청 수 (기본: 2.0, 0=무제한)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="API 없이 분류/회사명 추론만 확인",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    if not input_dir.is_dir():
        logger.error(f"Not a directory: {input_dir}")
        sys.exit(1)

    if args.dry_run:
        logger.info("=== DRY RUN (no API calls) ===")

    run_batch(
        input_dir=input_dir,
        output_dir=Path(args.output).resolve(),
        workers=args.workers,
        dry_run=args.dry_run,
        rate_limit_rps=args.rate_limit,
    )


if __name__ == "__main__":
    main()
