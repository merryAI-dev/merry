#!/usr/bin/env python3
"""Evaluate condition_check JSON artifacts against a goldset manifest."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _normalize_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _normalize_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = _normalize_text(value).lower()
    return text in {"1", "true", "pass", "yes", "y", "충족", "적합"}


@dataclass
class GoldsetRecord:
    record_id: str
    filename: str
    policy_id: str
    policy_text: str
    expected_result: bool
    company_group_key: str = ""
    relative_path: str = ""
    company_group_name: str = ""
    expected_evidence: List[str] | None = None
    notes: str = ""
    tags: List[str] | None = None
    review_status: str = "confirmed"

    @classmethod
    def from_json(cls, payload: Dict[str, Any]) -> "GoldsetRecord":
        required = ["record_id", "filename", "policy_id", "policy_text", "review_status"]
        missing = [key for key in required if not _normalize_text(payload.get(key))]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")
        return cls(
            record_id=_normalize_text(payload["record_id"]),
            filename=Path(_normalize_text(payload["filename"])).name,
            policy_id=_normalize_text(payload["policy_id"]),
            policy_text=_normalize_text(payload["policy_text"]),
            expected_result=_normalize_bool(payload.get("expected_result")),
            company_group_key=_normalize_text(payload.get("company_group_key")).lower(),
            relative_path=_normalize_text(payload.get("relative_path")),
            company_group_name=_normalize_text(payload.get("company_group_name")),
            expected_evidence=[_normalize_text(item) for item in payload.get("expected_evidence") or [] if _normalize_text(item)],
            notes=_normalize_text(payload.get("notes")),
            tags=[_normalize_text(item) for item in payload.get("tags") or [] if _normalize_text(item)],
            review_status=_normalize_text(payload.get("review_status")),
        )


@dataclass
class EvalDetail:
    record_id: str
    filename: str
    policy_id: str
    policy_text: str
    expected_result: bool
    actual_result: Optional[bool]
    outcome: str
    company_group_key: str = ""
    evidence: str = ""
    evidence_hit: bool = False
    notes: str = ""


def load_goldset_manifest(path: Path) -> List[GoldsetRecord]:
    records: List[GoldsetRecord] = []
    for index, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid jsonl at line {index}: {exc}") from exc
        records.append(GoldsetRecord.from_json(payload))
    return records


def build_result_index(result_payload: Dict[str, Any]) -> Dict[Tuple[str, str, str], Dict[str, Any]]:
    index: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    rows = result_payload.get("results")
    if not isinstance(rows, list):
        return index
    for row in rows:
        if not isinstance(row, dict):
            continue
        filename = Path(_normalize_text(row.get("filename"))).name
        group_key = _normalize_text(row.get("company_group_key")).lower()
        for condition in row.get("conditions") or []:
            if not isinstance(condition, dict):
                continue
            policy_text = _normalize_text(condition.get("condition"))
            if not filename or not policy_text:
                continue
            index[(filename, policy_text, group_key)] = {
                "result": condition.get("result"),
                "evidence": _normalize_text(condition.get("evidence")),
                "company_group_key": group_key,
            }
            index[(filename, policy_text, "")] = {
                "result": condition.get("result"),
                "evidence": _normalize_text(condition.get("evidence")),
                "company_group_key": group_key,
            }
    return index


def _pick_result(
    record: GoldsetRecord,
    result_index: Dict[Tuple[str, str, str], Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    keys = [
        (record.filename, record.policy_text, record.company_group_key),
        (record.filename, record.policy_text, ""),
    ]
    for key in keys:
        if key in result_index:
            return result_index[key]
    return None


def _evidence_hit(expected_evidence: Iterable[str], actual_evidence: str) -> bool:
    normalized_actual = _normalize_text(actual_evidence).lower()
    expected = [_normalize_text(item).lower() for item in expected_evidence if _normalize_text(item)]
    if not expected:
        return False
    return any(token in normalized_actual for token in expected)


def evaluate_goldset(
    goldset_records: List[GoldsetRecord],
    result_payload: Dict[str, Any],
) -> Dict[str, Any]:
    result_index = build_result_index(result_payload)
    details: List[EvalDetail] = []
    policy_totals: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for record in goldset_records:
        result = _pick_result(record, result_index)
        if result is None:
            outcome = "missing"
            actual = None
            evidence = ""
            evidence_hit = False
        else:
            actual = _normalize_bool(result.get("result"))
            evidence = _normalize_text(result.get("evidence"))
            evidence_hit = _evidence_hit(record.expected_evidence or [], evidence)
            if actual and record.expected_result:
                outcome = "tp"
            elif actual and not record.expected_result:
                outcome = "fp"
            elif not actual and record.expected_result:
                outcome = "fn"
            else:
                outcome = "tn"

        policy_totals[record.policy_id]["total"] += 1
        policy_totals[record.policy_id][outcome] += 1
        policy_totals[record.policy_id]["evidence_hit"] += 1 if evidence_hit else 0

        details.append(EvalDetail(
            record_id=record.record_id,
            filename=record.filename,
            policy_id=record.policy_id,
            policy_text=record.policy_text,
            expected_result=record.expected_result,
            actual_result=actual,
            outcome=outcome,
            company_group_key=record.company_group_key,
            evidence=evidence,
            evidence_hit=evidence_hit,
            notes=record.notes,
        ))

    totals = defaultdict(int)
    for detail in details:
      totals[detail.outcome] += 1
      totals["total"] += 1
      totals["evidence_hit"] += 1 if detail.evidence_hit else 0

    def _ratio(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round(numerator / denominator, 4)

    policies = {}
    for policy_id, bucket in sorted(policy_totals.items()):
        tp = int(bucket.get("tp", 0))
        fp = int(bucket.get("fp", 0))
        fn = int(bucket.get("fn", 0))
        missing = int(bucket.get("missing", 0))
        total = int(bucket.get("total", 0))
        policies[policy_id] = {
            "total": total,
            "tp": tp,
            "fp": fp,
            "tn": int(bucket.get("tn", 0)),
            "fn": fn,
            "missing": missing,
            "precision": _ratio(tp, tp + fp),
            "recall": _ratio(tp, tp + fn + missing),
            "evidence_hit_rate": _ratio(int(bucket.get("evidence_hit", 0)), total),
        }

    report = {
        "summary": {
            "total": int(totals["total"]),
            "tp": int(totals["tp"]),
            "fp": int(totals["fp"]),
            "tn": int(totals["tn"]),
            "fn": int(totals["fn"]),
            "missing": int(totals["missing"]),
            "precision": _ratio(int(totals["tp"]), int(totals["tp"]) + int(totals["fp"])),
            "recall": _ratio(
                int(totals["tp"]),
                int(totals["tp"]) + int(totals["fn"]) + int(totals["missing"]),
            ),
            "evidence_hit_rate": _ratio(int(totals["evidence_hit"]), int(totals["total"])),
        },
        "policies": policies,
        "errors": {
            "false_positives": [asdict(item) for item in details if item.outcome == "fp"],
            "false_negatives": [asdict(item) for item in details if item.outcome == "fn"],
            "missing": [asdict(item) for item in details if item.outcome == "missing"],
        },
        "details": [asdict(item) for item in details],
    }
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate condition_check JSON artifacts against a goldset manifest.")
    parser.add_argument("--manifest", required=True, help="Path to goldset JSONL manifest.")
    parser.add_argument("--results", required=True, help="Path to condition_check_results.json.")
    parser.add_argument("--out", default="", help="Optional output path for the evaluation report.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    results_path = Path(args.results).resolve()
    output_path = Path(args.out).resolve() if args.out else results_path.with_name(f"{results_path.stem}.eval.json")

    goldset = load_goldset_manifest(manifest_path)
    result_payload = json.loads(results_path.read_text(encoding="utf-8"))
    report = evaluate_goldset(goldset, result_payload)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "manifest": str(manifest_path),
        "results": str(results_path),
        "out": str(output_path),
        "summary": report["summary"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
