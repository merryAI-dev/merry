"""
Claude Vision PDF Processor

Claude Opus를 사용하여 PDF를 구조화된 데이터로 추출합니다.
Dolphin 대신 Claude Vision API를 기본으로 사용합니다.
"""

import base64
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
try:
    # Optional in minimal/runtime environments (e.g., worker containers).
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

# 프로젝트 루트의 .env 파일 로드 (절대 경로 사용)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if load_dotenv:
    load_dotenv(PROJECT_ROOT / ".env")

from .config import DOLPHIN_CONFIG
from . import classifier as doc_classifier
from . import chunker
from . import prompts as prompt_registry
from .strategy import get_strategy, ProcessingStrategy
from shared.training_logger import log_training_data

logger = logging.getLogger(__name__)


def _rows_to_markdown(rows: List[List]) -> str:
    """2D 리스트를 마크다운 테이블로 변환."""
    if not rows:
        return ""
    lines = []
    for i, row in enumerate(rows):
        cells = [str(c) if c is not None else "" for c in row]
        lines.append("| " + " | ".join(cells) + " |")
        if i == 0:
            lines.append("| " + " | ".join(["---"] * len(cells)) + " |")
    return "\n".join(lines)


def _llm_provider() -> str:
    return (os.getenv("LLM_PROVIDER", "anthropic") or "anthropic").strip().lower()


def _resolve_bedrock_model_id(model_hint: Optional[str]) -> str:
    """Resolve a Bedrock modelId from a model hint.

    - If model_hint already looks like a Bedrock modelId (anthropic.*), use it.
    - Otherwise, map common Anthropic name hints to env-configured Bedrock IDs.
    """
    hint = (model_hint or "").strip()
    if hint.startswith("anthropic."):
        return hint

    default = (os.getenv("BEDROCK_MODEL_ID") or "").strip()
    if not default:
        raise ValueError("Missing env BEDROCK_MODEL_ID (required when LLM_PROVIDER=bedrock)")

    if not hint:
        return default

    h = hint.lower()
    if "haiku" in h:
        return (os.getenv("BEDROCK_HAIKU_MODEL_ID") or default).strip()
    if "opus" in h:
        return (os.getenv("BEDROCK_OPUS_MODEL_ID") or default).strip()
    if "sonnet" in h:
        return (os.getenv("BEDROCK_SONNET_MODEL_ID") or default).strip()
    return default


def _extract_text_blocks(content: object) -> str:
    if not isinstance(content, list):
        return ""
    parts: List[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "\n".join(parts).strip()


def _normalize_usage(usage: object) -> Dict[str, int]:
    if not isinstance(usage, dict):
        return {}
    in_tok = usage.get("input_tokens") if isinstance(usage.get("input_tokens"), int) else usage.get("inputTokens")
    out_tok = usage.get("output_tokens") if isinstance(usage.get("output_tokens"), int) else usage.get("outputTokens")
    out: Dict[str, int] = {}
    if isinstance(in_tok, int):
        out["input_tokens"] = int(in_tok)
    if isinstance(out_tok, int):
        out["output_tokens"] = int(out_tok)
    return out


def _invoke_bedrock_anthropic_messages(
    *,
    model_id: str,
    system_prompt: str,
    content_blocks: List[Dict[str, Any]],
    max_tokens: int,
    temperature: float,
    timeout_seconds: int,
) -> tuple[str, Dict[str, int], str]:
    import boto3
    from botocore.config import Config

    region = (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-northeast-2").strip()
    client = boto3.client(
        "bedrock-runtime",
        region_name=region,
        config=Config(connect_timeout=30, read_timeout=timeout_seconds, retries={"max_attempts": 4}),
    )

    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_prompt,
        "messages": [{"role": "user", "content": content_blocks}],
    }

    resp = client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(payload).encode("utf-8"),
    )
    raw = resp.get("body").read()
    parsed = json.loads(raw)

    text = _extract_text_blocks(parsed.get("content"))
    usage = _normalize_usage(parsed.get("usage"))
    return text, usage, model_id

# 캐시 디렉토리
CACHE_DIR = Path(os.getenv("PDF_CACHE_DIR", "/tmp/claude_pdf_cache"))


