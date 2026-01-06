"""
Discovery verification loop with trust score and challenge log.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from anthropic import Anthropic

from shared.discovery_quality import evaluate_recommendations
from agent.teaming.trust_calculator import calculate_trust_score


class DiscoveryVerifier:
    """Generate challenge logs and trust scores for discovery outputs."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-opus-4-5-20251101",
        response_language: str = "Korean",
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=self.api_key) if self.api_key else None
        self.model = model
        self.response_language = response_language

    def verify(
        self,
        policy_analysis: Optional[Dict[str, Any]] = None,
        iris_mapping: Optional[Dict[str, Any]] = None,
        recommendations: Optional[Dict[str, Any]] = None,
        hypotheses: Optional[Dict[str, Any]] = None,
        interest_areas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        policy_analysis = policy_analysis or {}
        iris_mapping = iris_mapping or {}
        recommendations = recommendations or {}
        hypotheses = hypotheses or {}
        interest_areas = interest_areas or []

        quality_gate = evaluate_recommendations(recommendations.get("recommendations", []))
        sub_mary = self._generate_logic_review(
            policy_analysis=policy_analysis,
            iris_mapping=iris_mapping,
            recommendations=recommendations,
            hypotheses=hypotheses,
            interest_areas=interest_areas,
        )
        super_mary = self._generate_challenges(
            policy_analysis=policy_analysis,
            iris_mapping=iris_mapping,
            recommendations=recommendations,
            hypotheses=hypotheses,
            interest_areas=interest_areas,
            sub_mary=sub_mary,
        )

        logic_score = self._calculate_logic_score(sub_mary)
        trust_score = self._calculate_trust_score(
            policy_analysis=policy_analysis,
            recommendations=recommendations,
            quality_gate=quality_gate,
            super_mary=super_mary,
            logic_score=logic_score,
        )
        trust_score, trust_breakdown = trust_score
        trust_level = self._trust_level(trust_score)

        verification_summary = (
            f"신뢰점수 {trust_score:.1f} ({trust_level}) · 논리점수 {logic_score:.1f}"
        )
        if quality_gate.get("issues"):
            verification_summary += f" · 품질 이슈 {len(quality_gate['issues'])}건"
        if super_mary.get("challenges"):
            verification_summary += f" · 챌린지 {len(super_mary['challenges'])}건"

        return {
            "trust_score": trust_score,
            "trust_level": trust_level,
            "logic_score": logic_score,
            "trust_breakdown": trust_breakdown,
            "process_trace": self._build_process_trace(
                policy_analysis=policy_analysis,
                iris_mapping=iris_mapping,
                recommendations=recommendations,
                hypotheses=hypotheses,
                quality_gate=quality_gate,
                sub_mary=sub_mary,
                super_mary=super_mary,
                trust_breakdown=trust_breakdown,
            ),
            "quality_gate": quality_gate,
            "super_mary": super_mary,
            "sub_mary": sub_mary,
            "research_mary": {
                "summary": hypotheses.get("summary") or "리서치 메리 요약이 없습니다.",
                "hypotheses": hypotheses.get("hypotheses", []),
            },
            "loop_steps": [
                "리서치 메리 가설 생성",
                "근거/IRIS 매핑",
                "서브메리 논리 점검",
                "슈퍼메리 검증",
            ],
            "verification_summary": verification_summary,
        }

    def _generate_challenges(
        self,
        policy_analysis: Dict[str, Any],
        iris_mapping: Dict[str, Any],
        recommendations: Dict[str, Any],
        hypotheses: Dict[str, Any],
        interest_areas: List[str],
        sub_mary: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not self.client:
            return self._fallback_challenges(recommendations, sub_mary)

        prompt = self._build_prompt(
            policy_analysis=policy_analysis,
            iris_mapping=iris_mapping,
            recommendations=recommendations,
            hypotheses=hypotheses,
            interest_areas=interest_areas,
            sub_mary=sub_mary,
        )
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            result_text = response.content[0].text
            json_match = re.search(r"```json\s*(.*?)\s*```", result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group(1)
            result = json.loads(result_text)
            result.setdefault("summary", "")
            result.setdefault("challenges", [])
            result.setdefault("reasoning_steps", [])
            result.setdefault("sub_mary_review", [])
            result["role"] = "슈퍼메리"
            return result
        except Exception:
            return self._fallback_challenges(recommendations, sub_mary)

    def _generate_logic_review(
        self,
        policy_analysis: Dict[str, Any],
        iris_mapping: Dict[str, Any],
        recommendations: Dict[str, Any],
        hypotheses: Dict[str, Any],
        interest_areas: List[str],
    ) -> Dict[str, Any]:
        if not self.client:
            return self._fallback_logic_review(recommendations, hypotheses)

        prompt = self._build_logic_prompt(
            policy_analysis=policy_analysis,
            iris_mapping=iris_mapping,
            recommendations=recommendations,
            hypotheses=hypotheses,
            interest_areas=interest_areas,
        )
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            result_text = response.content[0].text
            json_match = re.search(r"```json\s*(.*?)\s*```", result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group(1)
            result = json.loads(result_text)
            result.setdefault("summary", "")
            result.setdefault("logic_checks", [])
            result.setdefault("reasoning_steps", [])
            result["role"] = "서브메리"
            return result
        except Exception:
            return self._fallback_logic_review(recommendations, hypotheses)

    def _build_logic_prompt(
        self,
        policy_analysis: Dict[str, Any],
        iris_mapping: Dict[str, Any],
        recommendations: Dict[str, Any],
        hypotheses: Dict[str, Any],
        interest_areas: List[str],
    ) -> str:
        return f"""당신은 서브메리입니다. 주장/가설의 논리적 정합성만 평가하세요.
사실 여부보다 추론 구조가 타당한지에 집중합니다. 체인오브쏘트는 노출하지 마세요.
한국어로 JSON만 출력하세요.

## 관심 분야
{interest_areas}

## 정책 요약
- 정책 테마: {policy_analysis.get('policy_themes', [])}
- 타겟 산업: {policy_analysis.get('target_industries', [])}

## 가설
{json.dumps(hypotheses.get('hypotheses', []), ensure_ascii=False)}

## 추천
{json.dumps(recommendations.get('recommendations', [])[:5], ensure_ascii=False)}

## 출력(JSON)
```json
{{
  "summary": "서브메리 논리 점검 요약",
  "logic_checks": [
    {{
      "claim": "검토 대상 주장",
      "premise": "핵심 전제",
      "logic_gap": "논리적 취약점/누락",
      "status": "pass|warn|fail",
      "fix": "논리 보완 방향"
    }}
  ],
  "reasoning_steps": [
    {{
      "step": "논리 점검 단계 요약",
      "note": "간단한 논리 검증 포인트",
      "status": "pass|warn|fail"
    }}
  ]
}}
```
"""

    def _fallback_logic_review(
        self,
        recommendations: Dict[str, Any],
        hypotheses: Dict[str, Any],
    ) -> Dict[str, Any]:
        checks = []
        for hypo in (hypotheses.get("hypotheses") or [])[:2]:
            checks.append({
                "claim": hypo.get("hypothesis", "가설"),
                "premise": "정책 지원 + 수요 증가 가정",
                "logic_gap": "전제의 독립 검증이 없음",
                "status": "warn",
                "fix": "정책 예산과 수요 지표의 선행성 확인",
            })
        for rec in (recommendations.get("recommendations") or [])[:2]:
            checks.append({
                "claim": f"{rec.get('industry', '산업')} 추천",
                "premise": "정책 테마와 산업이 직접 연결됨",
                "logic_gap": "연결 고리가 구체적이지 않음",
                "status": "warn",
                "fix": "정책 문구-산업 매핑 근거 보강",
            })
        return {
            "summary": "서브메리(폴백) 논리 점검: 전제-결론 연결 강화 필요",
            "logic_checks": checks,
            "reasoning_steps": [
                {
                    "step": "전제-결론 연결 점검",
                    "note": "정책 지원/수요 가정의 독립 검증 필요",
                    "status": "warn",
                }
            ],
            "role": "서브메리",
            "fallback_used": True,
        }

    def _build_prompt(
        self,
        policy_analysis: Dict[str, Any],
        iris_mapping: Dict[str, Any],
        recommendations: Dict[str, Any],
        hypotheses: Dict[str, Any],
        interest_areas: List[str],
        sub_mary: Dict[str, Any],
    ) -> str:
        return f"""당신은 슈퍼메리입니다. 리서치 메리의 가설과 추천을 적대적으로 검증하세요.
한국어로 JSON만 출력하세요. 체인오브쏘트는 노출하지 마세요.

## 관심 분야
{interest_areas}

## 정책 요약
- 정책 테마: {policy_analysis.get('policy_themes', [])}
- 타겟 산업: {policy_analysis.get('target_industries', [])}
- 예산 정보: {policy_analysis.get('budget_info', {})}

## IRIS+ 요약
- SDG: {iris_mapping.get('aggregate_sdgs', [])}
- 메트릭: {iris_mapping.get('aggregate_metrics', [])[:10]}

## 가설
{json.dumps(hypotheses.get('hypotheses', []), ensure_ascii=False)}

## 추천
{json.dumps(recommendations.get('recommendations', [])[:5], ensure_ascii=False)}

## 서브메리 논리 점검 결과
요약: {sub_mary.get('summary')}
논리 체크: {json.dumps(sub_mary.get('logic_checks', []), ensure_ascii=False)}
논리 단계: {json.dumps(sub_mary.get('reasoning_steps', []), ensure_ascii=False)}

## 출력(JSON)
```json
{{
  "summary": "슈퍼메리 검증 요약",
  "challenges": [
    {{
      "claim": "검증 대상 주장",
      "challenge": "왜 문제가 되는지",
      "severity": "low|medium|high",
      "needed_evidence": "필요 근거",
      "impact": "의사결정 영향"
    }}
  ],
  "reasoning_steps": [
    {{
      "step": "검증 단계 요약",
      "note": "간단한 검증 포인트",
      "status": "pass|warn|fail"
    }}
  ],
  "sub_mary_review": [
    {{
      "sub_claim": "서브메리 판단 요약",
      "assessment": "agree|partial|disagree",
      "reason": "판단 근거",
      "correction": "필요한 보완/수정"
    }}
  ]
}}
```
"""

    def _fallback_challenges(self, recommendations: Dict[str, Any], sub_mary: Dict[str, Any]) -> Dict[str, Any]:
        challenges = []
        for rec in (recommendations.get("recommendations") or [])[:3]:
            industry = rec.get("industry", "N/A")
            challenges.append({
                "claim": f"{industry} 산업 추천",
                "challenge": "정책 근거의 직접성/효과 크기가 명확하지 않습니다.",
                "severity": "medium",
                "needed_evidence": "정책 예산 배분 근거 또는 시장 성장률",
                "impact": "투자 우선순위 재조정 필요",
            })
        review_items = []
        for check in (sub_mary.get("logic_checks") or [])[:3]:
            review_items.append({
                "sub_claim": check.get("claim", "서브메리 판단"),
                "assessment": "partial",
                "reason": "추가 근거가 필요하거나 과도한 일반화 가능성",
                "correction": "정책 문구/예산과의 직접 연결 검증",
            })
        return {
            "summary": "슈퍼메리(폴백) 검증: 추가 근거가 필요합니다.",
            "challenges": challenges,
            "reasoning_steps": [
                {
                    "step": "근거 직접성 확인",
                    "note": "정책 문구와 산업 연결 고리가 부족",
                    "status": "warn",
                },
                {
                    "step": "효과 크기 점검",
                    "note": "정량 근거가 부족",
                    "status": "fail",
                },
            ],
            "sub_mary_review": review_items,
            "role": "슈퍼메리",
            "fallback_used": True,
        }

    def _calculate_trust_score(
        self,
        policy_analysis: Dict[str, Any],
        recommendations: Dict[str, Any],
        quality_gate: Dict[str, Any],
        super_mary: Dict[str, Any],
        logic_score: float,
    ) -> tuple:
        policy_score = calculate_trust_score("analyze_government_policy", policy_analysis) * 100
        rec_score = calculate_trust_score("generate_industry_recommendation", recommendations) * 100

        base_score = (policy_score + rec_score) / 2 if (policy_score and rec_score) else max(policy_score, rec_score, 40)
        quality_score = quality_gate.get("quality_score", 60)

        weighted_score = base_score * 0.3 + quality_score * 0.3 + logic_score * 0.4

        source_reliability = policy_analysis.get("source_reliability") or []
        source_adjustment = 0.0
        if source_reliability:
            avg_rel = sum(source_reliability) / len(source_reliability)
            source_adjustment = (avg_rel - 0.6) * 20
            weighted_score += source_adjustment

        fallback_penalty = 0.0
        if policy_analysis.get("fallback_used") or recommendations.get("fallback_used"):
            fallback_penalty -= 8
            weighted_score += fallback_penalty

        severity_penalties = {"high": 10, "medium": 5, "low": 2}
        challenge_penalty = 0.0
        severity_counts = {"high": 0, "medium": 0, "low": 0}
        for item in super_mary.get("challenges", []):
            severity = str(item.get("severity", "low")).lower()
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            challenge_penalty -= severity_penalties.get(severity, 2)
        weighted_score += challenge_penalty

        final_score = max(min(weighted_score, 100), 0)
        breakdown = {
            "base_score": round(base_score, 2),
            "quality_score": round(quality_score, 2),
            "logic_score": round(logic_score, 2),
            "weights": {"base": 0.3, "quality": 0.3, "logic": 0.4},
            "source_adjustment": round(source_adjustment, 2),
            "fallback_penalty": round(fallback_penalty, 2),
            "challenge_penalty": round(challenge_penalty, 2),
            "severity_counts": severity_counts,
            "weighted_score": round(weighted_score, 2),
            "final_score": round(final_score, 2),
        }
        return final_score, breakdown

    def _calculate_logic_score(self, sub_mary: Dict[str, Any]) -> float:
        checks = sub_mary.get("logic_checks", []) or []
        if not checks:
            return 60.0
        weights = {"pass": 1.0, "warn": 0.6, "fail": 0.2}
        total = 0.0
        for check in checks:
            status = str(check.get("status", "warn")).lower()
            total += weights.get(status, 0.6)
        avg = total / len(checks)
        return max(min(avg * 100, 100), 0)

    def _build_process_trace(
        self,
        policy_analysis: Dict[str, Any],
        iris_mapping: Dict[str, Any],
        recommendations: Dict[str, Any],
        hypotheses: Dict[str, Any],
        quality_gate: Dict[str, Any],
        sub_mary: Dict[str, Any],
        super_mary: Dict[str, Any],
        trust_breakdown: Dict[str, Any],
    ) -> Dict[str, Any]:
        recs = recommendations.get("recommendations", []) or []
        rec_count = len(recs)
        missing_sources = 0
        assumption_count = 0
        finding_count = 0

        for rec in recs:
            sources = rec.get("sources", []) or []
            if not sources or all("미제공" in str(s) for s in sources):
                missing_sources += 1
            markers = rec.get("evidence_markers", []) or []
            if markers:
                for marker in markers:
                    label = str(marker.get("marker", "")).upper()
                    if "ASSUMPTION" in label or "UNCERTAINTY" in label:
                        assumption_count += 1
                    if "FINDING" in label:
                        finding_count += 1
            else:
                evidence = rec.get("evidence", []) or []
                for ev in evidence:
                    text = str(ev)
                    if "[ASSUMPTION]" in text or "[UNCERTAINTY]" in text:
                        assumption_count += 1
                    if "[FINDING]" in text:
                        finding_count += 1

        total_markers = assumption_count + finding_count
        assumption_ratio = round(assumption_count / total_markers, 2) if total_markers else 1.0

        weighting = recommendations.get("weighting", {}) or {}
        data_summary = {
            "policy_has_budget": bool(policy_analysis.get("budget_info")),
            "policy_has_key_policies": bool(policy_analysis.get("key_policies")),
            "policy_sources_count": len(policy_analysis.get("sources", []) or []),
            "sdg_count": len(iris_mapping.get("aggregate_sdgs", []) or []),
            "metric_count": len(iris_mapping.get("aggregate_metrics", []) or []),
            "recommendation_count": rec_count,
            "recommendations_missing_sources": missing_sources,
            "assumption_ratio": assumption_ratio,
            "quality_issues": len(quality_gate.get("issues", []) or []),
        }
        if weighting:
            data_summary.update({
                "document_weight": weighting.get("document_weight"),
                "interest_weight": weighting.get("interest_weight"),
            })

        return {
            "data_summary": data_summary,
            "fallback_flags": {
                "policy_fallback": bool(policy_analysis.get("fallback_used")),
                "recommendation_fallback": bool(recommendations.get("fallback_used")),
                "hypothesis_fallback": bool(hypotheses.get("fallback_used")),
            },
            "trust_breakdown": trust_breakdown,
            "sub_mary": {
                "reasoning_steps": sub_mary.get("reasoning_steps", []),
                "logic_checks": sub_mary.get("logic_checks", []),
            },
            "super_mary": {
                "reasoning_steps": super_mary.get("reasoning_steps", []),
                "challenges": super_mary.get("challenges", []),
                "sub_mary_review": super_mary.get("sub_mary_review", []),
            },
        }

    @staticmethod
    def _trust_level(score: float) -> str:
        if score >= 85:
            return "A"
        if score >= 70:
            return "B"
        if score >= 55:
            return "C"
        return "D"
