"""
Hypothesis Generator for coarse industry inputs.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from anthropic import Anthropic
from dotenv import load_dotenv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

MAX_RETRIES = 2


class HypothesisGenerator:
    """Generate industry hypotheses from coarse inputs."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=self.api_key) if self.api_key else None

    def generate(
        self,
        interest_areas: List[str],
        policy_analysis: Optional[Dict[str, Any]] = None,
        iris_mapping: Optional[Dict[str, Any]] = None,
        hypothesis_count: int = 4,
        fusion_proposals: Optional[List[Dict[str, Any]]] = None,
        fusion_feedback: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not interest_areas:
            return {
                "success": False,
                "error": "관심 분야가 없습니다",
                "hypotheses": [],
            }

        if not self.client:
            return self._generate_local(
                interest_areas,
                hypothesis_count,
                policy_analysis,
                iris_mapping,
                fusion_proposals,
                fusion_feedback,
            )

        prompt = self._build_prompt(
            interest_areas,
            policy_analysis,
            iris_mapping,
            hypothesis_count,
            fusion_proposals,
            fusion_feedback,
        )
        last_error = None
        result_text = ""
        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.messages.create(
                    model="claude-opus-4-5-20251101",
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}],
                )
                result_text = response.content[0].text if response.content else ""
                parsed = self._try_parse_json(result_text)
                if isinstance(parsed, dict):
                    parsed["success"] = True
                    if attempt > 0:
                        parsed["repair_used"] = True
                    return parsed
                last_error = "JSON 파싱 오류"
                prompt = self._build_repair_prompt(result_text)
            except Exception as e:
                last_error = f"Claude 가설 실패: {str(e)}"
                break

        fallback = self._generate_local(
            interest_areas,
            hypothesis_count,
            policy_analysis,
            iris_mapping,
            fusion_proposals,
            fusion_feedback,
        )
        if last_error:
            fallback["warnings"] = [last_error]
        fallback["fallback_used"] = True
        return fallback

    def _build_prompt(
        self,
        interest_areas: List[str],
        policy_analysis: Optional[Dict[str, Any]],
        iris_mapping: Optional[Dict[str, Any]],
        hypothesis_count: int,
        fusion_proposals: Optional[List[Dict[str, Any]]] = None,
        fusion_feedback: Optional[Dict[str, Any]] = None,
    ) -> str:
        policy = policy_analysis or {}
        iris = iris_mapping or {}
        fusion_section = ""
        if fusion_proposals:
            fusion_payload = {
                "proposals": fusion_proposals[:6],
                "feedback": fusion_feedback or {},
            }
            fusion_section = f"\n\n## 사전 융합안/평가\n{json.dumps(fusion_payload, ensure_ascii=False)}"
        return f"""당신은 리서치 메리입니다. 사용자의 거친 관심 분야를 바탕으로 검증 가능한 가설을 세우세요.
내부 추론은 사용하되 체인오브쏘트는 노출하지 마세요.

## 관심 분야
{interest_areas}

## 정책 테마
{policy.get('policy_themes', [])}

## 타겟 산업
{policy.get('target_industries', [])}

## IRIS+ SDG
{iris.get('aggregate_sdgs', [])}
{fusion_section}

## 요청
- 가설 {hypothesis_count}개
- 각 가설은 검증 가능한 형태로 작성
- 필요한 근거/데이터, 관찰 신호, 리스크 포함
- 정책 문서에 직접 근거가 없으면 '융합 가설'로 표시하고 근거 부족을 명시
- confidence는 근거 수준에 따라 0~1로 조정 (직접 근거 부족 시 0.3 이하)
- 사전 융합안 평가가 있다면 "좋음"은 우선 반영, "보통"은 보조, "아님"은 제외
- 한국어로 JSON만 출력

## 출력(JSON)
```json
{{
  "hypotheses": [
    {{
      "hypothesis": "...",
      "rationale": "...",
      "evidence_needed": ["..."],
      "signals": ["..."],
      "risks": ["..."],
      "logic_steps": [
        {{
          "premise": "...",
          "inference": "...",
          "risk": "..."
        }}
      ],
      "confidence": 0.0
    }}
  ],
  "assumptions": ["..."],
  "unknowns": ["..."],
  "summary": "가설 요약"
}}
```
"""

    @staticmethod
    def _try_parse_json(text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if json_match:
            candidate = json_match.group(1)
        else:
            start = text.find("{")
            end = text.rfind("}")
            candidate = text[start:end + 1] if start != -1 and end != -1 and end > start else text
        candidate = candidate.strip()
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _build_repair_prompt(raw_text: str) -> str:
        snippet = (raw_text or "")[:4000]
        return f"""다음 출력에서 유효한 JSON만 추출/수정해 반환하세요.
체인오브쏘트는 노출하지 마세요.

원본 출력:
```text
{snippet}
```

JSON만 출력하세요.
"""

    def _generate_local(
        self,
        interest_areas: List[str],
        hypothesis_count: int,
        policy_analysis: Optional[Dict[str, Any]] = None,
        iris_mapping: Optional[Dict[str, Any]] = None,
        fusion_proposals: Optional[List[Dict[str, Any]]] = None,
        fusion_feedback: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        policy = policy_analysis or {}
        iris = iris_mapping or {}
        policy_themes = [str(item).strip() for item in policy.get("policy_themes", []) if str(item).strip()]
        target_industries = [str(item).strip() for item in policy.get("target_industries", []) if str(item).strip()]
        budget_keys = list((policy.get("budget_info") or {}).keys())
        key_policies = policy.get("key_policies") or []
        policy_names = [p.get("name") for p in key_policies if isinstance(p, dict) and p.get("name")]
        sdgs = iris.get("aggregate_sdgs", []) or []

        hypotheses = []
        feedback = fusion_feedback or {}
        accepted = self._select_fusion_proposals(fusion_proposals, feedback, rating="좋음")
        neutral = self._select_fusion_proposals(fusion_proposals, feedback, rating="보통")

        for proposal in accepted[:hypothesis_count]:
            hypotheses.append(self._build_fusion_hypothesis(proposal, priority_note="사용자 평가(좋음)"))

        remaining_slots = max(hypothesis_count - len(hypotheses), 0)
        for proposal in neutral[:remaining_slots]:
            hypotheses.append(self._build_fusion_hypothesis(proposal, priority_note="사용자 평가(보통)"))

        remaining_slots = max(hypothesis_count - len(hypotheses), 0)
        for area in interest_areas[:remaining_slots]:
            area_lower = area.lower()
            matched_themes = [
                theme for theme in policy_themes
                if area_lower in theme.lower() or theme.lower() in area_lower
            ]
            matched_industries = [
                industry for industry in target_industries
                if area_lower in industry.lower() or industry.lower() in area_lower
            ]
            direct_match = bool(matched_themes or matched_industries)
            anchor_theme = matched_themes[0] if matched_themes else (policy_themes[0] if policy_themes else None)
            anchor_industry = matched_industries[0] if matched_industries else (
                target_industries[0] if target_industries else None
            )

            if direct_match:
                hypothesis = (
                    f"{area} 분야는 {anchor_theme or anchor_industry or '정책 기조'}와 맞물려 "
                    "정책 지원과 수요가 동시 확대될 가능성이 있다."
                )
                rationale = "정책 테마/타겟 산업에서 관심 분야와의 직접 연관이 확인됨"
                confidence = 0.45
            else:
                fusion_basis = anchor_theme or "주요 정책 기조"
                hypothesis = (
                    f"현재 정책 문서에서 {area} 직접 언급은 제한적이지만, "
                    f"{fusion_basis}와의 융합을 통해 {area} 수요가 확대될 가능성이 있다."
                )
                rationale = "관심 분야 기반 융합 가설이며 정책 직접 근거는 부족함"
                confidence = 0.25

            evidence_needed = [
                "최근 3년 정책 예산/집행 현황",
                "시장 성장률 및 수요 지표",
                "관련 기업 투자/매출 추이",
            ]
            if budget_keys:
                evidence_needed.insert(0, f"{', '.join(budget_keys[:2])} 예산 배분 근거")
            if policy_names:
                evidence_needed.append(f"{', '.join(policy_names[:2])} 실행 계획/성과 지표")
            if sdgs:
                evidence_needed.append(f"연계 SDG({', '.join(map(str, sdgs[:3]))}) 관련 지표")

            signals = [
                "정부 로드맵 발표",
                "민간 투자 증가",
                "규제 완화",
            ]
            if direct_match:
                signals.append("관련 부처 예산 공고/사업 공모")
            else:
                signals.append("정책 문서에서 관련 언급 증가")

            risks = [
                "정책 우선순위 변경",
                "시장 과열",
                "공급 과잉",
            ]
            if not direct_match:
                risks.append("정책 지원 부재 또는 정합성 부족")

            logic_steps = []
            if direct_match:
                logic_steps.append({
                    "premise": f"{area} 관련 정책 테마/산업이 문서에 명시됨",
                    "inference": "공공 자금/제도 지원이 수요를 촉진할 수 있음",
                    "risk": "예산 집행 지연 또는 범위 축소",
                })
            else:
                logic_steps.append({
                    "premise": f"{area} 직접 정책 근거 부족, {fusion_basis}와의 융합 필요",
                    "inference": "융합 시나리오에서 정책/시장 수요가 생길 수 있음",
                    "risk": "정책 범위 확장이 이루어지지 않을 수 있음",
                })
            logic_steps.append({
                "premise": f"{area} 시장 수요 증가 가정",
                "inference": "민간 투자/매출 성장 가능",
                "risk": "수요 증가가 단기 반짝일 수 있음",
            })

            if budget_keys:
                confidence = min(confidence + 0.05, 0.6)

            hypotheses.append({
                "hypothesis": hypothesis,
                "rationale": rationale,
                "evidence_needed": evidence_needed,
                "signals": signals,
                "risks": risks,
                "logic_steps": logic_steps,
                "confidence": round(confidence, 2),
            })

        assumptions = ["입력 관심 분야가 정책 또는 정책 기조와 맞닿아 있을 수 있음"]
        if accepted:
            assumptions.append("사용자 평가(좋음) 융합안을 우선 반영함")
        if not policy_themes and not target_industries:
            assumptions.append("정책 문서 근거가 충분하지 않아 관심 분야만 반영됨")

        return {
            "success": True,
            "hypotheses": hypotheses,
            "assumptions": assumptions,
            "unknowns": ["정책 예산 규모", "시장 수요 탄력성", "정책 집행 일정"],
            "summary": "정책 테마와 관심 분야의 정합성을 기준으로 임시 가설을 구성했습니다.",
            "fallback_used": True,
        }

    def generate_fusion_proposals(
        self,
        interest_areas: List[str],
        policy_analysis: Optional[Dict[str, Any]] = None,
        iris_mapping: Optional[Dict[str, Any]] = None,
        proposal_count: int = 4,
    ) -> Dict[str, Any]:
        if not interest_areas:
            return {
                "success": False,
                "error": "관심 분야가 없습니다",
                "proposals": [],
            }

        if not self.client:
            return self._generate_local_fusion_proposals(
                interest_areas,
                policy_analysis,
                iris_mapping,
                proposal_count,
            )

        prompt = self._build_fusion_prompt(interest_areas, policy_analysis, iris_mapping, proposal_count)
        last_error = None
        result_text = ""
        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.messages.create(
                    model="claude-opus-4-5-20251101",
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}],
                )
                result_text = response.content[0].text if response.content else ""
                parsed = self._try_parse_json(result_text)
                if isinstance(parsed, dict):
                    parsed["success"] = True
                    if attempt > 0:
                        parsed["repair_used"] = True
                    return parsed
                last_error = "JSON 파싱 오류"
                prompt = self._build_repair_prompt(result_text)
            except Exception as e:
                last_error = f"Claude 융합안 실패: {str(e)}"
                break

        fallback = self._generate_local_fusion_proposals(
            interest_areas,
            policy_analysis,
            iris_mapping,
            proposal_count,
        )
        if last_error:
            fallback["warnings"] = [last_error]
        fallback["fallback_used"] = True
        return fallback

    def _build_fusion_prompt(
        self,
        interest_areas: List[str],
        policy_analysis: Optional[Dict[str, Any]],
        iris_mapping: Optional[Dict[str, Any]],
        proposal_count: int,
    ) -> str:
        policy = policy_analysis or {}
        iris = iris_mapping or {}
        return f"""당신은 리서치 메리입니다. 관심 분야와 정책 키워드를 융합한 사전 제안안을 만드세요.
내부 추론은 사용하되 체인오브쏘트는 노출하지 마세요.

## 관심 분야
{interest_areas}

## 정책 테마
{policy.get('policy_themes', [])}

## 타겟 산업
{policy.get('target_industries', [])}

## IRIS+ SDG
{iris.get('aggregate_sdgs', [])}

## 요청
- 융합 제안 {proposal_count}개
- 각 제안은 관심 분야와 정책/산업 키워드의 결합으로 구성
- 정책 문서에 직접 근거가 없으면 '융합 가설'로 표시하고 근거 부족을 명시
- 각 제안에 검증 질문 2~3개 포함
- 한국어로 JSON만 출력

## 출력(JSON)
```json
{{
  "proposals": [
    {{
      "id": "fusion_1",
      "title": "융합안 제목",
      "fusion_basis": ["정책 테마", "타겟 산업"],
      "concept": "융합 개념 설명",
      "validation_questions": ["검증 질문1", "검증 질문2"],
      "risks": ["리스크1", "리스크2"],
      "confidence": 0.0
    }}
  ],
  "summary": "요약"
}}
```
"""

    def _generate_local_fusion_proposals(
        self,
        interest_areas: List[str],
        policy_analysis: Optional[Dict[str, Any]],
        iris_mapping: Optional[Dict[str, Any]],
        proposal_count: int,
    ) -> Dict[str, Any]:
        policy = policy_analysis or {}
        policy_themes = [str(item).strip() for item in policy.get("policy_themes", []) if str(item).strip()]
        target_industries = [str(item).strip() for item in policy.get("target_industries", []) if str(item).strip()]
        seeds = self._select_fusion_seeds(policy_themes, target_industries)

        proposals = []
        proposal_id = 1
        for area in interest_areas:
            for seed in seeds:
                if len(proposals) >= proposal_count:
                    break
                title = f"{area} + {seed} 융합안"
                concept = (
                    f"{area} 분야에 {seed}를 적용해 데이터 기반 의사결정/자동화를 강화하는 시나리오."
                )
                proposals.append({
                    "id": f"fusion_{proposal_id}",
                    "title": title,
                    "fusion_basis": [seed],
                    "concept": concept,
                    "validation_questions": [
                        f"{area} 고객/현장의 핵심 문제는 무엇인가?",
                        f"{seed} 적용 시 성과 지표는 무엇으로 측정할 것인가?",
                    ],
                    "risks": [
                        "정책 근거 부족",
                        "현장 도입 비용 과다",
                    ],
                    "confidence": 0.25,
                })
                proposal_id += 1
            if len(proposals) >= proposal_count:
                break

        return {
            "success": True,
            "proposals": proposals,
            "summary": "관심 분야 기반 융합안을 임시로 구성했습니다.",
            "fallback_used": True,
        }

    @staticmethod
    def _select_fusion_proposals(
        proposals: Optional[List[Dict[str, Any]]],
        feedback: Dict[str, Any],
        rating: str,
    ) -> List[Dict[str, Any]]:
        if not proposals:
            return []
        selected = []
        for proposal in proposals:
            proposal_id = str(proposal.get("id", "")).strip()
            if not proposal_id:
                continue
            item = feedback.get(proposal_id, {})
            if item.get("rating") == rating:
                selected.append(proposal)
        return selected

    @staticmethod
    def _build_fusion_hypothesis(
        proposal: Dict[str, Any],
        priority_note: str,
    ) -> Dict[str, Any]:
        title = proposal.get("title") or "융합안"
        basis = proposal.get("fusion_basis") or []
        basis_text = ", ".join([str(item) for item in basis if str(item).strip()])
        concept = proposal.get("concept") or ""
        confidence = proposal.get("confidence")
        if isinstance(confidence, (int, float)):
            confidence_value = min(max(float(confidence), 0.1), 0.6)
        else:
            confidence_value = 0.35

        hypothesis = f"{title}은/는 정책/시장 흐름과 맞물리면 수요 확대 가능성이 있다."
        rationale = f"{priority_note}로 사전 반영된 융합안입니다."
        if basis_text:
            rationale += f" 기반 키워드: {basis_text}"
        if concept:
            rationale += f" 개념: {concept}"

        return {
            "hypothesis": hypothesis,
            "rationale": rationale,
            "evidence_needed": [
                "정책 예산/지원 사업 확인",
                "시장 성장률 및 수요 지표",
                "현장 도입 비용/ROI 데이터",
            ],
            "signals": [
                "관련 부처 공모 확대",
                "민간 투자 증가",
                "현장 PoC 성공 사례",
            ],
            "risks": [
                "정책 우선순위 변경",
                "현장 도입 저항",
                "기술 비용 급등",
            ],
            "logic_steps": [
                {
                    "premise": f"{title} 융합안에 대한 초기 수요 가정",
                    "inference": "정책/시장 신호가 맞물리면 확산 가능",
                    "risk": "근거 부족 시 가설 유지 실패",
                }
            ],
            "confidence": round(confidence_value, 2),
        }

    @staticmethod
    def _select_fusion_seeds(policy_themes: List[str], target_industries: List[str]) -> List[str]:
        seeds = []
        for item in policy_themes[:2]:
            if item and item not in seeds:
                seeds.append(item)
        for item in target_industries[:2]:
            if item and item not in seeds:
                seeds.append(item)
        if not seeds:
            seeds = ["디지털전환", "AI", "데이터", "자동화"]
        return seeds[:3]
