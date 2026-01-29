"""
AC Startup Discovery Agent

정부 정책 자료와 IRIS+ 임팩트 기준으로 유망 스타트업 영역을 추천하는 에이전트입니다.
Claude Agent SDK를 사용하여 대화형 추천을 제공합니다.
"""

import json
import asyncio
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncIterator
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트의 .env 파일 로드 (절대 경로 사용)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Claude Agent SDK
try:
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock
    CLAUDE_SDK_AVAILABLE = True
except ImportError:
    CLAUDE_SDK_AVAILABLE = False

# Fallback to Anthropic SDK
from anthropic import Anthropic, AsyncAnthropic

from .tools import execute_tool, register_tools
from .memory import ChatMemory
from .discovery_verifier import DiscoveryVerifier
from discovery_service import HypothesisGenerator
from shared.discovery_store import DiscoveryRecordStore

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent


# 시스템 프롬프트
DISCOVERY_SYSTEM_PROMPT = """당신은 **AC(액셀러레이터) 스타트업 발굴 지원 에이전트**입니다.

## 역할
정부 정책 자료와 IRIS+ 임팩트 기준을 분석하여 유망 스타트업 영역을 추천합니다.

## 현재 컨텍스트
{context}

## 핵심 원칙

### 1. 근거 기반 추천
- 모든 추천은 정책 문서에서 추출한 근거와 함께 제시
- 페이지 번호, 예산 규모, 정책 목표를 명시
- 추측/예시 답변 금지

### 2. IRIS+ 임팩트 연계
- 추천 산업을 IRIS+ 메트릭과 매핑
- SDG(지속가능발전목표) 연계 표시
- 임팩트 측정 가능성 평가

### 3. 대화형 진행
- 사용자의 관심 분야를 파악
- 추가 질문으로 정교화
- 단계별 분석 결과 제공

## 워크플로우

1. **정책 분석 단계**
   - 업로드된 PDF 분석 (analyze_government_policy)
   - 핵심 정책 테마, 예산 배분, 타겟 산업 추출

2. **IRIS+ 매핑 단계**
   - 정책 테마를 IRIS+ 카테고리에 매핑 (map_policy_to_iris)
   - SDG 연계 확인

3. **추천 생성 단계**
    - 정책 + 임팩트 점수 종합 (generate_industry_recommendation)
    - 관심 분야 가중치 적용
    - 상위 5개 산업 추천

4. **투자기업 포트폴리오 조회**
    - query_investment_portfolio 툴을 써서 Airtable/CSV 기반 포트폴리오에서 조건에 맞는 기업을 찾습니다.
    - 지역/카테고리/SDG/투자단계 등을 자연어로 요청하면 요약과 리스트를 제공합니다.

## 사용 가능한 도구

1. **analyze_government_policy**: 정부 정책 PDF 분석
   - pdf_paths: PDF 파일 경로 리스트
   - focus_keywords: 집중 분석 키워드 (선택)

2. **search_iris_plus_metrics**: IRIS+ 메트릭 검색
   - query: 검색 키워드
   - category: 카테고리 필터 (environmental/social/governance)
   - sdg_filter: SDG 번호 필터

3. **map_policy_to_iris**: 정책 → IRIS+ 매핑
   - policy_themes: 정책 테마 리스트
   - target_industries: 타겟 산업 리스트

4. **generate_industry_recommendation**: 산업 추천 생성
    - policy_analysis: 정책 분석 결과
    - iris_mapping: IRIS+ 매핑 결과
    - interest_areas: 사용자 관심 분야

5. **query_investment_portfolio**: 투자기업 포트폴리오 검색
     - query: 검색어 (예: "강원도 소재 기업", "농식품 관련 스타트업")
     - filters: {\"본점 소재지\": \"강원도\", \"카테고리1\": [\"푸드\"]} 형태로 키와 값을 전달
     - limit / sort_by / sort_order로 결과 수/정렬을 제어할 수 있습니다.

## 출력 형식

### 정책 분석 결과
| 정책 테마 | 예산 규모 | 타겟 산업 | 근거 |
|----------|---------|----------|------|
| 탄소중립 | 50조원 | 신재생에너지 | p.15 |

### IRIS+ 매핑 결과
| IRIS+ 코드 | 메트릭명 | 연관 SDG | 정책 연관도 |
|-----------|---------|---------|-----------|
| PI1568 | Clean Energy | SDG 7 | 0.92 |

### 산업 추천 결과
1. **[산업명]** (총점: X.XX)
   - 정책 점수: X.XX
   - 임팩트 점수: X.XX
   - 근거: [정책 문서 인용]
   - IRIS+ 코드: [코드 리스트]

한국어로 전문적이고 정중하게 답변하세요.
"""


