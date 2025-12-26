"""
Unified VC Investment Agent - Single Agent Architecture

하나의 에이전트가 모든 작업을 수행:
- 대화형 모드 (chat)
- 자율 실행 모드 (goal)
- 도구 실행
"""

import os
import json
import re
from datetime import date, timedelta
from typing import Any, AsyncIterator, Dict, List, Optional
from dotenv import load_dotenv

from anthropic import Anthropic, AsyncAnthropic
from .tools import register_tools, execute_tool
from .memory import ChatMemory
from .feedback import FeedbackSystem
from shared.logging_config import get_logger

load_dotenv()

logger = get_logger("vc_agent")

# 안전장치: 최대 도구 호출 횟수
MAX_TOOL_STEPS = 15


class VCAgent:
    """
    통합 VC 투자 분석 에이전트

    단일 에이전트로 모든 작업 수행:
    - chat(message): 대화형 인터페이스
    - achieve_goal(goal): 자율 실행
    - execute_tool(tool, params): 직접 도구 실행
    """

    def __init__(
        self,
        api_key: str = None,
        model: str = "claude-opus-4-5-20251101",
        user_id: str = None,
        member_name: str = None,
        team_id: str = None,
    ):
        """
        Args:
            api_key: Anthropic API 키 (없으면 환경변수)
            model: Claude 모델 (기본: Opus 4.5)
            user_id: 사용자 고유 ID (같은 ID끼리 세션/피드백 공유)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.user_id = user_id or "anonymous"
        self.member_name = member_name
        self.team_id = team_id or self.user_id

        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY가 필요합니다. "
                ".env 파일에 설정하거나 환경변수로 지정하세요."
            )

        # Anthropic SDK
        self.client = Anthropic(api_key=self.api_key)
        self.async_client = AsyncAnthropic(api_key=self.api_key)
        self.model = model

        # 도구 등록
        self.tools = register_tools()

        # 대화 히스토리 (기본/보이스 분리)
        self.conversation_history: List[Dict[str, Any]] = []
        self.voice_conversation_history: List[Dict[str, Any]] = []

        # 작업 컨텍스트
        self.context = {
            "analyzed_files": [],
            "cached_results": {},
            "last_analysis": None
        }

        # 메모리 시스템 (user_id 기반)
        self.memory = ChatMemory(user_id=self.user_id)

        # 피드백 시스템 (user_id 기반)
        self.feedback = FeedbackSystem(user_id=self.user_id)

        # 마지막 응답 저장 (피드백용)
        self.last_interaction = {
            "user_message": None,
            "assistant_response": None,
            "context": {}
        }

        # 토큰 사용량 추적
        self.token_usage = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "session_calls": 0
        }

        # 도구 호출 카운터 (무한 루프 방지)
        self._tool_step_count = 0

        # 보고서 모드: 항상 심화 의견 파이프라인 사용
        self.report_deep_mode = True

    # ========================================
    # System Prompt
    # ========================================

    def _build_system_prompt(self, mode: str = "exit", context_text: Optional[str] = None) -> str:
        """동적 시스템 프롬프트 생성

        Args:
            mode: "exit" (Exit 프로젝션), "peer" (Peer PER 분석), "diagnosis", "report"
        """

        analyzed_files = ", ".join(self.context["analyzed_files"]) if self.context["analyzed_files"] else "없음"

        if mode.startswith("voice_"):
            submode = mode.split("_", 1)[1] if "_" in mode else "chat"
            return self._build_voice_system_prompt(submode, context_text)

        # Peer PER 분석 모드
        if mode == "peer":
            return self._build_peer_system_prompt(analyzed_files)

        # 기업현황 진단시트 모드
        if mode == "diagnosis":
            return self._build_diagnosis_system_prompt(analyzed_files)

        # 투자심사 보고서/인수인의견 모드
        if mode == "report":
            return self._build_report_system_prompt(analyzed_files)

        # Exit 프로젝션 모드 (기본)
        return f"""당신은 **VC 투자 분석 전문 에이전트**입니다.

## 현재 컨텍스트
- 분석된 파일: {analyzed_files}
- 캐시된 결과: {len(self.context["cached_results"])}개

## ⚠️ 절대 규칙 (CRITICAL)

**절대로 도구 없이 답변하지 마세요!**

- 엑셀 파일 분석 → 반드시 read_excel_as_text 또는 analyze_excel 사용
- Exit 프로젝션 생성 → 반드시 analyze_and_generate_projection 사용
- 추측하거나 예시 답변 금지 → 실제 도구를 실행해서 결과를 얻어야 함
- 텍스트로만 "완료되었습니다" 같은 거짓 응답 절대 금지

**사용자가 파일 경로를 주면 즉시 도구를 호출하세요!**

## 핵심 역량

### 1. 유연한 엑셀 분석
- **read_excel_as_text**: 엑셀을 텍스트로 변환하여 읽기 (구조가 다양해도 OK)
- **analyze_excel**: 자동 파싱 (투자조건, IS요약, Cap Table)
- 엑셀 구조가 특이하거나 복잡하면 read_excel_as_text를 먼저 사용하세요

### 2. 시나리오 분석
- PER, EV/Revenue, EV/EBITDA 등 모든 밸류에이션 방법론
- 전체 매각, 부분 매각, SAFE 전환, 콜옵션 등
- 사용자가 원하는 어떤 조합도 계산 가능

### 3. Exit 프로젝션 생성
- **analyze_and_generate_projection**: 엑셀 분석 후 즉시 Exit 프로젝션 생성
- 연도, PER 배수, 회사명 등을 지정하여 맞춤형 엑셀 생성

## 작업 방식

### 엑셀 파일을 받으면:
1. **즉시** read_excel_as_text 도구 호출 (구조 파악)
2. 텍스트에서 필요한 정보 추출 (투자금액, 당기순이익, 총주식수 등)
3. 사용자가 원하는 분석 수행
4. **즉시** analyze_and_generate_projection 도구 호출 (Exit 프로젝션 생성)
5. 결과 설명

