#!/usr/bin/env python3
"""
Condition-check fan-out probe for local PDF bundles.

Purpose:
- Estimate cache leverage before running a 700-800 file batch
- Measure company recognition / grouping coverage
- Measure rule-covered conditions vs unresolved conditions

Examples:
    python scripts/condition_fanout_probe.py ./companyData \
      --condition "업력 3년 미만" \
      --condition "매출 10억 미만"

    python scripts/condition_fanout_probe.py ./companyData \
      --conditions-json '["업력 3년 미만","매출 10억 미만"]' \
      --limit 800 \
      --output-dir temp/condition_probe
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ralph.condition_checker import _evaluate_rule_conditions, extract_condition_facts
from ralph.company_encoder import build_company_alias_map
from ralph.playground_parser import extract_text


@dataclass
class ProbeRecord:
    relative_path: str
    digest: str
    pages: int
    text_chars: int
    company_name: str
    company_group_name: str
    company_group_key: str
    rule_count: int
    unresolved_count: int
    unresolved_conditions: List[str]
    company_group_alias_from: str = ""
    error: str = ""


def list_pdf_paths(dataset_dir: Path, *, limit: int | None = None) -> List[Path]:
    if not dataset_dir.exists():
        raise FileNotFoundError(f"dataset dir not found: {dataset_dir}")
    paths = sorted(path for path in dataset_dir.rglob("*.pdf") if path.is_file())
    if limit is not None and limit >= 0:
        return paths[:limit]
    return paths


def file_sha256(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_conditions(conditions: Sequence[str]) -> List[str]:
    return [str(condition).strip() for condition in conditions if str(condition).strip()]


def _load_conditions(args: argparse.Namespace) -> List[str]:
    loaded: List[str] = []
    if args.conditions_json:
        parsed = json.loads(args.conditions_json)
        if not isinstance(parsed, list):
            raise ValueError("--conditions-json must be a JSON array")
        loaded.extend(str(item) for item in parsed)
    loaded.extend(args.condition or [])
    normalized = _normalize_conditions(loaded)
    if not normalized:
        raise ValueError("at least one condition is required")
    return normalized


def analyze_pdf(
    pdf_path: Path,
    *,
    dataset_dir: Path,
    conditions: Sequence[str],
    reference_date: date | None = None,
) -> ProbeRecord:
    digest = file_sha256(pdf_path)
    relative_path = str(pdf_path.relative_to(dataset_dir))
    try:
        text, pages, _ = extract_text(str(pdf_path))
        facts = extract_condition_facts(text, reference_date=reference_date)
        rule_results, facts = _evaluate_rule_conditions(
            text,
            list(conditions),
            reference_date=reference_date,
            facts=facts,
        )
        unresolved_conditions = [
            condition
            for index, condition in enumerate(conditions)
            if index not in rule_results
        ]
        return ProbeRecord(
            relative_path=relative_path,
            digest=digest,
            pages=int(pages or 0),
            text_chars=len(text or ""),
            company_name=str(facts.get("company_name") or ""),
            company_group_name=str(facts.get("company_group_name") or ""),
            company_group_key=str(facts.get("company_group_key") or ""),
            rule_count=len(rule_results),
            unresolved_count=len(unresolved_conditions),
            unresolved_conditions=unresolved_conditions,
        )
    except Exception as exc:
        return ProbeRecord(
            relative_path=relative_path,
            digest=digest,
            pages=0,
            text_chars=0,
            company_name="",
            company_group_name="",
            company_group_key="",
            rule_count=0,
            unresolved_count=len(conditions),
            unresolved_conditions=list(conditions),
            error=str(exc),
        )


def analyze_dataset(
    pdf_paths: Sequence[Path],
    *,
    dataset_dir: Path,
    conditions: Sequence[str],
    reference_date: date | None = None,
) -> Dict[str, Any]:
    normalized_conditions = _normalize_conditions(conditions)
    if not normalized_conditions:
        raise ValueError("conditions must not be empty")

    records = [
        analyze_pdf(
            pdf_path,
            dataset_dir=dataset_dir,
            conditions=normalized_conditions,
            reference_date=reference_date,
        )
        for pdf_path in pdf_paths
    ]

    digest_counts = Counter(record.digest for record in records)
    raw_groups: Dict[str, Dict[str, Any]] = {}
    for record in records:
        if not record.company_group_key:
            continue
        group = raw_groups.setdefault(record.company_group_key, {
            "company_group_key": record.company_group_key,
            "company_group_name": record.company_group_name or record.company_name,
            "file_count": 0,
        })
        group["file_count"] += 1

    alias_map, alias_stats = build_company_alias_map(list(raw_groups.values()))
    alias_merged_files = 0
    for record in records:
        if not record.company_group_key:
            continue
        canonical = alias_map.get(record.company_group_key)
        if not canonical:
            continue
        if canonical["company_group_key"] == record.company_group_key:
            continue
        alias_merged_files += 1
        record.company_group_alias_from = record.company_group_name or record.company_group_key
        record.company_group_name = canonical["company_group_name"]
        record.company_group_key = canonical["company_group_key"]

    company_groups: Dict[str, Dict[str, Any]] = {}
    for record in records:
        if not record.company_group_key:
            continue
        group = company_groups.setdefault(record.company_group_key, {
            "company_group_key": record.company_group_key,
            "company_group_name": record.company_group_name or record.company_name,
            "variants": [],
            "file_count": 0,
            "duplicate_file_count": 0,
            "rule_only_file_count": 0,
            "unresolved_file_count": 0,
        })
        group["file_count"] += 1
        group["duplicate_file_count"] += 1 if digest_counts[record.digest] > 1 else 0
        group["rule_only_file_count"] += 1 if record.unresolved_count == 0 else 0
        group["unresolved_file_count"] += 1 if record.unresolved_count > 0 else 0
        if record.company_name and record.company_name not in group["variants"]:
            group["variants"].append(record.company_name)

    unique_file_digests = len(digest_counts)
    total_files = len(records)
    duplicate_files = total_files - unique_file_digests
    recognized_company_files = sum(1 for record in records if record.company_group_key)
    unrecognized_company_files = total_files - recognized_company_files
    total_rule_conditions = sum(record.rule_count for record in records)
    total_unresolved_conditions = sum(record.unresolved_count for record in records)
    total_conditions = total_files * len(normalized_conditions)
    analyzed_files = sum(1 for record in records if not record.error)
    error_files = total_files - analyzed_files
    rule_only_files = sum(1 for record in records if not record.error and record.unresolved_count == 0)
    avg_text_chars = (
        round(sum(record.text_chars for record in records) / analyzed_files, 1)
        if analyzed_files
        else 0.0
    )
    estimated_result_cache_hits = duplicate_files

    summary = {
        "conditions": list(normalized_conditions),
        "total_files": total_files,
        "analyzed_files": analyzed_files,
        "error_files": error_files,
        "unique_file_digests": unique_file_digests,
        "duplicate_files": duplicate_files,
        "estimated_result_cache_hits": estimated_result_cache_hits,
        "estimated_result_cache_rate": round(estimated_result_cache_hits / total_files, 4) if total_files else 0.0,
        "recognized_company_files": recognized_company_files,
        "unrecognized_company_files": unrecognized_company_files,
        "company_group_count": len(company_groups),
        "company_alias_merge_count": int(alias_stats.get("merged_group_count", 0)),
        "company_alias_merged_files": alias_merged_files,
        "rule_only_files": rule_only_files,
        "rule_coverage_rate": round(total_rule_conditions / total_conditions, 4) if total_conditions else 0.0,
        "unresolved_condition_rate": round(total_unresolved_conditions / total_conditions, 4) if total_conditions else 0.0,
        "avg_text_chars": avg_text_chars,
        "top_company_groups": sorted(
            company_groups.values(),
            key=lambda item: (-int(item["file_count"]), str(item["company_group_name"])),
        )[:20],
    }

    return {
        "summary": summary,
        "records": [record.__dict__ for record in records],
    }


def write_probe_outputs(result: Dict[str, Any], *, output_dir: Path) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "condition_fanout_probe_summary.json"
    records_path = output_dir / "condition_fanout_probe_files.csv"

    summary_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with records_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "relative_path",
                "digest",
                "pages",
                "text_chars",
                "company_name",
                "company_group_name",
                "company_group_key",
                "company_group_alias_from",
                "rule_count",
                "unresolved_count",
                "unresolved_conditions",
                "error",
            ],
        )
        writer.writeheader()
        for record in result["records"]:
            row = dict(record)
            row["unresolved_conditions"] = " | ".join(row.get("unresolved_conditions") or [])
            writer.writerow(row)

    return {
        "summary_json": str(summary_path),
        "records_csv": str(records_path),
    }


def _print_summary(summary: Dict[str, Any]) -> None:
    print(f"총 파일: {summary['total_files']}")
    print(f"분석 성공: {summary['analyzed_files']} / 오류: {summary['error_files']}")
    print(f"고유 문서 해시: {summary['unique_file_digests']} / 중복 파일: {summary['duplicate_files']}")
    print(
        "예상 result-cache 적중: "
        f"{summary['estimated_result_cache_hits']} "
        f"({summary['estimated_result_cache_rate'] * 100:.1f}%)"
    )
    print(
        "기업 인식: "
        f"{summary['recognized_company_files']} / {summary['total_files']} "
        f"(그룹 {summary['company_group_count']}개)"
    )
    if summary.get("company_alias_merge_count", 0):
        print(
            "기업 alias 병합: "
            f"{summary['company_alias_merge_count']}개 그룹, "
            f"{summary['company_alias_merged_files']}개 파일"
        )
    print(
        "규칙 전용 파일: "
        f"{summary['rule_only_files']} / {summary['analyzed_files']} "
        f"(coverage {summary['rule_coverage_rate'] * 100:.1f}%)"
    )
    if summary["top_company_groups"]:
        print("상위 기업 그룹:")
        for group in summary["top_company_groups"][:5]:
            variants = ", ".join(group["variants"][:2]) if group["variants"] else "-"
            print(
                f"  - {group['company_group_name']}: "
                f"{group['file_count']}건, duplicate {group['duplicate_file_count']}건, "
                f"rule-only {group['rule_only_file_count']}건, 표기 {variants}"
            )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe local PDFs for condition-check fan-out readiness.")
    parser.add_argument("dataset_dir", help="directory containing PDF files")
    parser.add_argument("--condition", action="append", default=[], help="repeatable condition string")
    parser.add_argument("--conditions-json", help="JSON array of conditions")
    parser.add_argument("--limit", type=int, default=800, help="maximum number of PDFs to inspect")
    parser.add_argument("--output-dir", help="optional directory to write JSON/CSV probe outputs")
    parser.add_argument(
        "--reference-date",
        help="override reference date for age rules (YYYY-MM-DD)",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    dataset_dir = Path(args.dataset_dir).expanduser().resolve()
    conditions = _load_conditions(args)
    reference_date = date.fromisoformat(args.reference_date) if args.reference_date else None
    pdf_paths = list_pdf_paths(dataset_dir, limit=args.limit)
    result = analyze_dataset(
        pdf_paths,
        dataset_dir=dataset_dir,
        conditions=conditions,
        reference_date=reference_date,
    )
    _print_summary(result["summary"])

    if args.output_dir:
        outputs = write_probe_outputs(result, output_dir=Path(args.output_dir).expanduser().resolve())
        print(f"summary: {outputs['summary_json']}")
        print(f"records: {outputs['records_csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