class DiscoveryAgent:
    """
    AC 스타트업 발굴 지원 에이전트

    정부 정책 자료와 IRIS+ 임팩트 기준으로 유망 산업을 추천합니다.
    """

    def __init__(
        self,
        api_key: str = None,
        model: str = "claude-opus-4-5-20251101",
        user_id: str = None
    ):
        """
        DiscoveryAgent 초기화

        Args:
            api_key: Anthropic API 키
            model: 사용할 모델
            user_id: 사용자 ID (세션 분리용)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

        self.model = model
        self.user_id = user_id or "anonymous"

        # SDK 클라이언트
        if CLAUDE_SDK_AVAILABLE and self.api_key:
            self.sdk_client = ClaudeSDKClient(
                options=ClaudeAgentOptions(
                    model=model,
                    setting_sources=["project"],
                    allowed_tools=["Read", "Glob", "Grep"],
                    permission_mode="acceptEdits"
                )
            )
        else:
            self.sdk_client = None

        # Anthropic 클라이언트 (폴백)
        if self.api_key:
            self.client = Anthropic(api_key=self.api_key)
            self.async_client = AsyncAnthropic(api_key=self.api_key)
        else:
            self.client = None
            self.async_client = None

        # 도구 등록
        self.tools = self._get_discovery_tools()

        # 분석 컨텍스트
        self.policy_analysis = None
        self.iris_mapping = None
        self.recommendations = None
        self.interest_areas = []
        self.pdf_paths = []
        self.hypotheses = None
        self.verification = None
        self.document_weight = 0.7
        self.fusion_proposals = []
        self.fusion_feedback = {}

        # 대화 히스토리
        self.conversation_history = []

        # 메모리
        self.memory = ChatMemory(user_id=self.user_id)
        self.session_store = DiscoveryRecordStore(self.user_id)

    def _get_discovery_tools(self) -> List[Dict[str, Any]]:
        """발굴 관련 도구만 필터링"""
        all_tools = register_tools()
        discovery_tool_names = [
            "analyze_government_policy",
            "search_iris_plus_metrics",
            "map_policy_to_iris",
            "generate_industry_recommendation",
            "read_pdf_as_text",  # PDF 직접 읽기용
            "query_investment_portfolio",
        ]
        return [t for t in all_tools if t["name"] in discovery_tool_names]

    def _get_context_string(self) -> str:
        """현재 컨텍스트 문자열 생성"""
        context_parts = []

        if self.pdf_paths:
            context_parts.append(f"- 업로드된 PDF: {len(self.pdf_paths)}개")

        if self.interest_areas:
            context_parts.append(f"- 관심 분야: {', '.join(self.interest_areas)}")

        if self.policy_analysis:
            themes = self.policy_analysis.get("policy_themes", [])
            context_parts.append(f"- 분석된 정책 테마: {', '.join(themes[:5])}")

        if self.iris_mapping:
            sdgs = self.iris_mapping.get("aggregate_sdgs", [])
            context_parts.append(f"- 연계 SDG: {sdgs}")

        if self.recommendations:
            rec_count = len(self.recommendations.get("recommendations", []))
            context_parts.append(f"- 생성된 추천: {rec_count}개")

        if self.hypotheses:
            hypo_count = len(self.hypotheses.get("hypotheses", []))
            context_parts.append(f"- 생성된 가설: {hypo_count}개")

        if self.document_weight is not None:
            context_parts.append(f"- 문서 가중치: {self.document_weight:.0%}")

        if self.fusion_proposals:
            accepted_count = self._count_fusion_feedback("좋음")
            context_parts.append(
                f"- 융합안: {len(self.fusion_proposals)}개 (좋음 {accepted_count}개)"
            )

        if self.verification:
            trust_score = self.verification.get("trust_score")
            if trust_score is not None:
                context_parts.append(f"- 신뢰점수: {trust_score:.1f}")
            logic_score = self.verification.get("logic_score")
            if logic_score is not None:
                context_parts.append(f"- 논리점수: {logic_score:.1f}")

        return "\n".join(context_parts) if context_parts else "아직 분석이 시작되지 않았습니다."

    def _count_fusion_feedback(self, rating: str) -> int:
        if not self.fusion_feedback:
            return 0
        count = 0
        for item in self.fusion_feedback.values():
            if isinstance(item, dict) and item.get("rating") == rating:
                count += 1
        return count

    def _build_stub_policy_analysis(self, interest_areas: List[str]) -> Dict[str, Any]:
        themes = list(dict.fromkeys(interest_areas)) if interest_areas else []
        return {
            "success": True,
            "policy_themes": themes,
            "target_industries": themes,
            "budget_info": {},
            "timeline": {},
            "key_policies": [],
            "summary": "관심 분야 기반 가설용 정책 요약입니다.",
            "warnings": ["정책 문서 입력이 없어 관심 분야만 반영됨"],
            "fallback_used": True,
            "source_reliability": [0.4],
        }

    async def analyze_and_recommend(
        self,
        pdf_paths: List[str] = None,
        text_content: str = None,
        interest_areas: List[str] = None,
        focus_keywords: List[str] = None,
        autonomous_mode: bool = True,
        document_weight: float = 0.7,
        fusion_proposals: Optional[List[Dict[str, Any]]] = None,
        fusion_feedback: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        PDF/텍스트 분석부터 추천까지 전체 파이프라인 실행

        Args:
            pdf_paths: PDF 파일 경로 리스트 (선택)
            text_content: 분석할 텍스트 콘텐츠 (선택)
            interest_areas: 사용자 관심 분야
            focus_keywords: 집중 분석 키워드
            autonomous_mode: 가설/검증 루프 실행 여부
            document_weight: 문서 기반 가중치 (0~1)
            fusion_proposals: 사전 융합안 리스트
            fusion_feedback: 융합안 사용자 평가

        Returns:
            {
                "success": bool,
                "policy_analysis": {...},
                "iris_mapping": {...},
                "recommendations": {...},
                "hypotheses": {...},
                "verification": {...}
            }
        """
        self.pdf_paths = pdf_paths or []
        self.interest_areas = interest_areas or []
        self.hypotheses = None
        self.verification = None
        if document_weight is not None:
            try:
                self.document_weight = max(min(float(document_weight), 1.0), 0.0)
            except (TypeError, ValueError):
                pass
        if not self.interest_areas:
            self.document_weight = 1.0
        self.fusion_proposals = fusion_proposals or []
        self.fusion_feedback = fusion_feedback or {}

        session_id = self.memory.session_id
        created_at = datetime.now().isoformat()

        result = {
            "success": False,
            "policy_analysis": None,
            "iris_mapping": None,
            "recommendations": None,
            "hypotheses": None,
            "verification": None,
            "document_weight": self.document_weight,
            "fusion_proposals": self.fusion_proposals,
            "fusion_feedback": self.fusion_feedback,
            "session_id": session_id,
            "report_path": None,
            "checkpoint_path": None,
            "errors": []
        }

        def _save_checkpoint(stage: str) -> None:
            payload = {
                "created_at": created_at,
                "session_id": session_id,
                "stage": stage,
                "interest_areas": self.interest_areas,
                "pdf_paths": self.pdf_paths,
                "text_content_excerpt": (text_content or "")[:2000],
                "policy_analysis": self.policy_analysis,
                "iris_mapping": self.iris_mapping,
                "recommendations": self.recommendations,
                "hypotheses": self.hypotheses,
                "verification": self.verification,
                "document_weight": self.document_weight,
                "fusion_proposals": self.fusion_proposals,
                "fusion_feedback": self.fusion_feedback,
            }
            try:
                result["checkpoint_path"] = self.session_store.save_checkpoint(session_id, payload)
            except Exception:
                pass

        has_content = bool(self.pdf_paths or (text_content and text_content.strip()))
        if not has_content and not self.interest_areas:
            result["errors"].append("분석할 콘텐츠 또는 관심 분야가 없습니다")
            return result

        # 1. 정책 분석 (PDF/텍스트 또는 관심 분야 기반)
        if has_content:
            policy_result = execute_tool("analyze_government_policy", {
                "pdf_paths": pdf_paths or [],
                "text_content": text_content,
                "focus_keywords": focus_keywords,
                "max_pages_per_pdf": 30,
                "api_key": self.api_key
            })
        else:
            policy_result = self._build_stub_policy_analysis(self.interest_areas)

        if not policy_result.get("success"):
            result["errors"].append(f"정책 분석 실패: {policy_result.get('error')}")
            return result

        self.policy_analysis = policy_result
        result["policy_analysis"] = policy_result
        _save_checkpoint("policy_analysis")

        # 2. IRIS+ 매핑
        policy_themes = policy_result.get("policy_themes", [])
        target_industries = policy_result.get("target_industries", [])

        if policy_themes:
            iris_result = execute_tool("map_policy_to_iris", {
                "policy_themes": policy_themes,
                "target_industries": target_industries,
                "min_relevance_score": 0.3
            })

            if iris_result.get("success"):
                self.iris_mapping = iris_result
                result["iris_mapping"] = iris_result
            else:
                result["errors"].append(f"IRIS+ 매핑 실패: {iris_result.get('error')}")
        if not self.iris_mapping:
            self.iris_mapping = {
                "success": False,
                "mappings": [],
                "aggregate_sdgs": [],
                "aggregate_metrics": [],
                "warnings": ["IRIS+ 매핑 결과 없음"]
            }
            result["iris_mapping"] = self.iris_mapping
        _save_checkpoint("iris_mapping")

        # 3. 산업 추천 생성
        if self.policy_analysis:
            rec_result = execute_tool("generate_industry_recommendation", {
                "policy_analysis": self.policy_analysis,
                "iris_mapping": self.iris_mapping,
                "interest_areas": self.interest_areas,
                "recommendation_count": 5,
                "api_key": self.api_key,
                "document_weight": self.document_weight
            })

            if rec_result.get("success"):
                self.recommendations = rec_result
                result["recommendations"] = rec_result
            else:
                result["errors"].append(f"추천 생성 실패: {rec_result.get('error')}")
        _save_checkpoint("recommendations")

        # 4. 가설 생성
        if self.interest_areas:
            generator = HypothesisGenerator(api_key=self.api_key)
            hypo_result = generator.generate(
                interest_areas=self.interest_areas,
                policy_analysis=self.policy_analysis,
                iris_mapping=self.iris_mapping,
                fusion_proposals=self.fusion_proposals,
                fusion_feedback=self.fusion_feedback,
            )
            if hypo_result.get("success"):
                self.hypotheses = hypo_result
                result["hypotheses"] = hypo_result
            else:
                result["errors"].append(f"가설 생성 실패: {hypo_result.get('error')}")
        _save_checkpoint("hypotheses")

        # 5. 검증 루프 + 신뢰점수
        if autonomous_mode:
            verifier = DiscoveryVerifier(api_key=self.api_key)
            self.verification = verifier.verify(
                policy_analysis=self.policy_analysis,
                iris_mapping=self.iris_mapping,
                recommendations=self.recommendations,
                hypotheses=self.hypotheses,
                interest_areas=self.interest_areas,
            )
            result["verification"] = self.verification
            _save_checkpoint("verification")

        if self.policy_analysis:
            result["success"] = True
            if result["errors"]:
                result["warnings"] = list(result["errors"])
                result["errors"] = []
        else:
            result["success"] = len(result["errors"]) == 0

        session_payload = {
            "created_at": created_at,
            "interest_areas": self.interest_areas,
            "pdf_paths": self.pdf_paths,
            "text_content_excerpt": (text_content or "")[:2000],
            "policy_analysis": self.policy_analysis,
            "iris_mapping": self.iris_mapping,
            "recommendations": self.recommendations,
            "hypotheses": self.hypotheses,
            "verification": self.verification,
            "document_weight": self.document_weight,
            "fusion_proposals": self.fusion_proposals,
            "fusion_feedback": self.fusion_feedback,
        }
        try:
            stored = self.session_store.save_session(session_id, session_payload, write_report=True)
            result["report_path"] = stored.get("report_path")
        except Exception:
            pass

        if self.pdf_paths:
            for path in self.pdf_paths:
                self.memory.add_file_analysis(path)
        if result.get("report_path"):
            self.memory.add_generated_file(result["report_path"])

        return result

    async def chat(
        self,
        user_message: str,
        stream: bool = True
    ) -> AsyncIterator[str]:
        """
        대화형 인터페이스

        Args:
            user_message: 사용자 메시지
            stream: 스트리밍 여부

        Yields:
            응답 텍스트 청크
        """
        if not self.client or not self.async_client:
            yield "API 키가 없어 대화형 응답을 제공할 수 없습니다. 분석 결과 기반 Q&A는 API 키를 설정해주세요."
            return
        # 시스템 프롬프트 생성
        context = self._get_context_string()
        system_prompt = DISCOVERY_SYSTEM_PROMPT.format(context=context)

        # 히스토리에 사용자 메시지 추가
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        try:
            if stream:
                async for chunk in self._stream_response(system_prompt):
                    yield chunk
            else:
                response = await self._get_response(system_prompt)
                yield response

        except Exception as e:
            yield f"오류가 발생했습니다: {str(e)}"

    async def _stream_response(self, system_prompt: str) -> AsyncIterator[str]:
        """스트리밍 응답 생성"""
        full_response = ""

        with self.client.messages.stream(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=self.conversation_history,
            tools=self.tools
        ) as stream:
            for event in stream:
                if hasattr(event, 'type'):
                    if event.type == 'content_block_delta':
                        if hasattr(event.delta, 'text'):
                            text = event.delta.text
                            full_response += text
                            yield text

                    elif event.type == 'message_stop':
                        break

        # 히스토리에 어시스턴트 응답 추가
        if full_response:
            self.conversation_history.append({
                "role": "assistant",
                "content": full_response
            })

    async def _get_response(self, system_prompt: str) -> str:
        """비스트리밍 응답 생성"""
        response = await self.async_client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=self.conversation_history,
            tools=self.tools
        )

        # 응답 처리
        full_response = ""
        for block in response.content:
            if hasattr(block, 'text'):
                full_response += block.text
            elif hasattr(block, 'type') and block.type == 'tool_use':
                # 도구 실행
                tool_input = dict(block.input or {})
                if block.name in {"analyze_government_policy", "generate_industry_recommendation"}:
                    tool_input.setdefault("api_key", self.api_key)
                tool_result = execute_tool(block.name, tool_input)
                full_response += f"\n[도구 실행: {block.name}]\n"
                full_response += json.dumps(tool_result, ensure_ascii=False, indent=2)

        # 히스토리에 추가
        if full_response:
            self.conversation_history.append({
                "role": "assistant",
                "content": full_response
            })

        return full_response

    def add_pdf(self, pdf_path: str) -> bool:
        """PDF 경로 추가"""
        if pdf_path not in self.pdf_paths:
            self.pdf_paths.append(pdf_path)
            return True
        return False

    def set_interest_areas(self, areas: List[str]):
        """관심 분야 설정"""
        self.interest_areas = areas

    def get_status(self) -> Dict[str, Any]:
        """현재 분석 상태 반환"""
        return {
            "pdf_count": len(self.pdf_paths),
            "pdf_paths": self.pdf_paths,
            "interest_areas": self.interest_areas,
            "policy_analyzed": self.policy_analysis is not None,
            "iris_mapped": self.iris_mapping is not None,
            "recommendations_generated": self.recommendations is not None,
            "document_weight": self.document_weight,
            "fusion_proposal_count": len(self.fusion_proposals),
            "policy_themes": self.policy_analysis.get("policy_themes", []) if self.policy_analysis else [],
            "target_industries": self.policy_analysis.get("target_industries", []) if self.policy_analysis else [],
            "aggregate_sdgs": self.iris_mapping.get("aggregate_sdgs", []) if self.iris_mapping else [],
            "recommendation_count": len(self.recommendations.get("recommendations", [])) if self.recommendations else 0,
            "hypothesis_count": len(self.hypotheses.get("hypotheses", [])) if self.hypotheses else 0,
            "trust_score": self.verification.get("trust_score") if self.verification else None,
        }

    def get_recommendations(self) -> Optional[Dict[str, Any]]:
        """추천 결과 반환"""
        return self.recommendations

    def reset(self):
        """상태 초기화"""
        self.policy_analysis = None
        self.iris_mapping = None
        self.recommendations = None
        self.interest_areas = []
        self.pdf_paths = []
        self.hypotheses = None
        self.verification = None
        self.conversation_history = []
        self.document_weight = 0.7
        self.fusion_proposals = []
        self.fusion_feedback = {}