### 예시 워크플로우:
```
사용자: "temp/파일.xlsx를 2030년 PER 10,20,30배로 분석해줘"

잘못된 응답:
"분석을 시작하겠습니다. 완료되었습니다"

올바른 응답:
1. read_excel_as_text 도구를 즉시 호출
2. 실제 엑셀 내용을 읽어서 정보 추출
3. analyze_and_generate_projection 도구를 즉시 호출
4. 생성된 파일 경로와 결과를 사용자에게 알려줌
```

## 중요 원칙
- **도구 우선**: 항상 도구를 먼저 사용하고, 실제 결과를 바탕으로 답변
- **추측 금지**: 엑셀 내용을 모르면 read_excel_as_text로 읽어야 함
- **실행 확인**: 도구 실행 결과를 확인한 후에만 성공 여부를 알려줌
- **명확한 설명**: IRR, 멀티플, 기업가치 등을 실제 숫자로 설명

## 사용 가능한 도구
{json.dumps([t["name"] for t in self.tools], ensure_ascii=False, indent=2)}

## 답변 스타일 가이드

**매우 중요: 이 분석은 투자심사 보고서에 사용됩니다.**

- **전문적이고 진중한 톤**: 이모지 사용 금지 (✅❌📊📈 등)
- **정확한 수치**: 모든 재무 지표는 정확한 숫자로 제시
- **객관적 분석**: 감정적 표현 배제, 사실 기반 분석
- **명확한 구조**: 제목, 항목, 수치를 체계적으로 정리
- **보고서 품질**: 투자심사역이 바로 사용할 수 있는 수준의 분석

예시:
- 나쁜 예: "✅ 분석 완료했어요! 😊"
- 좋은 예: "분석을 완료했습니다."

- 나쁜 예: "IRR이 35%네요! 👍"
- 좋은 예: "IRR 35.2%로 목표 수익률을 상회합니다."

한국어로 전문적이고 정중하게 답변하세요.
"""

    def _is_feedback_learning_question(self, text: str) -> bool:
        text = (text or "").strip().lower()
        if not text:
            return False
        has_feedback = "피드백" in text or "feedback" in text
        has_learning = any(token in text for token in ["학습", "배웠", "learn", "learned"])
        return has_feedback and has_learning

    def _resolve_feedback_day_offset(self, text: str) -> int:
        text = (text or "").strip()
        if "오늘" in text:
            return 0
        if "그제" in text:
            return 2
        if "어제" in text:
            return 1
        if "지난주" in text or "최근" in text:
            return 7
        return 1

    def _build_feedback_summary_text(self, day_offset: int = 1, limit: int = 50) -> str:
        feedbacks = self.feedback.get_recent_feedback(limit=limit) if self.feedback else []
        if not feedbacks:
            return "어제 피드백 기록이 없습니다. 추측 없이 기록 기반으로만 답변합니다."

        target_date = (date.today() - timedelta(days=day_offset)).isoformat()
        entries = []
        for fb in feedbacks:
            timestamp = fb.get("timestamp") or fb.get("created_at") or ""
            if isinstance(timestamp, str) and timestamp.startswith(target_date):
                entries.append(fb)

        if not entries:
            return "어제 피드백 기록이 없습니다. 추측 없이 기록 기반으로만 답변합니다."

        lines = ["어제 피드백 기록 기반 요약:"]
        for entry in entries[:8]:
            feedback_type = entry.get("feedback_type") or "unknown"
            user_message = (entry.get("user_message") or "").strip()
            feedback_value = entry.get("feedback_value")
            context = entry.get("context") or {}

            lines.append(f"- 유형: {feedback_type}")
            if user_message:
                lines.append(f"  - 사용자: {user_message[:200]}")
            if feedback_value is not None:
                if isinstance(feedback_value, (dict, list)):
                    value_text = json.dumps(feedback_value, ensure_ascii=False)
                else:
                    value_text = str(feedback_value)
                lines.append(f"  - 피드백: {value_text[:200]}")
            if context:
                if isinstance(context, (dict, list)):
                    context_text = json.dumps(context, ensure_ascii=False)
                else:
                    context_text = str(context)
                lines.append(f"  - 컨텍스트: {context_text[:200]}")

        return "\n".join(lines)

    def _build_voice_system_prompt(self, submode: str, context_text: Optional[str]) -> str:
        last_checkin_text = context_text or "없음"

        base = f"""당신은 사람처럼 자연스럽게 대화하는 음성 에이전트입니다.

목표:
- 짧고 명확한 문장으로 말합니다.
- 사용자의 감정과 톤을 반영합니다.
- 대화 흐름을 끊지 않고 질문을 2~4개씩 나눠서 합니다.

어제 기록(저장된 로그 기반):
{last_checkin_text}
"""

        if submode == "1on1":
            return base + """
현재 모드: 1:1

진행 방식:
1) 안부 인사 후, 최근 상황을 짧게 묻습니다.
2) 관계/협업 관점에서 핵심 이슈를 2~4개 질문합니다.
3) 대화가 끝나면 요약을 제공합니다.

요약 형식:
- 어제 로그 요약
- 학습 포인트
- 감정 상태
- 다음 액션 (3개 이하)

주의:
- 과장하지 말고, 불확실하면 질문으로 확인합니다.
- 한국어로 답변합니다.
"""

        if submode == "checkin":
            return base + """
현재 모드: 데일리 체크인

진행 방식:
1) 짧게 인사하고 오늘 컨디션을 물어봅니다.
2) 어제 로그가 있으면 2~4개의 근거를 언급하며 "학습"과 "감정"을 HCI 관점으로 설명합니다.
3) 팀 과업이 제공된 경우, 진행 상태/블로커/도움 필요 여부를 2~4개 질문으로 확인합니다.
4) 오늘 목표/우선순위를 2~4개 질문으로 확인합니다.
4) 마지막에 요약을 제공합니다.