def _get_cache_path(pdf_path: str, max_pages: int, output_mode: str) -> Path:
    """캐시 파일 경로 생성"""
    # 파일 해시 생성
    file_stat = Path(pdf_path).stat()
    cache_key = f"{pdf_path}:{file_stat.st_size}:{file_stat.st_mtime}:{max_pages}:{output_mode}"
    hash_key = hashlib.md5(cache_key.encode()).hexdigest()
    return CACHE_DIR / f"{hash_key}.json"


def _get_cached_result(cache_path: Path) -> Optional[Dict[str, Any]]:
    """캐시된 결과 조회"""
    if not DOLPHIN_CONFIG.get("cache_enabled", True):
        return None

    if not cache_path.exists():
        return None

    try:
        # TTL 체크
        ttl_days = DOLPHIN_CONFIG.get("cache_ttl_days", 7)
        file_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
        if file_age > timedelta(days=ttl_days):
            cache_path.unlink()  # 만료된 캐시 삭제
            return None

        with open(cache_path, "r", encoding="utf-8") as f:
            result = json.load(f)
            result["cache_hit"] = True
            return result
    except Exception as e:
        logger.warning(f"캐시 읽기 실패: {e}")
        return None


def _save_to_cache(cache_path: Path, result: Dict[str, Any]) -> None:
    """결과를 캐시에 저장"""
    if not DOLPHIN_CONFIG.get("cache_enabled", True):
        return

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"캐시 저장 실패: {e}")


