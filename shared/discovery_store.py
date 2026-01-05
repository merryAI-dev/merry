"""
Discovery session store for checkpoints, notebooks, and session search.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _sanitize_session_id(session_id: str, max_length: int = 100) -> str:
    if not session_id:
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    sanitized = session_id.replace("/", "_").replace("\\", "_").replace("..", "_")
    sanitized = re.sub(r"[^\w가-힣\-]", "_", sanitized, flags=re.UNICODE)
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    return sanitized or datetime.now().strftime("%Y%m%d_%H%M%S")


class DiscoveryRecordStore:
    """Session storage for discovery analyses."""

    def __init__(self, user_id: str):
        self.user_id = user_id or "anonymous"
        self.base_dir = PROJECT_ROOT / "temp" / "discovery_records" / self.user_id
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.base_dir / "index.json"

    def create_session_id(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _load_index(self) -> List[Dict[str, Any]]:
        if not self.index_path.exists():
            return []
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception:
            return []
        return []

    def _save_index(self, items: List[Dict[str, Any]]) -> None:
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

    def save_checkpoint(self, session_id: str, payload: Dict[str, Any]) -> str:
        safe_id = _sanitize_session_id(session_id)
        checkpoint_path = self.base_dir / f"checkpoint_{safe_id}.json"
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return str(checkpoint_path)

    def load_checkpoint(self, session_id: str) -> Optional[Dict[str, Any]]:
        safe_id = _sanitize_session_id(session_id)
        checkpoint_path = self.base_dir / f"checkpoint_{safe_id}.json"
        if not checkpoint_path.exists():
            return None
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        checkpoints = sorted(
            self.base_dir.glob("checkpoint_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not checkpoints:
            return None
        with open(checkpoints[0], "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data["checkpoint_path"] = str(checkpoints[0])
        return data

    def save_session(self, session_id: str, payload: Dict[str, Any], write_report: bool = True) -> Dict[str, str]:
        safe_id = _sanitize_session_id(session_id)
        session_path = self.base_dir / f"session_{safe_id}.json"
        stored_payload = dict(payload)
        stored_payload.setdefault("created_at", datetime.now().isoformat())
        stored_payload["session_id"] = safe_id

        report_path = None
        if write_report:
            report_path = self._write_report(safe_id, stored_payload)
        stored_payload["report_path"] = report_path

        with open(session_path, "w", encoding="utf-8") as f:
            json.dump(stored_payload, f, ensure_ascii=False, indent=2)

        self._update_index(safe_id, stored_payload, report_path)

        return {
            "session_path": str(session_path),
            "report_path": report_path,
            "session_id": safe_id,
        }

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        safe_id = _sanitize_session_id(session_id)
        session_path = self.base_dir / f"session_{safe_id}.json"
        if not session_path.exists():
            return None
        with open(session_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        items = self._load_index()
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return items[:limit]

    def search_sessions(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        if not query:
            return self.list_sessions(limit)
        query_lower = query.lower()
        results = []
        for item in self._load_index():
            haystack = " ".join([
                item.get("summary", ""),
                " ".join(item.get("policy_themes", []) or []),
                " ".join(item.get("target_industries", []) or []),
                " ".join(item.get("interest_areas", []) or []),
            ]).lower()
            if query_lower in haystack:
                results.append(item)
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results[:limit]

    def _update_index(self, session_id: str, payload: Dict[str, Any], report_path: Optional[str]) -> None:
        index = self._load_index()
        created_at = payload.get("created_at") or datetime.now().isoformat()
        policy = payload.get("policy_analysis") or {}
        recommendations = payload.get("recommendations") or {}
        verification = payload.get("verification") or {}

        summary = (
            verification.get("verification_summary")
            or recommendations.get("summary")
            or policy.get("summary")
            or ""
        )

        entry = {
            "session_id": session_id,
            "created_at": created_at,
            "policy_themes": policy.get("policy_themes", []) or [],
            "target_industries": policy.get("target_industries", []) or [],
            "interest_areas": payload.get("interest_areas", []) or [],
            "trust_score": verification.get("trust_score"),
            "summary": summary,
            "report_path": report_path,
        }

        index = [item for item in index if item.get("session_id") != session_id]
        index.append(entry)
        self._save_index(index)

    def _write_report(self, session_id: str, payload: Dict[str, Any]) -> str:
        report_path = self.base_dir / f"report_{session_id}.md"
        lines = []

        created_at = payload.get("created_at") or datetime.now().isoformat()
        verification = payload.get("verification") or {}
        trust_score = verification.get("trust_score", "N/A")
        trust_level = verification.get("trust_level", "N/A")

        lines.append("---")
        lines.append(f"session_id: {session_id}")
        lines.append(f"created_at: {created_at}")
        lines.append(f"user_id: {self.user_id}")
        lines.append(f"trust_score: {trust_score}")
        lines.append(f"trust_level: {trust_level}")
        lines.append("---")
        lines.append("")
        lines.append("# 스타트업 발굴 노트북")
        lines.append("")
        lines.append("## 입력 요약")
        lines.append(f"- 관심 분야: {', '.join(payload.get('interest_areas', []) or [])}")

        policy = payload.get("policy_analysis") or {}
        if policy:
            lines.append(f"- 정책 테마: {', '.join(policy.get('policy_themes', []) or [])}")
            lines.append(f"- 타겟 산업: {', '.join(policy.get('target_industries', []) or [])}")

        hypotheses = payload.get("hypotheses") or {}
        if hypotheses:
            lines.append("")
            lines.append("## 리서치 메리 가설")
            for item in hypotheses.get("hypotheses", []) or []:
                lines.append(f"- {item.get('hypothesis', '')}")

        recommendations = payload.get("recommendations") or {}
        if recommendations.get("recommendations"):
            lines.append("")
            lines.append("## 추천 결과")
            for rec in recommendations.get("recommendations", []):
                lines.append(f"- **{rec.get('industry', 'N/A')}** (총점 {rec.get('total_score', 0):.2f})")
                rationale = rec.get("rationale")
                if rationale:
                    lines.append(f"  - 근거: {rationale}")
                sources = rec.get("sources") or []
                if sources:
                    lines.append(f"  - 출처: {', '.join(sources)}")

        if verification:
            lines.append("")
            lines.append("## 슈퍼메리 검증")
            summary = verification.get("super_mary", {}).get("summary")
            if summary:
                lines.append(f"- 요약: {summary}")
            for step in verification.get("super_mary", {}).get("reasoning_steps", []) or []:
                lines.append(
                    f"- [{step.get('status', 'warn')}] {step.get('step', '')}: {step.get('note', '')}"
                )
            for item in verification.get("super_mary", {}).get("sub_mary_review", []) or []:
                lines.append(
                    f"- [{item.get('assessment', 'partial')}] {item.get('sub_claim', '')} · "
                    f"근거: {item.get('reason', '')} · 보완: {item.get('correction', '')}"
                )
            challenges = verification.get("super_mary", {}).get("challenges", []) or []
            for ch in challenges:
                lines.append(f"- [{ch.get('severity', 'low')}] {ch.get('challenge', '')}")

            sub_mary = verification.get("sub_mary", {})
            if sub_mary:
                lines.append("")
                lines.append("## 서브메리 논리 점검")
                if sub_mary.get("summary"):
                    lines.append(f"- 요약: {sub_mary.get('summary')}")
                for step in sub_mary.get("reasoning_steps", []) or []:
                    lines.append(
                        f"- [{step.get('status', 'warn')}] {step.get('step', '')}: {step.get('note', '')}"
                    )
                for check in sub_mary.get("logic_checks", []) or []:
                    lines.append(
                        f"- [{check.get('status', 'warn')}] {check.get('claim', '')} · "
                        f"전제: {check.get('premise', '')} · 취약점: {check.get('logic_gap', '')}"
                    )

        process_trace = verification.get("process_trace", {})
        if process_trace:
            lines.append("")
            lines.append("## 전체 과정 로그")
            data_summary = process_trace.get("data_summary", {})
            if data_summary:
                lines.append("- 입력/데이터 상태")
                for key, value in data_summary.items():
                    lines.append(f"  - {key}: {value}")
            trust_breakdown = process_trace.get("trust_breakdown", {})
            if trust_breakdown:
                lines.append("- 신뢰점수 계산 내역")
                for key, value in trust_breakdown.items():
                    lines.append(f"  - {key}: {value}")

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return str(report_path)