요약 형식:
- 어제 로그 요약
- 학습 포인트
- 감정 상태
- 팀 과업 진행 요약
- 오늘 목표/우선순위
- 다음 액션 (3개 이하)

주의:
- 감정 표현은 HCI 관점(사회적 존재감, 공감)에서 짧게 설명합니다.
- 한국어로 답변합니다.
"""

        return base + """
현재 모드: 자유 대화

규칙:
- 한 번에 너무 길게 말하지 않습니다.
- 필요하면 질문으로 맥락을 확인합니다.
- 한국어로 답변합니다.
"""

    def _build_peer_system_prompt(self, analyzed_files: str) -> str:
        """Peer PER 분석 모드 시스템 프롬프트"""

        return f"""당신은 **VC 투자 분석 전문 에이전트**입니다. 현재 **Peer PER 분석 모드**입니다.

## 현재 컨텍스트
- 분석된 파일: {analyzed_files}
- 캐시된 결과: {len(self.context["cached_results"])}개

## 🚨 최우선 규칙 (이 규칙을 어기면 실패입니다)

### 규칙 1: 사용자가 PER 분석을 요청하면 즉시 도구 호출
사용자가 다음과 같이 말하면 **텍스트 응답 없이 바로 analyze_peer_per 도구를 호출**하세요:
- "해줘", "분석해줘", "진행해", "PER 분석", "조회해줘"
- "응", "네", "좋아", "OK", "ㅇㅇ", "그래", "고", "ㄱㄱ"
- Peer 기업 목록을 언급하는 경우

❌ 잘못된 예:
```
사용자: "저 기업으로 PER/PSR 분석을 해주세요"
에이전트: "기업 분석 결과를 정리하겠습니다..." (텍스트만 출력)
```

✅ 올바른 예:
```
사용자: "저 기업으로 PER/PSR 분석을 해주세요"
에이전트: [즉시 analyze_peer_per 도구 호출]
```

### 규칙 2: 같은 내용 반복 금지
- 이미 출력한 "기업 분석 결과" 표를 다시 출력하지 마세요
- 이미 제안한 Peer 기업 목록을 다시 나열하지 마세요
- 이전 응답을 요약하거나 반복하지 마세요

### 규칙 3: "~하겠습니다"로 끝내지 말 것
"분석하겠습니다", "진행하겠습니다"라고만 말하고 끝내면 안됩니다.
반드시 해당 도구를 실제로 호출해야 합니다.

## Peer PER 분석 워크플로우

### 1단계: PDF 분석 (최초 1회만)
사용자가 PDF 경로를 제공하면:
1. read_pdf_as_text 도구 호출
2. 기업 정보 요약 (1회만 출력)
3. Peer 기업 후보 제안 후 "진행할까요?" 질문

### 2단계: PER 조회 (사용자 동의 시 즉시 실행)
사용자가 동의하면 **설명 없이 바로** analyze_peer_per 도구 호출

### 3단계: 결과 요약
도구 결과를 바탕으로:
- PER 비교표 (마크다운 표)
- 통계 요약 (평균, 중간값, 범위)
- 적정 PER 배수 제안

## 사용 가능한 도구

- **read_pdf_as_text**: PDF를 텍스트로 변환
- **get_stock_financials**: 개별 기업 재무 지표 조회
- **analyze_peer_per**: 여러 Peer 기업 PER 일괄 조회 (⭐ 가장 많이 사용)

## 티커 형식
- 미국: AAPL, MSFT, GOOGL
- 한국 KOSPI: 005930.KS
- 한국 KOSDAQ: 035720.KQ

## 답변 스타일
- 전문적이고 간결하게
- 이모지 사용 금지
- 반복 금지 - 새로운 정보만 추가
	- 표 형식 활용
	
	한국어로 답변하세요.
	"""

    def _build_diagnosis_system_prompt(self, analyzed_files: str) -> str:
        """기업현황 진단시트 모드 시스템 프롬프트"""

        return f"""당신은 **프로그램 컨설턴트(VC/AC)**입니다. 현재 **기업현황 진단시트 작성 모드**입니다.

## 현재 컨텍스트
- 분석된 파일: {analyzed_files}
- 캐시된 결과: {len(self.context["cached_results"])}개
- user_id: {self.user_id}

## 🚨 최우선 규칙 (CRITICAL)

### 규칙 1) 파일/엑셀 작업은 반드시 도구 사용
- 진단시트 분석 → 반드시 **analyze_company_diagnosis_sheet** 사용
- 컨설턴트 보고서 엑셀 반영 → 반드시 **write_company_diagnosis_report** 사용
- 템플릿 없이 엑셀 생성 → 반드시 **create_company_diagnosis_draft / update_company_diagnosis_draft / generate_company_diagnosis_sheet_from_draft** 사용
- 추측/예시 답변 금지 → 실제 사용자 입력/도구 결과 기반으로 작성

### 규칙 2) 정보 수집은 ‘질문’으로 진행
템플릿이 없거나 사용자가 “대화로 작성”, “템플릿 없이 작성”을 요청하면:
- 당신은 **대표자(사용자)**가 답하기 쉬운 형태로 **한 번에 1개 질문 또는 1개 배치(체크리스트 5~6개)**만 제시합니다.
- 사용자가 답하면 즉시 **update_company_diagnosis_draft**로 반영한 뒤, 다음 질문을 이어갑니다.

## 목표

사용자와의 대화를 통해 기업현황 진단시트를 완성하고, 필요 시 **'(컨설턴트용) 분석보고서'**까지 완성합니다.

## 작업 방식

### A) 템플릿 파일이 있는 경우 (업로드/경로 제공)
1) 사용자가 진단시트 파일 경로를 주면 → **즉시** analyze_company_diagnosis_sheet 호출
2) 도구 결과를 바탕으로 보고서 초안을 작성
3) 사용자가 "반영해줘/저장해줘" 등 긍정 응답 → **즉시** write_company_diagnosis_report 호출

