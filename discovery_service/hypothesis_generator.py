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
    ) -> Dict[str, Any]:
        if not interest_areas:
            return {
                "success": False,
                "error": "관심 분야가 없습니다",
                "hypotheses": [],
            }

        if not self.client:
            return self._generate_local(interest_areas, hypothesis_count)

        prompt = self._build_prompt(interest_areas, policy_analysis, iris_mapping, hypothesis_count)
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

        fallback = self._generate_local(interest_areas, hypothesis_count)
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
    ) -> str:
        policy = policy_analysis or {}
        iris = iris_mapping or {}
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

## 요청
- 가설 {hypothesis_count}개
- 각 가설은 검증 가능한 형태로 작성
- 필요한 근거/데이터, 관찰 신호, 리스크 포함
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

    def _generate_local(self, interest_areas: List[str], hypothesis_count: int) -> Dict[str, Any]:
        hypotheses = []
        for area in interest_areas[:hypothesis_count]:
            hypotheses.append({
                "hypothesis": f"{area} 분야에서 정책 지원과 수요가 동시 확대될 가능성이 높다.",
                "rationale": "관심 분야 입력에 기반한 초기 가설",
                "evidence_needed": ["최근 3년 정책 예산", "시장 성장률", "관련 기업 투자 추이"],
                "signals": ["정부 로드맵 발표", "민간 투자 증가", "규제 완화"],
                "risks": ["정책 우선순위 변경", "시장 과열", "공급 과잉"],
                "logic_steps": [
                    {
                        "premise": f"{area} 관련 정책 지원 가능성",
                        "inference": "공공 자금/제도 지원이 수요를 촉진할 수 있음",
                        "risk": "정책 집행 지연",
                    },
                    {
                        "premise": f"{area} 시장 수요 증가 가정",
                        "inference": "민간 투자/매출 성장 가능",
                        "risk": "수요 증가가 단기 반짝일 수 있음",
                    },
                ],
                "confidence": 0.35,
            })
        return {
            "success": True,
            "hypotheses": hypotheses,
            "assumptions": ["입력 관심 분야가 실제 정책과 맞닿아 있음"],
            "unknowns": ["정책 예산 규모", "시장 수요 탄력성"],
            "summary": "거친 입력을 바탕으로 임시 가설을 구성했습니다.",
            "fallback_used": True,
        }
