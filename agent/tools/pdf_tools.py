"""
PDF parsing tools.

Claude Vision primary processing with PyMuPDF fallback.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from ._common import (
    CACHE_VERSION,
    _validate_file_path,
    compute_file_hash,
    compute_payload_hash,
    get_cache_dir,
    load_json,
    logger,
    save_json,
)

TOOLS = [
    {
        "name": "read_pdf_as_text",
        "description": "PDF 파일(기업 소개서, IR 자료, 사업계획서 등)을 Claude Vision으로 분석합니다. 테이블 구조를 보존하고 재무제표를 자동으로 추출합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pdf_path": {
                    "type": "string",
                    "description": "읽을 PDF 파일 경로",
                },
                "max_pages": {
                    "type": "integer",
                    "description": "읽을 최대 페이지 수 (기본값: 30)",
                },
                "output_mode": {
                    "type": "string",
                    "enum": ["text_only", "structured", "tables_only"],
                    "description": "출력 모드 (text_only: 텍스트만, structured: 전체 구조+재무제표, tables_only: 테이블만)",
                },
                "extract_financial_tables": {
                    "type": "boolean",
                    "description": "재무제표 테이블 자동 추출 여부 (IS/BS/CF)",
                },
            },
            "required": ["pdf_path"],
        },
    },
    {
        "name": "parse_pdf_dolphin",
        "description": "Claude Vision을 사용하여 PDF를 구조화된 형태로 파싱합니다. 테이블, 재무제표, Cap Table을 자동 인식합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pdf_path": {
                    "type": "string",
                    "description": "분석할 PDF 파일 경로",
                },
                "max_pages": {
                    "type": "integer",
                    "description": "분석할 최대 페이지 수 (기본값: 30)",
                },
                "output_mode": {
                    "type": "string",
                    "enum": ["text_only", "structured", "tables_only"],
                    "description": "출력 모드",
                },
                "extract_financial_tables": {
                    "type": "boolean",
                    "description": "재무제표 테이블 자동 추출 여부 (기본값: true)",
                },
            },
            "required": ["pdf_path"],
        },
    },
    {
        "name": "extract_pdf_tables",
        "description": "PDF에서 테이블만 추출합니다. 재무제표(IS/BS/CF), Cap Table 등을 구조화된 데이터로 반환합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pdf_path": {
                    "type": "string",
                    "description": "PDF 파일 경로",
                },
                "max_pages": {
                    "type": "integer",
                    "description": "처리할 최대 페이지 수 (기본값: 50)",
                },
            },
            "required": ["pdf_path"],
        },
    },
]


def _execute_read_pdf_as_text_pymupdf(
    pdf_path: str, max_pages: int = 30, cache_path: Path = None
) -> Dict[str, Any]:
    """PyMuPDF를 사용한 기존 PDF 텍스트 추출 (폴백용)"""
    import fitz  # PyMuPDF

    doc = None
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        pages_to_read = min(total_pages, max_pages)

        text_content = []

        for page_num in range(pages_to_read):
            page = doc[page_num]
            text = page.get_text()

            if text.strip():
                text_content.append(f"\n{'='*60}")
                text_content.append(f"페이지 {page_num + 1}")
                text_content.append(f"{'='*60}")
                text_content.append(text)

        full_text = "\n".join(text_content)

        logger.info(
            f"PDF read with PyMuPDF (fallback): {pdf_path} ({pages_to_read}/{total_pages} pages)"
        )
        result = {
            "success": True,
            "file_path": pdf_path,
            "total_pages": total_pages,
            "pages_read": pages_to_read,
            "content": full_text,
            "char_count": len(full_text),
            "processing_method": "pymupdf_fallback",
            "fallback_used": True,
            "cache_hit": False,
            "cached_at": datetime.utcnow().isoformat(),
        }
        if cache_path:
            save_json(cache_path, result)
        return result

    except FileNotFoundError:
        return {"success": False, "error": f"파일을 찾을 수 없습니다: {pdf_path}"}
    except PermissionError:
        return {"success": False, "error": f"파일 접근 권한이 없습니다: {pdf_path}"}
    except Exception as e:
        logger.error(f"Failed to read PDF {pdf_path}: {e}", exc_info=True)
        return {"success": False, "error": f"PDF 파일 읽기 실패: {str(e)}"}
    finally:
        if doc is not None:
            doc.close()


def execute_read_pdf_as_text(
    pdf_path: str,
    max_pages: int = 30,
    output_mode: str = "structured",
    extract_financial_tables: bool = True,
) -> Dict[str, Any]:
    """PDF 파일을 Claude Vision으로 파싱하여 읽기

    Claude Vision 사용 불가 시 PyMuPDF로 자동 폴백합니다.
    """
    is_valid, error = _validate_file_path(
        pdf_path, allowed_extensions=[".pdf"], require_temp_dir=True
    )
    if not is_valid:
        return {"success": False, "error": error}

    if not os.path.exists(pdf_path):
        return {"success": False, "error": f"파일을 찾을 수 없습니다: {pdf_path}"}

    # 캐시 확인
    try:
        file_hash = compute_file_hash(Path(pdf_path))
        payload = {
            "version": CACHE_VERSION,
            "file_hash": file_hash,
            "max_pages": max_pages,
            "output_mode": output_mode,
            "extract_financial_tables": extract_financial_tables,
            "tool": "read_pdf_as_text_dolphin",
        }
        cache_key = compute_payload_hash(payload)
        cache_dir = get_cache_dir("dolphin_pdf", "shared")
        cache_path = cache_dir / f"{cache_key}.json"
        cached = load_json(cache_path)
        if cached:
            cached["cache_hit"] = True
            logger.info(f"Cache hit for PDF: {pdf_path}")
            return cached
    except Exception:
        cache_path = None

    # Claude Vision으로 처리 시도
    try:
        from dolphin_service.processor import ClaudeVisionProcessor

        processor = ClaudeVisionProcessor()
        result = processor.process_pdf(
            pdf_path=pdf_path,
            max_pages=max_pages,
            output_mode=output_mode,
        )

        if cache_path and result.get("success"):
            save_json(cache_path, result)

        logger.info(f"PDF processed with Claude Vision: {pdf_path}")
        return result

    except ImportError as e:
        logger.warning(f"Claude Vision 모듈 로드 실패, PyMuPDF로 폴백: {e}")
        return _execute_read_pdf_as_text_pymupdf(pdf_path, max_pages, cache_path)

    except Exception as e:
        logger.warning(f"Claude Vision 처리 실패, PyMuPDF로 폴백: {e}")
        return _execute_read_pdf_as_text_pymupdf(pdf_path, max_pages, cache_path)


def execute_parse_pdf_dolphin(
    pdf_path: str,
    max_pages: int = 30,
    output_mode: str = "structured",
    extract_financial_tables: bool = True,
) -> Dict[str, Any]:
    """Claude Vision으로 PDF 파싱 (전용 도구)"""
    return execute_read_pdf_as_text(
        pdf_path=pdf_path,
        max_pages=max_pages,
        output_mode=output_mode,
        extract_financial_tables=extract_financial_tables,
    )


def execute_extract_pdf_tables(
    pdf_path: str, max_pages: int = 50
) -> Dict[str, Any]:
    """PDF에서 테이블만 추출"""
    result = execute_read_pdf_as_text(
        pdf_path=pdf_path,
        max_pages=max_pages,
        output_mode="tables_only",
        extract_financial_tables=True,
    )

    if not result.get("success"):
        return result

    return {
        "success": True,
        "file_path": pdf_path,
        "total_pages": result.get("total_pages", 0),
        "financial_tables": result.get("financial_tables", {}),
        "structured_content": result.get("structured_content", {}),
        "processing_method": result.get("processing_method", "unknown"),
        "cache_hit": result.get("cache_hit", False),
    }


EXECUTORS = {
    "read_pdf_as_text": execute_read_pdf_as_text,
    "parse_pdf_dolphin": execute_parse_pdf_dolphin,
    "extract_pdf_tables": execute_extract_pdf_tables,
}