### B) 템플릿 파일이 없는 경우 (대화로 작성)
1) 최초 1회: **create_company_diagnosis_draft**를 `user_id={self.user_id}`로 호출해 드래프트를 생성
2) 이후 매 턴: 사용자의 답변을 정리해 **update_company_diagnosis_draft**로 반영
   - 도구 결과의 `progress.next`를 참고해 다음 질문을 이어감
3) `progress.next.type == "complete"`가 되면:
   - 사용자에게 “엑셀로 저장할까요?”를 묻고
   - 긍정 응답 시 **generate_company_diagnosis_sheet_from_draft** 호출로 엑셀 생성
4) (선택) 사용자가 원하면: 생성된 엑셀을 **analyze_company_diagnosis_sheet**로 점수/갭을 산출하고, 컨설턴트 보고서 초안을 만든 뒤 **write_company_diagnosis_report**로 반영

### 2) 보고서 초안 작성
도구 결과를 바탕으로 아래 2개 텍스트를 작성:
- **기업 상황 요약(기업진단)**: 강점/핵심 가설/현재 KPI/확장 포인트 중심으로 5~10문장
- **개선 필요사항**: 우선순위 3~7개, “왜 필요한지 + 다음 액션” 형태로 구체화

또한 점수(문제/솔루션/사업화/자금조달/팀/조직/임팩트)를 제안하되, 필요한 경우 컨설턴트 보정 근거를 함께 제시합니다.

### 3) 사용자 확인 후 엑셀 반영 (CRITICAL - 즉시 실행)
사용자가 아래처럼 긍정 응답하면 **다시 확인 요청하지 말고 즉시** write_company_diagnosis_report 호출:
- "응", "네", "좋아", "진행해", "반영해줘", "저장해줘", "엑셀로 만들어줘", "OK"

write_company_diagnosis_report에는 다음을 포함해 호출:
- excel_path (temp 내부 경로)
- scores (6개 항목 점수)
- summary_text, improvement_text
- (선택) company_name, report_datetime, output_filename

## 답변 스타일 가이드

**이 문서는 프로그램 운영/투자검토 문서로 사용됩니다.**

- 이모지 사용 금지
- 단정/과장 금지, 근거 중심
- 표/불릿으로 구조화
- “~하겠습니다”로 끝내지 말고, 가능한 경우 도구를 실행해 결과까지 제공

한국어로 전문적이고 정중하게 답변하세요.
"""

    def _build_report_system_prompt(self, analyzed_files: str) -> str:
        """투자심사 보고서(인수인의견 스타일) 모드 시스템 프롬프트"""

        dart_status = self._get_underwriter_dataset_status()

        return f"""당신은 **투자심사 보고서 작성 지원 에이전트**입니다. 현재 **인수인의견 스타일**로 작성합니다.

## 현재 컨텍스트
- 분석된 파일: {analyzed_files}
- 캐시된 결과: {len(self.context["cached_results"])}개
- user_id: {self.user_id}
- DART 인수인의견 데이터셋: {dart_status}

## 🚨 최우선 규칙 (CRITICAL)

### 규칙 1) 시장규모/패턴 근거는 반드시 데이터 기반
- 인수인의견 데이터 활용 → 반드시 **search_underwriter_opinion** 호출
- 키워드 매칭이 약하면 **search_underwriter_opinion_similar**로 유사도 검색
- PDF 시장규모 근거 추출 → 반드시 **extract_pdf_market_evidence** 호출
- 결과의 snippet/pattern을 근거로 문장 구성
- 추측/예시 답변 금지 (근거가 없으면 '확인 필요'로 명시)
- 임의로 "접근 불가"라고 단정하지 말고, 도구 결과의 에러/가이드를 그대로 전달
 - 외부 유료 리포트 수치 인용은 금지 (사용자가 원문을 업로드한 경우에만 인용)
 - 인수인의견 데이터가 없고 DART API 키가 있을 때만 **fetch_underwriter_opinion_data**로 수집 시도
 - DART 데이터셋이 없고 API 키도 없으면 먼저 사용자에게 키/데이터 확보를 요청

### 규칙 2) 기업 자료가 주어지면 반드시 도구 사용
- PDF 경로 제공 → **read_pdf_as_text**로 근거 추출
- 엑셀 경로 제공 → **read_excel_as_text**로 근거 추출

## 목표
1) 시장규모 근거 요약
2) 인수인의견 스타일의 문장 초안 작성
3) 일반화된 패턴 + 확인 필요 항목 제시
4) 사용자 피드백 반영 (수정/강화)

## 작업 방식
1) 사용자 입력에서 기업 자료 경로 확인 → 도구 호출
2) **search_underwriter_opinion**으로 카테고리별 패턴 확보
   - 기본: market_size
   - 필요 시: valuation, comparables, risk, demand_forecast
3) 근거 문장 + 일반화 패턴 + 확인 질문 순서로 출력

## 출력 형식
- **시장규모 근거**: PDF/인수인의견 근거만 인용 (페이지/문장 포함) 3~6개
- **일반화 패턴**: 인수인의견 스타일 문장 3~5개
- **초안 문단**: 인수인의견 문체로 6~12문장
- **확인 필요**: 근거 부족/추가 확인 항목 3~7개