# 동기 래퍼 (Streamlit 호환)
def run_discovery_analysis(
    pdf_paths: List[str] = None,
    text_content: str = None,
    interest_areas: List[str] = None,
    focus_keywords: List[str] = None,
    api_key: str = None,
    autonomous_mode: bool = True,
    document_weight: float = 0.7,
    fusion_proposals: Optional[List[Dict[str, Any]]] = None,
    fusion_feedback: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    동기 방식으로 발굴 분석 실행 (Streamlit 호환)

    Args:
        pdf_paths: PDF 파일 경로 리스트 (선택)
        text_content: 분석할 텍스트 콘텐츠 (선택)
        interest_areas: 관심 분야
        focus_keywords: 집중 키워드
        api_key: API 키
        autonomous_mode: 가설/검증 루프 실행 여부
        document_weight: 문서 기반 가중치 (0~1)
        fusion_proposals: 사전 융합안 리스트
        fusion_feedback: 융합안 사용자 평가
    """
    agent = DiscoveryAgent(api_key=api_key)
    return asyncio.run(agent.analyze_and_recommend(
        pdf_paths=pdf_paths,
        text_content=text_content,
        interest_areas=interest_areas,
        focus_keywords=focus_keywords,
        autonomous_mode=autonomous_mode,
        document_weight=document_weight,
        fusion_proposals=fusion_proposals,
        fusion_feedback=fusion_feedback,
    ))


def run_fusion_proposals(
    interest_areas: List[str],
    policy_analysis: Optional[Dict[str, Any]] = None,
    iris_mapping: Optional[Dict[str, Any]] = None,
    proposal_count: int = 4,
    api_key: str = None,
) -> Dict[str, Any]:
    generator = HypothesisGenerator(api_key=api_key)
    return generator.generate_fusion_proposals(
        interest_areas=interest_areas,
        policy_analysis=policy_analysis,
        iris_mapping=iris_mapping,
        proposal_count=proposal_count,
    )
