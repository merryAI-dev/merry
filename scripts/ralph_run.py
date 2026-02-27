#!/usr/bin/env python3
"""
RALPH Loop CLI Runner.

Usage:
    # Single file
    python scripts/ralph_run.py companyData/4.\ MYSC_사업자등록증.pdf --type business_reg

    # Auto-detect type and run all PDFs in a folder
    python scripts/ralph_run.py companyData/ --all

    # Show stats from PROMPT_LOG.md
    python scripts/ralph_run.py --stats
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ralph.loop import ralph_loop, RalphResult


# Auto-detect document type from filename
DOC_TYPE_HINTS = {
    "사업자등록증": "business_reg",
    "재무제표": "financial_stmt",
    "표준재무제표": "financial_stmt",
    "주주명부": "shareholder",
    "법인등기부등본": "corporate_reg",
    "정관": "articles",
    "인증서": "certificate",
    "창업기업확인서": "certificate",
    "임직원": "employee",
    "투자검토": "ir_review",
    "IR": "ir_deck",
}

# Currently supported types
SUPPORTED_TYPES = {"business_reg", "financial_stmt", "shareholder"}


def detect_doc_type(filename: str) -> str | None:
    """Auto-detect document type from filename."""
    for hint, dtype in DOC_TYPE_HINTS.items():
        if hint in filename:
            return dtype
    return None


def print_result(result: RalphResult, verbose: bool = False) -> None:
    """Pretty-print RALPH result."""
    status = "✅ SUCCESS" if result.success else "❌ FAIL"
    print(f"\n{'='*60}")
    print(f"  {status} ({result.attempts} attempts, {result.total_duration_seconds:.1f}s)")
    print(f"{'='*60}")

    if result.success and result.result:
        r = result.result
        print(f"\n📄 Type: {r.doc_type}")
        print(f"📁 File: {r.source_file}")

        # Print extracted fields (excluding base fields)
        base_fields = {"doc_type", "source_file", "extracted_at", "confidence", "raw_fields", "natural_language"}
        for key, val in r.model_dump().items():
            if key in base_fields:
                continue
            if val is None:
                continue
            if isinstance(val, list):
                print(f"\n  {key}:")
                for item in val:
                    if isinstance(item, dict):
                        fields = ", ".join(f"{k}={v}" for k, v in item.items() if v is not None)
                        print(f"    - {fields}")
                    else:
                        print(f"    - {item}")
            else:
                print(f"  {key}: {val}")

        # Natural language
        if r.natural_language:
            print(f"\n💬 자연어 요약:")
            print(f"  {r.natural_language}")

    # Cost
    cost = result.cost_summary
    print(f"\n💰 토큰: {cost['total_input_tokens']:,} in / {cost['total_output_tokens']:,} out")

    if verbose:
        print(f"\n📋 Iteration History:")
        for it in result.history:
            errs = f", {len(it.errors)} errors" if it.errors else ""
            print(f"  #{it.attempt}: {it.prompt_used} ({it.duration_seconds:.1f}s, {it.model}{errs})")

    print()


def run_single(pdf_path: str, doc_type: str, max_retries: int, verbose: bool) -> bool:
    """Run RALPH on a single file. Returns True if successful."""
    print(f"\n🔄 RALPH Loop: {Path(pdf_path).name} (type={doc_type})")

    def on_iteration(it):
        status = "✅" if not it.errors else f"❌ ({len(it.errors)} errors)"
        print(f"  Attempt {it.attempt}: {status} ({it.duration_seconds:.1f}s)")

    result = ralph_loop(
        pdf_path=pdf_path,
        doc_type=doc_type,
        max_retries=max_retries,
        on_iteration=on_iteration,
    )

    print_result(result, verbose=verbose)

    # Save result JSON
    if result.success and result.result:
        out_dir = PROJECT_ROOT / "ralph" / "results"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{Path(pdf_path).stem}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result.result.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
        print(f"💾 결과 저장: {out_path}")

    return result.success


def run_all(folder: str, max_retries: int, verbose: bool) -> None:
    """Run RALPH on all PDFs in a folder."""
    folder_path = Path(folder)
    if not folder_path.is_dir():
        print(f"❌ 폴더를 찾을 수 없습니다: {folder}")
        return

    pdfs = sorted(folder_path.glob("*.pdf"))
    if not pdfs:
        print(f"❌ PDF 파일이 없습니다: {folder}")
        return

    print(f"\n📂 {len(pdfs)}개 PDF 발견: {folder}")
    print()

    results = {"success": 0, "fail": 0, "skip": 0}

    for pdf in pdfs:
        doc_type = detect_doc_type(pdf.name)
        if doc_type is None:
            print(f"  ⏭  {pdf.name}: 타입 감지 불가 (skip)")
            results["skip"] += 1
            continue

        if doc_type not in SUPPORTED_TYPES:
            print(f"  ⏭  {pdf.name}: {doc_type} (미지원, skip)")
            results["skip"] += 1
            continue

        ok = run_single(str(pdf), doc_type, max_retries, verbose)
        if ok:
            results["success"] += 1
        else:
            results["fail"] += 1

    print(f"\n{'='*60}")
    print(f"  📊 결과: ✅ {results['success']} / ❌ {results['fail']} / ⏭ {results['skip']}")
    print(f"{'='*60}\n")


def show_stats() -> None:
    """Show stats from PROMPT_LOG.md."""
    log_path = PROJECT_ROOT / "ralph" / "PROMPT_LOG.md"
    if not log_path.exists():
        print("프롬프트 로그가 아직 없습니다.")
        return

    content = log_path.read_text(encoding="utf-8")
    runs = content.count("## 20")  # Count dated entries
    successes = content.count("| SUCCESS")
    fails = content.count("| FAIL")

    print(f"\n📊 RALPH 실행 통계")
    print(f"  총 실행: {runs}")
    print(f"  성공: {successes}")
    print(f"  실패: {fails}")
    print(f"\n📝 로그 파일: {log_path}")
    print(f"   크기: {log_path.stat().st_size / 1024:.1f} KB")


def main():
    parser = argparse.ArgumentParser(description="RALPH Loop CLI Runner")
    parser.add_argument("path", nargs="?", help="PDF file or directory path")
    parser.add_argument("--type", "-t", help="Document type (business_reg, financial_stmt, shareholder)")
    parser.add_argument("--all", action="store_true", help="Process all PDFs in directory")
    parser.add_argument("--retries", "-r", type=int, default=3, help="Max retries (default: 3)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--stats", action="store_true", help="Show PROMPT_LOG stats")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quiet noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)

    if args.stats:
        show_stats()
        return

    if not args.path:
        parser.print_help()
        return

    path = Path(args.path)

    if args.all or path.is_dir():
        run_all(str(path), args.retries, args.verbose)
    elif path.is_file():
        doc_type = args.type
        if not doc_type:
            doc_type = detect_doc_type(path.name)
            if not doc_type:
                print(f"❌ 문서 타입을 감지할 수 없습니다. --type 옵션을 사용하세요.")
                print(f"   사용 가능: {', '.join(SUPPORTED_TYPES)}")
                sys.exit(1)
            print(f"  📋 타입 자동 감지: {doc_type}")

        if doc_type not in SUPPORTED_TYPES:
            print(f"❌ 미지원 문서 타입: {doc_type}")
            print(f"   지원: {', '.join(SUPPORTED_TYPES)}")
            sys.exit(1)

        ok = run_single(str(path), doc_type, args.retries, args.verbose)
        sys.exit(0 if ok else 1)
    else:
        print(f"❌ 파일/폴더를 찾을 수 없습니다: {args.path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