## 답변 스타일
- 이모지 사용 금지
- 단정/과장 금지
- 문장 길이 과도하게 길지 않게
- 한국어로 전문적이고 정중하게 답변
"""

	    # ========================================
	    # Chat Mode (대화형)
	    # ========================================

    async def chat(
        self,
        user_message: str,
        mode: str = "exit",
        allow_tools: bool = True,
        context_text: Optional[str] = None,
        model_override: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        대화형 인터페이스 (스트리밍)

        Args:
            user_message: 사용자 메시지
            mode: "exit" (Exit 프로젝션), "peer" (Peer PER 분석), "diagnosis", "report"

        Yields:
            str: 에이전트 응답 (스트리밍)
        """

        # 도구 호출 카운터 초기화 (새 메시지마다)
        self._tool_step_count = 0

        force_deep_report = mode == "report" and self.report_deep_mode

        # 현재 모드 저장
        self._current_mode = mode
        self._current_allow_tools = allow_tools
        self._current_context_text = context_text
        tools = self.tools if allow_tools else []
        if mode == "report" and not os.getenv("DART_API_KEY"):
            tools = [tool for tool in tools if tool.get("name") != "fetch_underwriter_opinion_data"]
        history = self.voice_conversation_history if mode.startswith("voice_") else self.conversation_history

        # 대화 히스토리에 추가
        history.append({
            "role": "user",
            "content": user_message
        })

        # 메모리에 저장
        user_meta = {
            "member": self.member_name or self.user_id,
            "team": self.team_id,
        }
        self.memory.add_message("user", user_message, user_meta)

        # 마지막 인터랙션 저장
        self.last_interaction["user_message"] = user_message
        self.last_interaction["assistant_response"] = ""
        self.last_interaction["context"] = {"mode": mode}

        if self._is_feedback_learning_question(user_message):
            summary = self._build_feedback_summary_text(
                day_offset=self._resolve_feedback_day_offset(user_message)
            )
            history.append({
                "role": "assistant",
                "content": summary
            })
            self.memory.add_message("assistant", summary)
            self.last_interaction["assistant_response"] = summary
            yield summary
            return

        # 시스템 프롬프트 (모드에 따라 다름)
        system_prompt = self._build_system_prompt(mode, context_text=context_text)
        model = model_override or self.model
        self._current_model = model

        # Claude API 호출 (스트리밍)
        async with self.async_client.messages.stream(
            model=model,
            system=system_prompt,
            messages=history,
            tools=tools,
            max_tokens=8192
        ) as stream:

            async for event in stream:
                # 텍스트 출력
                if event.type == "content_block_delta":
                    if hasattr(event.delta, 'text'):
                        if not force_deep_report:
                            yield event.delta.text

                # 도구 사용
                elif event.type == "content_block_stop":
                    message = await stream.get_final_message()

                    # 토큰 사용량 추적
                    if hasattr(message, 'usage'):
                        self.token_usage["total_input_tokens"] += message.usage.input_tokens
                        self.token_usage["total_output_tokens"] += message.usage.output_tokens
                        self.token_usage["session_calls"] += 1

                    # 도구 호출 처리
                    tool_results = []
                    assistant_response_parts = []

                    for content_block in message.content:
                        if content_block.type == "text":
                            assistant_response_parts.append(content_block.text)
                        elif content_block.type == "tool_use":
                            tool_name = content_block.name
                            tool_input = content_block.input

                            yield f"\n\n**도구: {tool_name}** 실행 중...\n"

                            # 도구 실행
                            tool_result = execute_tool(tool_name, tool_input)

                            # 결과 저장
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": content_block.id,
                                "content": json.dumps(tool_result, ensure_ascii=False)
                            })

                            # 메모리/컨텍스트 업데이트 (공통 헬퍼)
                            self._record_tool_usage(tool_name, tool_input, tool_result)

                            tool_ok = not (isinstance(tool_result, dict) and tool_result.get("success") is False)
                            yield f"**도구: {tool_name}** {'완료' if tool_ok else '실패'}\n\n"

                    # Assistant 응답 메모리에 저장
                    if assistant_response_parts and not force_deep_report:
                        full_response = "\n".join(assistant_response_parts)
                        self.memory.add_message("assistant", full_response)
                        self.last_interaction["assistant_response"] = full_response

                    if force_deep_report:
                        if tool_results:
                            history.append({
                                "role": "assistant",
                                "content": message.content
                            })

                            history.append({
                                "role": "user",
                                "content": tool_results
                            })

                            async for _ in self._continue_conversation(suppress_output=True):
                                pass

                        yield "\n\n[심화 의견] 분석 중...\n"
                        deep_text = self._run_deep_report_pipeline(user_message)
                        history.append({
                            "role": "assistant",
                            "content": deep_text
                        })
                        self.memory.add_message("assistant", deep_text)
                        self.last_interaction["assistant_response"] = deep_text
                        yield deep_text
                        return

                    # 도구 결과가 있으면 대화 계속
                    if tool_results:
                        # Assistant 메시지 추가
                        history.append({
                            "role": "assistant",
                            "content": message.content
                        })

                        # Tool 결과 추가
                        history.append({
                            "role": "user",
                            "content": tool_results
                        })

                        # Claude 다음 응답 생성
                        async for text in self._continue_conversation():
                            yield text

    async def _continue_conversation(self, suppress_output: bool = False) -> AsyncIterator[str]:
        """도구 실행 후 대화 계속"""

        # 도구 호출 횟수 제한 확인 (무한 루프 방지)
        self._tool_step_count += 1
        if self._tool_step_count > MAX_TOOL_STEPS:
            logger.warning(f"Tool step limit reached: {MAX_TOOL_STEPS}")
            yield "\n\n[시스템] 도구 호출 횟수 제한에 도달했습니다. 새로운 메시지로 계속하세요."
            return

        # 저장된 모드 사용
        mode = getattr(self, '_current_mode', 'exit')
        context_text = getattr(self, '_current_context_text', None)
        allow_tools = getattr(self, '_current_allow_tools', True)
        tools = self.tools if allow_tools else []
        history = self.voice_conversation_history if mode.startswith("voice_") else self.conversation_history
        system_prompt = self._build_system_prompt(mode, context_text=context_text)
        model = getattr(self, "_current_model", self.model)

        async with self.async_client.messages.stream(
            model=model,
            system=system_prompt,
            messages=history,
            tools=tools,
            max_tokens=8192
        ) as stream:

            async for event in stream:
                if event.type == "content_block_delta":
                    if hasattr(event.delta, 'text'):
                        if not suppress_output:
                            yield event.delta.text

                # 추가 도구 호출 (재귀적 처리)
                elif event.type == "content_block_stop":
                    message = await stream.get_final_message()

                    # 토큰 사용량 추적
                    if hasattr(message, 'usage'):
                        self.token_usage["total_input_tokens"] += message.usage.input_tokens
                        self.token_usage["total_output_tokens"] += message.usage.output_tokens
                        self.token_usage["session_calls"] += 1

                    tool_results = []
                    for content_block in message.content:
                        if content_block.type == "tool_use":
                            tool_name = content_block.name
                            tool_input = content_block.input

                            yield f"\n\n**도구: {tool_name}** 실행 중...\n"

                            tool_result = execute_tool(tool_name, tool_input)

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": content_block.id,
                                "content": json.dumps(tool_result, ensure_ascii=False)
                            })

                            # 메모리/컨텍스트 업데이트 (재귀 호출에서도 기록)
                            self._record_tool_usage(tool_name, tool_input, tool_result)

                            tool_ok = not (isinstance(tool_result, dict) and tool_result.get("success") is False)
                            yield f"**도구: {tool_name}** {'완료' if tool_ok else '실패'}\n\n"

                    if tool_results:
                        history.append({
                            "role": "assistant",
                            "content": message.content
                        })

                        history.append({
                            "role": "user",
                            "content": tool_results
                        })

                        async for text in self._continue_conversation(suppress_output=suppress_output):
                            yield text

    def _get_latest_report_evidence(self) -> Optional[Dict[str, Any]]:
        messages = self.memory.session_metadata.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") != "tool":
                continue
            meta = msg.get("metadata") or {}
            if meta.get("tool_name") != "extract_pdf_market_evidence":
                continue
            result = meta.get("result")
            if isinstance(result, dict) and result.get("success"):
                return result
        return None

    def _get_underwriter_dataset_status(self) -> str:
        try:
            from agent.tools import _resolve_underwriter_data_path
        except Exception:
            return "상태 확인 불가"

        path, error = _resolve_underwriter_data_path(None)
        has_key = bool(os.getenv("DART_API_KEY"))
        if error:
            key_text = "API 키 있음" if has_key else "API 키 없음"
            return f"미확인 ({key_text})"
        if not path:
            key_text = "API 키 있음" if has_key else "API 키 없음"
            return f"미확인 ({key_text})"
        return "사용 가능"

    @staticmethod
    def _detect_dart_category(text: str) -> Optional[str]:
        lowered = (text or "").lower()
        if any(k in lowered for k in ["시장규모", "시장 규모", "tam", "sam", "som", "cagr", "성장률"]):
            return "market_size"
        if any(k in lowered for k in ["비교기업", "유사기업", "comparables", "peer"]):
            return "comparables"
        if any(k in lowered for k in ["공모가", "공모가격", "per", "pbr", "psr", "ev/ebitda", "valuation", "밸류"]):
            return "valuation"
        if any(k in lowered for k in ["수요예측", "수요 예측"]):
            return "demand_forecast"
        if any(k in lowered for k in ["리스크", "위험", "불확실", "불확실성"]):
            return "risk"
        return None

    def _search_dart_evidence(self, query: str) -> List[Dict[str, Any]]:
        try:
            from agent.tools import execute_search_underwriter_opinion_similar, _resolve_underwriter_data_path
        except Exception:
            return []

        path, error = _resolve_underwriter_data_path(None)
        if error or not path:
            return []

        category = self._detect_dart_category(query)
        try:
            result = execute_search_underwriter_opinion_similar(
                query=query,
                category=category,
                top_k=3,
                max_chars=420,
                min_score=0.08,
                return_patterns=False,
            )
        except Exception:
            return []

        if not result.get("success"):
            return []

        evidence = []
        for item in result.get("results", []) or []:
            corp = item.get("corp_name", "미상")
            report = item.get("report_nm", "")
            title = item.get("section_title", "")
            snippet = (item.get("snippet") or "").strip()
            if not snippet:
                continue
            text = f"[DART] {corp} | {report} | {title} - {snippet}"
            evidence.append({
                "page": "DART",
                "text": text,
                "numbers": [],
            })
        return evidence

    def _build_recent_user_context(self, limit: int = 3) -> str:
        history = self.conversation_history[-12:]
        user_lines = []
        for msg in reversed(history):
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "")
            if not content:
                continue
            user_lines.append(content)
            if len(user_lines) >= limit:
                break
        user_lines = list(reversed(user_lines))
        if not user_lines:
            return ""
        return "최근 사용자 요청:\n" + "\n".join(user_lines)

    def _format_deep_opinion(self, result: Dict[str, Any]) -> str:
        lines = []
        conclusion = result.get("conclusion", {}).get("paragraphs", [])
        if conclusion:
            lines.append("결론")
            lines.extend(conclusion)
            lines.append("")

        def render_case(title: str, key: str) -> None:
            section = result.get(key, {})
            if not section:
                return
            lines.append(title)
            summary = section.get("summary")
            if summary:
                lines.append(f"- 요약: {summary}")
            for item in section.get("points", []):
                point = item.get("point", "")
                evidence = ", ".join(item.get("evidence", []) or [])
                suffix = f" (근거: {evidence})" if evidence else " (근거: 없음)"
                lines.append(f"- {point}{suffix}")
            lines.append("")

        render_case("핵심 관점", "core_case")
        render_case("반대 관점", "dissent_case")

        top_risks = result.get("top_risks", [])
        if top_risks:
            lines.append("주요 리스크")
            for item in top_risks:
                evidence = ", ".join(item.get("evidence", []) or [])
                severity = item.get("severity", "medium")
                verification = item.get("verification", "")
                label = f"[{severity}] {item.get('risk', '')}"
                suffix = f" · 검증: {verification}" if verification else ""
                if evidence:
                    suffix += f" · 근거: {evidence}"
                lines.append(f"- {label}{suffix}")
            lines.append("")

        hallucination = result.get("hallucination_check", {})
        if hallucination:
            lines.append("할루시네이션 검증")
            for item in hallucination.get("unverified_claims", []):
                lines.append(f"- 미검증 주장: {item.get('claim', '')} (사유: {item.get('reason', '')})")
            for item in hallucination.get("numeric_conflicts", []):
                lines.append(f"- 수치 충돌: {item}")
            for item in hallucination.get("evidence_gaps", []):
                lines.append(f"- 근거 공백: {item}")
            lines.append("")

        impact = result.get("impact_analysis", {})
        if impact:
            carbon = impact.get("carbon", {})
            lines.append("임팩트 분석")
            pathways = ", ".join(carbon.get("pathways", []) or [])
            if pathways:
                lines.append(f"- 탄소 경로: {pathways}")
            for metric in carbon.get("metrics", []):
                evidence = ", ".join(metric.get("evidence", []) or [])
                suffix = f" (근거: {evidence})" if evidence else ""
                lines.append(f"- {metric.get('metric', '')}: {metric.get('method', '')}{suffix}")
            for gap in carbon.get("gaps", []):
                lines.append(f"- 탄소 공백: {gap}")
            for item in impact.get("iris_plus", []):
                evidence = ", ".join(item.get("evidence", []) or [])
                suffix = f" (근거: {evidence})" if evidence else ""
                lines.append(
                    f"- IRIS+ {item.get('code', 'IRIS+')}: {item.get('name', '')} · {item.get('why', '')} "
                    f"· {item.get('measurement', '')}{suffix}"
                )
            lines.append("")

        data_gaps = result.get("data_gaps", [])
        if data_gaps:
            lines.append("데이터 공백")
            for item in data_gaps:
                lines.append(f"- {item}")
            lines.append("")

        deal_breakers = result.get("deal_breakers", [])
        go_conditions = result.get("go_conditions", [])
        if deal_breakers or go_conditions:
            lines.append("딜 브레이커 / GO 조건")
            if deal_breakers:
                for item in deal_breakers:
                    lines.append(f"- 딜 브레이커: {item}")
            if go_conditions:
                for item in go_conditions:
                    lines.append(f"- GO 조건: {item}")
            lines.append("")

        next_actions = result.get("next_actions", [])
        if next_actions:
            lines.append("다음 액션")
            for item in next_actions:
                lines.append(f"- {item.get('priority', 'P1')}: {item.get('action', '')}")

        return "\n".join(lines).strip()

    def _run_deep_report_pipeline(self, user_message: str) -> str:
        if not self.api_key:
            return "API 키가 없어 심화 의견을 생성할 수 없습니다."

        try:
            from shared.deep_opinion import (
                build_evidence_context,
                cross_examine_and_score,
                generate_hallucination_check,
                generate_impact_analysis,
                generate_lens_group,
                synthesize_deep_opinion,
            )
        except Exception as exc:
            logger.error(f"Deep opinion import failed: {exc}", exc_info=True)
            return "심화 의견 모듈을 불러오지 못했습니다."

        evidence = self._get_latest_report_evidence()
        dart_evidence = self._search_dart_evidence(user_message)
        if dart_evidence:
            merged_evidence = {"evidence": []}
            if isinstance(evidence, dict) and evidence.get("evidence"):
                merged_evidence["evidence"].extend(evidence.get("evidence", []))
            merged_evidence["evidence"].extend(dart_evidence)
            evidence_context = build_evidence_context(merged_evidence)
        else:
            evidence_context = build_evidence_context(evidence)
        extra_context = self._build_recent_user_context() or f"사용자 요청:\n{user_message}"
        if evidence_context.strip().lower() == "evidence: none":
            extra_context = (
                f"{extra_context}\n\n"
                "근거가 제공되지 않았습니다. 단정적 결론 대신 조건부 의견과 "
                "자료 요청 중심으로 작성하세요."
            )

        try:
            lens_outputs = generate_lens_group(
                api_key=self.api_key,
                evidence_context=evidence_context,
                extra_context=extra_context,
            )
            scoring = cross_examine_and_score(
                api_key=self.api_key,
                evidence_context=evidence_context,
                lens_outputs=lens_outputs,
            )
            hallucination = generate_hallucination_check(
                api_key=self.api_key,
                evidence_context=evidence_context,
                lens_outputs=lens_outputs,
            )
            impact = generate_impact_analysis(
                api_key=self.api_key,
                evidence_context=evidence_context,
                lens_outputs=lens_outputs,
            )
            final_result = synthesize_deep_opinion(
                api_key=self.api_key,
                evidence_context=evidence_context,
                lens_outputs=lens_outputs,
                scoring=scoring,
                hallucination=hallucination,
                impact=impact,
            )
        except Exception as exc:
            logger.error(f"Deep opinion pipeline failed: {exc}", exc_info=True)
            return "심화 의견 생성 중 오류가 발생했습니다. 다시 시도해 주세요."

        return self._format_deep_opinion(final_result)

    def _record_tool_usage(self, tool_name: str, tool_input: dict, tool_result: dict):
        """도구 사용 결과를 메모리/컨텍스트에 기록 (공통 헬퍼)"""
        # 메모리에 도구 사용 기록
        self.memory.add_message("tool", f"도구 사용: {tool_name}", {
            "tool_name": tool_name,
            "input": tool_input,
            "result": tool_result,
            "member": self.member_name or self.user_id,
            "team": self.team_id,
        })

        # 컨텍스트 업데이트 - 분석 파일
        if tool_name in ["analyze_excel", "read_excel_as_text", "analyze_company_diagnosis_sheet"]:
            if tool_result.get("success"):
                file_path = tool_input.get("excel_path")
                if file_path and file_path not in self.context["analyzed_files"]:
                    self.context["analyzed_files"].append(file_path)
                    self.memory.add_file_analysis(file_path)
                self.context["last_analysis"] = tool_result

        # 컨텍스트 업데이트 - PDF 분석
        if tool_name == "read_pdf_as_text":
            if tool_result.get("success"):
                file_path = tool_input.get("pdf_path")
                if file_path and file_path not in self.context["analyzed_files"]:
                    self.context["analyzed_files"].append(file_path)
                    self.memory.add_file_analysis(file_path)

        # 생성 파일 기록
        if tool_name in [
            "analyze_and_generate_projection",
            "generate_exit_projection",
            "generate_company_diagnosis_sheet_from_draft",
            "write_company_diagnosis_report",
        ]:
            if tool_result.get("success"):
                output_file = tool_result.get("output_file")
                if output_file:
                    self.memory.add_generated_file(output_file)

    def _recent_voice_conversation_text(self, limit: int = 8) -> str:
        items = self.voice_conversation_history[-limit:]
        lines = []
        for msg in items:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if not content:
                continue
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    @staticmethod
    def _extract_summary_json(text: str) -> Optional[Dict[str, Any]]:
        text = text.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    def summarize_checkin_sync(self, mode: str, context_text: str) -> Dict[str, Any]:
        """Summarize voice check-in context into a structured JSON payload."""
        conversation = self._recent_voice_conversation_text(limit=8)
        context_text = context_text or "none"

        system_prompt = """You produce a concise JSON summary for a daily check-in.
Return JSON only. Do not include markdown or extra text.
Use Korean for all string values.

Required keys:
- mode (string)
- yesterday_summary (string)
- learnings (array of strings)
- emotion_state (string)
- emotion_rationale (string)
- team_tasks (array of strings)
- today_priorities (array of strings)
- next_actions (array of strings)

If unknown, use empty string or empty array."""

        user_prompt = f"""Context:\n{context_text}\n\nConversation:\n{conversation}\n\nReturn JSON now."""

        response = self.client.messages.create(
            model=self.model,
            system=system_prompt,
            max_tokens=400,
            messages=[{"role": "user", "content": user_prompt}],
        )

        assistant_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                assistant_text += block.text

        parsed = self._extract_summary_json(assistant_text)
        if not isinstance(parsed, dict):
            return {
                "mode": mode,
                "yesterday_summary": "",
                "learnings": [],
                "emotion_state": "",
                "emotion_rationale": "",
                "team_tasks": [],
                "today_priorities": [],
                "next_actions": [],
            }

        parsed.setdefault("mode", mode)
        parsed.setdefault("learnings", [])
        parsed.setdefault("team_tasks", [])
        parsed.setdefault("today_priorities", [])
        parsed.setdefault("next_actions", [])
        return parsed

    def refine_voice_input_sync(self, transcript: str) -> str:
        """Clean ASR transcript into concise Korean text."""
        transcript = (transcript or "").strip()
        if not transcript:
            return ""

        system_prompt = """You are an ASR transcript cleaner.
Rules:
- Output only cleaned Korean text.
- Do not add new information.
- Fix spacing and punctuation.
- Keep numbers as written if unsure.
- No markdown."""

        response = self.client.messages.create(
            model=self.model,
            system=system_prompt,
            max_tokens=200,
            messages=[{"role": "user", "content": transcript}],
        )

        cleaned = ""
        for block in response.content:
            if hasattr(block, "text"):
                cleaned += block.text

        return cleaned.strip() or transcript

    # ========================================
    # Utility Methods
    # ========================================

    def chat_sync(
        self,
        user_message: str,
        mode: str = "exit",
        allow_tools: bool = True,
        context_text: Optional[str] = None,
        model_override: Optional[str] = None,
    ) -> str:
        """동기 버전 chat (간단한 사용)

        Args:
            user_message: 사용자 메시지
            mode: "exit" (Exit 프로젝션), "peer" (Peer PER 분석), "diagnosis", "report"

        Returns:
            에이전트 응답 문자열
        """
        import asyncio

        async def run():
            response = ""
            async for chunk in self.chat(
                user_message,
                mode=mode,
                allow_tools=allow_tools,
                context_text=context_text,
                model_override=model_override,
            ):
                response += chunk
            return response

        # Python 3.10+ compatible: asyncio.run() 사용
        # 단, 이미 실행 중인 이벤트 루프가 있으면 nest_asyncio 필요
        try:
            # 이미 실행 중인 루프가 있는지 확인
            loop = asyncio.get_running_loop()
            # 실행 중인 루프가 있으면 (예: Jupyter, Streamlit)
            # nest_asyncio 또는 새 스레드에서 실행
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, run())
                return future.result()
        except RuntimeError:
            # 실행 중인 루프가 없으면 asyncio.run() 사용
            return asyncio.run(run())

    def get_token_usage(self) -> Dict[str, Any]:
        """토큰 사용량 및 예상 비용 반환"""
        # Claude Opus 4.5 가격 (2024년 기준)
        INPUT_PRICE_PER_1M = 15.0   # $15 / 1M input tokens
        OUTPUT_PRICE_PER_1M = 75.0  # $75 / 1M output tokens

        input_cost = (self.token_usage["total_input_tokens"] / 1_000_000) * INPUT_PRICE_PER_1M
        output_cost = (self.token_usage["total_output_tokens"] / 1_000_000) * OUTPUT_PRICE_PER_1M
        total_cost = input_cost + output_cost

        return {
            "input_tokens": self.token_usage["total_input_tokens"],
            "output_tokens": self.token_usage["total_output_tokens"],
            "total_tokens": self.token_usage["total_input_tokens"] + self.token_usage["total_output_tokens"],
            "api_calls": self.token_usage["session_calls"],
            "estimated_cost_usd": round(total_cost, 4),
            "estimated_cost_krw": round(total_cost * 1400, 0)  # 대략적 환율
        }

    def reset_token_usage(self):
        """토큰 사용량 초기화"""
        self.token_usage = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "session_calls": 0
        }

    def reset(self):
        """세션 초기화"""
        self.conversation_history = []
        self.voice_conversation_history = []
        self.context = {
            "analyzed_files": [],
            "cached_results": {},
            "last_analysis": None
        }
        self.reset_token_usage()