class ClaudeVisionProcessor:
    """Claude Vision 기반 PDF 처리기

    - PDF → 이미지 변환
    - Claude Opus Vision으로 구조화된 데이터 추출
    - 테이블, 재무제표 자동 인식
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key

    def process_pdf(
        self,
        pdf_path: str,
        max_pages: int = None,
        output_mode: str = "structured",
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """PDF 파일을 분류 후 최적 전략으로 처리

        Args:
            pdf_path: PDF 파일 경로
            max_pages: 최대 처리 페이지 수
            output_mode: 출력 모드 (text_only, structured, tables_only)
            progress_callback: 진행 상황 콜백 함수

        Returns:
            처리 결과 딕셔너리
        """
        start_time = time.time()
        max_pages = max_pages or DOLPHIN_CONFIG["default_max_pages"]

        # 캐시 확인
        cache_path = _get_cache_path(pdf_path, max_pages, output_mode)
        cached = _get_cached_result(cache_path)
        if cached:
            self._emit_progress(progress_callback, "complete", "캐시에서 로드됨")
            return cached

        self._emit_progress(progress_callback, "loading", "PDF 로딩 중...")

        try:
            # 1. 문서 분류
            self._emit_progress(progress_callback, "classifying", "문서 유형 분류 중...")
            classification = doc_classifier.classify_document(pdf_path)
            strategy = get_strategy(classification.doc_type)

            logger.info(
                f"문서 분류: {classification.doc_type.value}, "
                f"전략: vision={strategy.use_vision}, model={strategy.model}"
            )

            # 2. 전략에 따라 분기
            if not strategy.use_vision:
                # PyMuPDF 직접 처리 (PURE_TEXT, TEXT_WITH_TABLES, SMALL_TABLE)
                self._emit_progress(
                    progress_callback,
                    "processing",
                    f"PyMuPDF로 {classification.total_pages}페이지 텍스트 추출 중...",
                )
                result = self._process_with_pymupdf(pdf_path, classification)
            else:
                # Vision API 처리
                self._emit_progress(
                    progress_callback,
                    "converting",
                    f"PDF를 이미지로 변환 중 (DPI={strategy.dpi})...",
                )
                images_base64, total_pages = self._pdf_to_base64_images(
                    pdf_path, max_pages, dpi_override=strategy.dpi
                )

                if not images_base64:
                    return {
                        "success": False,
                        "error": "PDF에서 이미지를 추출할 수 없습니다",
                    }

                # 스마트 청킹
                chunks = chunker.create_chunks(images_base64, strategy)
                self._emit_progress(
                    progress_callback,
                    "processing",
                    f"{strategy.model}로 {len(images_base64)}페이지 분석 중 "
                    f"({len(chunks)}청크)...",
                )

                if len(chunks) == 1:
                    # 단일 청크: 기존 방식
                    result = self._process_with_claude(
                        chunks[0], output_mode, progress_callback,
                        model_override=strategy.model,
                        prompt_type=strategy.prompt_type,
                        max_tokens_override=strategy.max_tokens,
                    )
                else:
                    # 다중 청크: 병렬 처리
                    result = self._process_chunks_parallel(
                        chunks, output_mode, progress_callback,
                        strategy=strategy,
                    )

            # 3. 결과 조합
            processing_time = time.time() - start_time

            total_pages = classification.total_pages
            pages_read = min(total_pages, max_pages)

            final_result = {
                "success": True,
                "file_path": pdf_path,
                "total_pages": total_pages,
                "pages_read": pages_read,
                "content": result.get("content", ""),
                "char_count": len(result.get("content", "")),
                "structured_content": result.get("structured_content", {}),
                "financial_tables": result.get("financial_tables", {}),
                "usage": result.get("usage", {}),
                "model": result.get("model", strategy.model),
                "provider": result.get("provider", _llm_provider() if strategy.use_vision else "pymupdf"),
                "doc_type": classification.doc_type.value,
                "processing_method": (
                    "pymupdf_direct" if not strategy.use_vision
                    else f"vision_{strategy.model or 'unknown'}"
                ),
                "processing_time_seconds": processing_time,
                "cache_hit": False,
                "cached_at": datetime.utcnow().isoformat(),
            }

            # 캐시에 저장
            _save_to_cache(cache_path, final_result)

            self._emit_progress(
                progress_callback,
                "complete",
                f"완료 ({processing_time:.1f}초)",
                {"duration": processing_time},
            )

            return final_result

        except Exception as e:
            logger.error(f"Claude Vision 처리 실패: {e}", exc_info=True)
            return self._fallback_to_pymupdf(pdf_path, max_pages, str(e))

    def _pdf_to_base64_images(
        self, pdf_path: str, max_pages: int, dpi_override: int = 0
    ) -> tuple:
        """PDF를 base64 인코딩된 이미지 리스트로 변환

        Args:
            pdf_path: PDF 파일 경로
            max_pages: 최대 페이지 수
            dpi_override: 0이면 config 기본값, >0이면 해당 DPI 사용

        Returns:
            (images_base64: List[str], total_pages: int)
        """
        try:
            import fitz  # PyMuPDF
        except ImportError as e:
            raise ImportError(f"PDF 변환에 PyMuPDF가 필요합니다: {e}")

        doc = None
        images_base64 = []

        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            pages_to_read = min(total_pages, max_pages)

            dpi = dpi_override if dpi_override > 0 else DOLPHIN_CONFIG.get("image_dpi", 150)
            zoom = dpi / 72

            for i in range(pages_to_read):
                page = doc[i]
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)

                # PNG로 변환 후 base64 인코딩
                img_bytes = pix.tobytes("png")
                img_base64 = base64.standard_b64encode(img_bytes).decode("utf-8")
                images_base64.append(img_base64)

            return images_base64, total_pages

        finally:
            if doc:
                doc.close()

    def _get_system_prompt(self) -> str:
        """VC 투자 분석 전문가 시스템 프롬프트 (하위 호환성)."""
        return prompt_registry.FINANCIAL_SYSTEM

    def _process_with_claude(
        self,
        images_base64: List[str],
        output_mode: str,
        progress_callback: Optional[Callable] = None,
        model_override: Optional[str] = None,
        prompt_type: str = "financial_structured",
        max_tokens_override: int = 0,
        page_offset: int = 0,
    ) -> Dict[str, Any]:
        """Claude Vision API로 이미지 처리

        Args:
            images_base64: base64 인코딩된 이미지 리스트
            output_mode: 출력 모드
            progress_callback: 진행 콜백
            model_override: 모델 오버라이드 (None이면 기본 Sonnet)
            prompt_type: prompts.py 키
            max_tokens_override: max_tokens 오버라이드 (0이면 기본값)
            page_offset: 청크의 시작 페이지 번호 (페이지 라벨에 사용)
        """
        timeout_seconds = int(DOLPHIN_CONFIG.get("timeout_seconds", 300))
        provider = _llm_provider()

        # 프롬프트 구성 (prompts.py 레지스트리 사용)
        system_prompt, user_prompt = prompt_registry.get_prompts(
            prompt_type,
            output_mode=output_mode,
            page_count=len(images_base64) or 1,
        )

        # 이미지 콘텐츠 구성
        content = []
        for i, img_b64 in enumerate(images_base64):
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_b64,
                },
            })
            content.append({
                "type": "text",
                "text": f"[페이지 {page_offset + i + 1}]"
            })

        content.append({
            "type": "text",
            "text": user_prompt
        })

        model = model_override or "claude-sonnet-4-5-20250929"
        max_tokens = max_tokens_override if max_tokens_override > 0 else 16384

        if provider == "bedrock":
            model_id = _resolve_bedrock_model_id(model)
            response_text, usage, used_model_id = _invoke_bedrock_anthropic_messages(
                model_id=model_id,
                system_prompt=system_prompt,
                content_blocks=content,
                max_tokens=max_tokens,
                temperature=0,
                timeout_seconds=timeout_seconds,
            )
            parsed = self._parse_claude_response(response_text, output_mode)
            parsed["provider"] = "bedrock"
            parsed["model"] = used_model_id
            if usage:
                parsed["usage"] = usage
            return parsed

        # Anthropic direct API (fallback / legacy).
        import httpx
        import anthropic

        timeout_config = httpx.Timeout(timeout=timeout_seconds, connect=30.0)
        client = anthropic.Anthropic(timeout=timeout_config)

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": content}],
        )

        response_text = response.content[0].text if response.content else ""
        parsed = self._parse_claude_response(response_text, output_mode)
        parsed["provider"] = "anthropic"
        parsed["model"] = model
        usage = _normalize_usage(getattr(response, "usage", {}) or {})
        if usage:
            parsed["usage"] = usage
        return parsed

    def _process_chunks_parallel(
        self,
        chunks: List[List[str]],
        output_mode: str,
        progress_callback: Optional[Callable] = None,
        strategy: Optional[ProcessingStrategy] = None,
    ) -> Dict[str, Any]:
        """다중 청크를 병렬로 처리 후 결과 병합."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        page_offsets = chunker.compute_page_offsets(chunks)
        chunk_results: List[Optional[Dict[str, Any]]] = [None] * len(chunks)

        def process_chunk(idx: int) -> Dict[str, Any]:
            return self._process_with_claude(
                chunks[idx],
                output_mode,
                progress_callback=None,  # 청크별 콜백 비활성화
                model_override=strategy.model if strategy else None,
                prompt_type=strategy.prompt_type if strategy else "financial_structured",
                max_tokens_override=strategy.max_tokens if strategy else 0,
                page_offset=page_offsets[idx],
            )

        completed = 0
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(process_chunk, i): i for i in range(len(chunks))}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    chunk_results[idx] = future.result()
                except Exception as e:
                    logger.error(f"청크 {idx} 처리 실패: {e}")
                    chunk_results[idx] = {"content": "", "error": str(e)}
                completed += 1
                self._emit_progress(
                    progress_callback,
                    "processing",
                    f"청크 {completed}/{len(chunks)} 완료",
                )

        # None 제거 및 병합
        valid_results = [r for r in chunk_results if r is not None]
        return chunker.merge_chunk_results(valid_results, page_offsets)

    def _process_with_pymupdf(
        self,
        pdf_path: str,
        classification: doc_classifier.ClassificationResult,
    ) -> Dict[str, Any]:
        """Vision API 없이 PyMuPDF만으로 처리 (PURE_TEXT, TEXT_WITH_TABLES, SMALL_TABLE)."""
        import fitz

        doc = fitz.open(pdf_path)
        try:
            text_parts: List[str] = []
            pages: List[Dict[str, Any]] = []
            all_tables: List[Dict[str, Any]] = []

            for i in range(len(doc)):
                page = doc[i]
                text = page.get_text("text")
                text_parts.append(
                    f"\n{'='*60}\n페이지 {i+1}\n{'='*60}\n{text}"
                )

                page_data: Dict[str, Any] = {
                    "page_num": i + 1,
                    "elements": [{"type": "text", "content": text}],
                }

                # PyMuPDF 테이블 감지
                try:
                    found_tables = page.find_tables()
                    for t in found_tables.tables:
                        rows = t.extract()
                        table_entry = {
                            "type": "table",
                            "content": {
                                "rows": rows,
                                "markdown": _rows_to_markdown(rows),
                            },
                        }
                        page_data["elements"].append(table_entry)
                        all_tables.append({
                            "page": i + 1,
                            "content": table_entry["content"],
                        })
                except Exception:
                    pass

                pages.append(page_data)

            content = "".join(text_parts)

            return {
                "content": content,
                "structured_content": {"pages": pages},
                "financial_tables": {},  # table_extractor가 나중에 처리
            }
        finally:
            doc.close()

    def _parse_claude_response(
        self, response_text: str, output_mode: str
    ) -> Dict[str, Any]:
        """Claude 응답 파싱"""
        import json
        import re

        if output_mode == "text_only":
            return {"content": response_text}

        # JSON 추출 시도
        try:
            # ```json ... ``` 블록 추출
            json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 전체가 JSON인 경우
                json_str = response_text.strip()

            parsed = json.loads(json_str)

            return {
                "content": parsed.get("content", response_text),
                "structured_content": parsed.get("structured_content", {}),
                "financial_tables": parsed.get("financial_tables", {}),
            }

        except json.JSONDecodeError:
            logger.warning("JSON 파싱 실패, 텍스트로 반환")
            return {"content": response_text}

    def _fallback_to_pymupdf(
        self, pdf_path: str, max_pages: int, reason: str
    ) -> Dict[str, Any]:
        """PyMuPDF로 폴백"""
        logger.info(f"PyMuPDF로 폴백: {reason}")

        try:
            import fitz

            doc = None
            try:
                doc = fitz.open(pdf_path)
                total_pages = len(doc)
                pages_to_read = min(total_pages, max_pages)

                text_content = []
                for i in range(pages_to_read):
                    page = doc[i]
                    text = page.get_text()
                    text_content.append(
                        f"\n{'='*60}\n페이지 {i+1}\n{'='*60}\n{text}"
                    )

                content = "".join(text_content)

                return {
                    "success": True,
                    "file_path": pdf_path,
                    "total_pages": total_pages,
                    "pages_read": pages_to_read,
                    "content": content,
                    "char_count": len(content),
                    "processing_method": "pymupdf_fallback",
                    "fallback_used": True,
                    "fallback_reason": reason,
                    "cache_hit": False,
                    "cached_at": datetime.utcnow().isoformat(),
                }

            finally:
                if doc:
                    doc.close()

        except Exception as e:
            logger.error(f"폴백 처리도 실패: {e}")
            return {
                "success": False,
                "error": f"PDF 처리 실패: {str(e)}",
                "fallback_attempted": True,
                "original_error": reason,
            }

    def _emit_progress(
        self,
        callback: Optional[Callable],
        stage: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """진행 상황 이벤트 발생"""
        if callback:
            event = {
                "type": "info",
                "content": message,
                "data": {"stage": stage, **(data or {})},
            }
            try:
                callback(event)
            except Exception as e:
                logger.warning(f"진행 콜백 실패: {e}")


# 기존 DolphinProcessor를 ClaudeVisionProcessor로 대체
DolphinProcessor = ClaudeVisionProcessor


@log_training_data(task_type="pdf_extraction", model_name="claude-sonnet-4-5-20250929")
def process_pdf_with_claude(
    pdf_path: str,
    max_pages: int = None,
    output_mode: str = "structured",
    progress_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
    """PDF를 Claude Vision으로 처리하는 편의 함수"""
    processor = ClaudeVisionProcessor()
    return processor.process_pdf(
        pdf_path=pdf_path,
        max_pages=max_pages,
        output_mode=output_mode,
        progress_callback=progress_callback,
    )


# 하위 호환성을 위한 별칭
process_pdf_with_dolphin = process_pdf_with_claude


class InteractiveAnalysisSession:
    """대화형 투자 분석 세션

    여러 파일과 텍스트 입력을 받아서 점진적으로 분석을 완성합니다.
    """

    def __init__(self, session_id: str = None):
        self.session_id = session_id or datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self.processor = ClaudeVisionProcessor()
        self.accumulated_data = {
            "company_info": {},
            "investment_terms": {"found": False},
            "financial_tables": {
                "income_statement": {"found": False},
                "balance_sheet": {"found": False},
                "cash_flow": {"found": False},
                "cap_table": {"found": False},
            },
            "valuation_metrics": {},
            "source_files": [],
            "text_inputs": [],
        }
        self.missing_data = []

    def add_pdf(self, pdf_path: str, max_pages: int = 30) -> Dict[str, Any]:
        """PDF 파일 추가 및 분석"""
        result = self.processor.process_pdf(
            pdf_path=pdf_path,
            max_pages=max_pages,
            output_mode="structured",
        )

        if result.get("success"):
            self._merge_data(result)
            self.accumulated_data["source_files"].append(pdf_path)

        return self._get_status()

    def add_text_input(self, text: str, data_type: str = "general") -> Dict[str, Any]:
        """텍스트 입력 추가 (재무 데이터, Cap Table 등)

        Args:
            text: 사용자가 입력한 텍스트
            data_type: "financial", "cap_table", "investment_terms", "general"
        """
        import json
        import re

        try:
            prompt = self._get_text_parsing_prompt(text, data_type)

            provider = _llm_provider()
            if provider == "bedrock":
                # Prefer a cheaper model when available.
                model_hint = os.getenv("DOLPHIN_TEXT_MODEL") or "claude-haiku-4-5-20251001"
                model_id = _resolve_bedrock_model_id(model_hint)
                response_text, _, _ = _invoke_bedrock_anthropic_messages(
                    model_id=model_id,
                    system_prompt=self.processor._get_system_prompt(),
                    content_blocks=[{"type": "text", "text": prompt}],
                    max_tokens=4096,
                    temperature=0,
                    timeout_seconds=int(DOLPHIN_CONFIG.get("timeout_seconds", 300)),
                )
            else:
                import anthropic

                client = anthropic.Anthropic()
                response = client.messages.create(
                    model="claude-haiku-4-5-20251001",  # 텍스트 파싱은 Haiku로 충분 (비용 95% 절감)
                    max_tokens=4096,
                    system=[
                        {
                            "type": "text",
                            "text": self.processor._get_system_prompt(),
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=[{"role": "user", "content": prompt}],
                )
                response_text = response.content[0].text

            json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(1))
            else:
                parsed = json.loads(response_text.strip())

            self._merge_parsed_text(parsed, data_type)
            self.accumulated_data["text_inputs"].append({
                "type": data_type,
                "content": text[:500],  # 요약 저장
            })

        except json.JSONDecodeError as e:
            logger.warning(f"JSON 파싱 실패: {e}")
            return {
                "success": False,
                "error": "응답 파싱에 실패했습니다. 다시 시도해주세요.",
            }
        except Exception as e:
            # Keep error messaging user-friendly; specific SDK exceptions differ by provider.
            msg = str(e) or type(e).__name__
            if "Rate" in msg and "limit" in msg.lower():
                logger.error(f"Rate limit: {e}")
                return {"success": False, "error": "API 호출 한도에 도달했습니다. 잠시 후 다시 시도해주세요."}
            if "connect" in msg.lower():
                logger.error(f"API 연결 실패: {e}")
                return {"success": False, "error": "API 연결에 실패했습니다. 네트워크를 확인해주세요."}
            logger.exception("텍스트 입력 처리 실패")
            return {"success": False, "error": f"처리 실패: {msg}"}

        return self._get_status()

    def _get_text_parsing_prompt(self, text: str, data_type: str) -> str:
        """텍스트 파싱용 프롬프트 생성"""
        base_prompt = f"""다음 텍스트에서 투자 분석에 필요한 정보를 추출해주세요.

텍스트:
{text}

"""
        if data_type == "financial":
            base_prompt += """
재무 정보를 다음 JSON 형식으로 추출:
```json
{
  "income_statement": {
    "found": true,
    "years": ["2023", "2024E"],
    "metrics": {
      "revenue": [값들],
      "operating_income": [값들],
      "net_income": [값들]
    }
  }
}
```"""
        elif data_type == "cap_table":
            base_prompt += """
Cap Table을 다음 JSON 형식으로 추출:
```json
{
  "cap_table": {
    "found": true,
    "total_shares_issued": 총주식수,
    "shareholders": [
      {"name": "주주명", "shares": 주식수, "percentage": 지분율}
    ]
  }
}
```"""
        elif data_type == "investment_terms":
            base_prompt += """
투자 조건을 다음 JSON 형식으로 추출:
```json
{
  "investment_terms": {
    "found": true,
    "investment_amount": 투자금액,
    "pre_money_valuation": Pre-money,
    "price_per_share": 주당가격,
    "investment_type": "보통주/우선주/CB"
  }
}
```"""
        else:
            base_prompt += """
관련 정보를 JSON 형식으로 추출해주세요.
```json
{
  "extracted_info": {...}
}
```"""

        return base_prompt

    def _merge_data(self, new_data: Dict[str, Any]) -> None:
        """새로운 데이터를 기존 데이터와 병합"""
        # 회사 정보
        if new_data.get("company_info"):
            self.accumulated_data["company_info"].update(new_data["company_info"])

        # 투자 조건
        if new_data.get("investment_terms", {}).get("found"):
            self.accumulated_data["investment_terms"] = new_data["investment_terms"]

        # 재무 테이블
        financial = new_data.get("financial_tables", {})
        for table_type in ["income_statement", "balance_sheet", "cash_flow", "cap_table"]:
            if financial.get(table_type, {}).get("found"):
                self.accumulated_data["financial_tables"][table_type] = financial[table_type]

        # 밸류에이션 지표
        if new_data.get("valuation_metrics"):
            self.accumulated_data["valuation_metrics"].update(new_data["valuation_metrics"])

    def _merge_parsed_text(self, parsed: Dict[str, Any], data_type: str) -> None:
        """파싱된 텍스트 데이터 병합"""
        if data_type == "financial" and parsed.get("income_statement"):
            self.accumulated_data["financial_tables"]["income_statement"] = parsed["income_statement"]
        elif data_type == "cap_table" and parsed.get("cap_table"):
            self.accumulated_data["financial_tables"]["cap_table"] = parsed["cap_table"]
        elif data_type == "investment_terms" and parsed.get("investment_terms"):
            self.accumulated_data["investment_terms"] = parsed["investment_terms"]

    def _get_status(self) -> Dict[str, Any]:
        """현재 분석 상태 반환"""
        missing = []
        critical_missing = []

        # 필수 데이터 체크
        if not self.accumulated_data["financial_tables"]["income_statement"].get("found"):
            critical_missing.append({
                "field": "income_statement",
                "name": "손익계산서",
                "suggestion": "재무제표 PDF를 업로드하거나, 매출/영업이익/순이익을 텍스트로 입력해주세요.\n예: '2024년 매출 100억, 영업이익 20억, 순이익 15억'",
            })

        if not self.accumulated_data["financial_tables"]["cap_table"].get("found"):
            critical_missing.append({
                "field": "cap_table",
                "name": "Cap Table (주주현황)",
                "suggestion": "Cap Table을 업로드하거나, 주주현황을 텍스트로 입력해주세요.\n예: '대표이사 60%, 투자자A 20%, 스톡옵션풀 20%'",
            })

        if not self.accumulated_data["investment_terms"].get("found"):
            missing.append({
                "field": "investment_terms",
                "name": "투자 조건",
                "suggestion": "투자금액, 밸류에이션, 주당가격 등을 입력해주세요.\n예: '투자금액 30억, Pre-money 100억, 주당가격 10,000원'",
            })

        # 상태 메시지 생성
        if critical_missing:
            status = "incomplete"
            message = "🔴 필수 데이터가 부족합니다:\n"
            for item in critical_missing:
                message += f"\n**{item['name']}**\n{item['suggestion']}\n"
        elif missing:
            status = "partial"
            message = "🟡 추가 데이터가 있으면 더 정확한 분석이 가능합니다:\n"
            for item in missing:
                message += f"\n**{item['name']}**\n{item['suggestion']}\n"
        else:
            status = "complete"
            message = "🟢 모든 필수 데이터가 수집되었습니다. 분석 가능합니다."

        return {
            "success": True,
            "session_id": self.session_id,
            "status": status,
            "message": message,
            "critical_missing": critical_missing,
            "optional_missing": missing,
            "accumulated_data": self.accumulated_data,
            "source_count": {
                "files": len(self.accumulated_data["source_files"]),
                "text_inputs": len(self.accumulated_data["text_inputs"]),
            },
        }

    def get_final_analysis(self) -> Dict[str, Any]:
        """최종 분석 결과 반환"""
        status = self._get_status()

        if status["status"] == "incomplete":
            return {
                "success": False,
                "error": "필수 데이터가 부족합니다",
                "missing": status["critical_missing"],
                "message": status["message"],
            }

        return {
            "success": True,
            "session_id": self.session_id,
            "analysis": self.accumulated_data,
            "data_quality": "complete" if status["status"] == "complete" else "partial",
            "warnings": status.get("optional_missing", []),
        }


# 세션 관리
_active_sessions: Dict[str, InteractiveAnalysisSession] = {}


def get_or_create_session(session_id: str = None) -> InteractiveAnalysisSession:
    """분석 세션 가져오기 또는 생성"""
    if session_id and session_id in _active_sessions:
        return _active_sessions[session_id]

    session = InteractiveAnalysisSession(session_id)
    _active_sessions[session.session_id] = session
    return session


def clear_session(session_id: str) -> None:
    """세션 삭제"""
    if session_id in _active_sessions:
        del _active_sessions[session_id]
