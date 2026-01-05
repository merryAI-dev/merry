"""
Output Converter

Dolphin 출력을 다양한 형식으로 변환합니다.
- 레거시 호환 텍스트 형식
- 구조화된 JSON 형식
- Markdown 형식
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OutputConverter:
    """Dolphin 출력 형식 변환기"""

    def to_legacy_format(
        self, dolphin_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """레거시 호환 형식으로 변환

        기존 read_pdf_as_text 출력과 동일한 형식 반환
        """
        return {
            "success": dolphin_result.get("success", False),
            "file_path": dolphin_result.get("file_path", ""),
            "total_pages": dolphin_result.get("total_pages", 0),
            "pages_read": dolphin_result.get("pages_read", 0),
            "content": dolphin_result.get("content", ""),
            "char_count": dolphin_result.get("char_count", 0),
            "cache_hit": dolphin_result.get("cache_hit", False),
            "cached_at": dolphin_result.get("cached_at", ""),
        }

    def to_structured_format(
        self, dolphin_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """구조화된 형식으로 변환

        레거시 필드 + 구조화된 콘텐츠 포함
        """
        result = self.to_legacy_format(dolphin_result)

        # 구조화된 콘텐츠 추가
        result["structured_content"] = dolphin_result.get("structured_content", {})
        result["financial_tables"] = dolphin_result.get("financial_tables", {})
        result["processing_method"] = dolphin_result.get("processing_method", "unknown")
        result["processing_time_seconds"] = dolphin_result.get("processing_time_seconds", 0)

        # 폴백 정보 (있는 경우)
        if dolphin_result.get("fallback_used"):
            result["fallback_used"] = True
            result["fallback_reason"] = dolphin_result.get("fallback_reason", "")

        return result

    def to_markdown(
        self, dolphin_result: Dict[str, Any]
    ) -> str:
        """Markdown 형식으로 변환"""
        parts = []

        structured = dolphin_result.get("structured_content", {})
        pages = structured.get("pages", [])

        for page in pages:
            page_num = page.get("page_num", 0)
            parts.append(f"\n---\n## 페이지 {page_num}\n")

            elements = page.get("elements", [])
            for elem in elements:
                elem_type = elem.get("type", "paragraph")
                text = elem.get("text", "")

                if elem_type == "table":
                    content = elem.get("content", {})
                    markdown = content.get("markdown", "")
                    parts.append(f"\n{markdown}\n")
                elif elem_type.startswith("heading"):
                    level = int(elem_type[-1]) if elem_type[-1].isdigit() else 2
                    parts.append(f"{'#' * level} {text}\n")
                else:
                    parts.append(f"{text}\n")

        return "".join(parts)

    def to_tables_only(
        self, dolphin_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """테이블만 추출하여 반환"""
        tables = []

        structured = dolphin_result.get("structured_content", {})
        pages = structured.get("pages", [])

        for page in pages:
            page_num = page.get("page_num", 0)
            elements = page.get("elements", [])

            for elem in elements:
                if elem.get("type") == "table":
                    tables.append({
                        "page": page_num,
                        "content": elem.get("content", {}),
                    })

        return {
            "success": dolphin_result.get("success", False),
            "file_path": dolphin_result.get("file_path", ""),
            "total_pages": dolphin_result.get("total_pages", 0),
            "table_count": len(tables),
            "tables": tables,
            "financial_tables": dolphin_result.get("financial_tables", {}),
        }

    def merge_with_financial_tables(
        self,
        dolphin_result: Dict[str, Any],
        financial_tables: Dict[str, Any],
    ) -> Dict[str, Any]:
        """재무제표 추출 결과 병합"""
        result = dict(dolphin_result)
        result["financial_tables"] = financial_tables
        return result


def convert_output(
    dolphin_result: Dict[str, Any],
    output_mode: str = "structured",
    legacy_format: bool = False,
) -> Dict[str, Any]:
    """출력 변환 편의 함수

    Args:
        dolphin_result: Dolphin 처리 결과
        output_mode: 출력 모드 (text_only, structured, tables_only)
        legacy_format: 레거시 포맷 강제 여부

    Returns:
        변환된 결과
    """
    converter = OutputConverter()

    if legacy_format or output_mode == "text_only":
        return converter.to_legacy_format(dolphin_result)
    elif output_mode == "tables_only":
        return converter.to_tables_only(dolphin_result)
    else:  # structured
        return converter.to_structured_format(dolphin_result)
