"""
문서 분류기 테스트

companyData/ 디렉토리의 실제 투자 문서 13개를 분류하고
기대 결과와 비교합니다.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dolphin_service.classifier import classify, DocType, ClassificationResult
from dolphin_service.strategy import get_strategy, STRATEGY_MAP, COST_ORDER
from dolphin_service.chunker import create_chunks, merge_chunk_results, compute_page_offsets
from dolphin_service.prompts import get_prompts


COMPANY_DATA = os.path.join(os.path.dirname(__file__), "..", "companyData")


def _path(filename: str) -> str:
    return os.path.join(COMPANY_DATA, filename)


# ─── 분류기 테스트 ───


@pytest.fixture
def skip_if_no_data():
    if not os.path.isdir(COMPANY_DATA):
        pytest.skip("companyData/ 디렉토리 없음")


class TestClassifier:
    """문서 분류 테스트"""

    def test_pure_text_정관(self, skip_if_no_data):
        result = classify(_path("7. MYSC_정관사본.pdf"))
        assert result.doc_type == DocType.PURE_TEXT
        assert result.image_count == 0
        assert result.text_chars > 1000

    def test_text_with_tables_재무제표(self, skip_if_no_data):
        result = classify(_path("6-1. MYSC_2022년 표준재무제표증명.pdf"))
        # 재무제표증명은 텍스트 + 테이블
        assert result.doc_type in (DocType.TEXT_WITH_TABLES, DocType.SIMPLE_FORM)
        assert result.table_count > 0

    def test_fully_scanned_등기부등본(self, skip_if_no_data):
        result = classify(_path("5. MYSC_법인등기부등본 (말소사항포함).pdf"))
        assert result.doc_type == DocType.FULLY_SCANNED
        assert result.scanned_page_ratio >= 0.8

    def test_image_heavy_IR(self, skip_if_no_data):
        result = classify(_path("10. MYSC_IR 자료.pdf"))
        assert result.doc_type == DocType.IMAGE_HEAVY
        assert result.image_count > 100

    def test_mixed_rich_투자검토자료(self, skip_if_no_data):
        result = classify(_path("1. MYSC_투자검토자료_스트레스솔루션_251211.pdf"))
        assert result.doc_type == DocType.MIXED_RICH
        assert result.total_pages > 30

    def test_small_table_주주명부(self, skip_if_no_data):
        result = classify(_path("2. MYSC_주주명부('25.10.16)_주식회사 스트레스솔루션.pdf"))
        # 1p + 테이블 → SMALL_TABLE
        assert result.doc_type in (DocType.SMALL_TABLE, DocType.SIMPLE_FORM)

    def test_simple_form_사업자등록증(self, skip_if_no_data):
        result = classify(_path("4. MYSC_사업자등록증.pdf"))
        assert result.doc_type == DocType.SIMPLE_FORM
        assert result.total_pages <= 4

    def test_simple_form_창업기업확인서(self, skip_if_no_data):
        result = classify(_path("9. MYSC_창업기업확인서.pdf"))
        assert result.doc_type == DocType.SIMPLE_FORM

    def test_인증서(self, skip_if_no_data):
        result = classify(
            _path("8. MYSC_인증서(중소기업, 벤처기업, 기업부설연구소, 스피커 전파인증KC).pdf")
        )
        assert result.doc_type == DocType.SIMPLE_FORM

    def test_classification_result_fields(self, skip_if_no_data):
        """ClassificationResult 필드가 올바르게 채워지는지 확인"""
        result = classify(_path("7. MYSC_정관사본.pdf"))
        assert isinstance(result, ClassificationResult)
        assert result.total_pages > 0
        assert result.total_size_bytes > 0
        assert result.per_page_text is not None
        assert len(result.per_page_text) == result.total_pages


# ─── 전략 테스트 ───


class TestStrategy:
    """처리 전략 테스트"""

    def test_pure_text_no_vision(self, skip_if_no_data):
        result = classify(_path("7. MYSC_정관사본.pdf"))
        strategy = get_strategy(result)
        assert strategy.use_vision is False
        assert strategy.model is None

    def test_fully_scanned_uses_vision(self, skip_if_no_data):
        result = classify(_path("5. MYSC_법인등기부등본 (말소사항포함).pdf"))
        strategy = get_strategy(result)
        assert strategy.use_vision is True
        assert "sonnet" in strategy.model.lower()
        assert strategy.dpi == 200  # 스캔 문서는 높은 DPI

    def test_simple_form_uses_haiku(self, skip_if_no_data):
        result = classify(_path("4. MYSC_사업자등록증.pdf"))
        strategy = get_strategy(result)
        assert strategy.use_vision is True
        assert "haiku" in strategy.model.lower()
        assert strategy.dpi == 100  # 단순 양식은 낮은 DPI

    def test_mixed_rich_uses_sonnet(self, skip_if_no_data):
        result = classify(_path("1. MYSC_투자검토자료_스트레스솔루션_251211.pdf"))
        strategy = get_strategy(result)
        assert strategy.use_vision is True
        assert "sonnet" in strategy.model.lower()
        assert strategy.chunk_pages == 8

    def test_cost_ordering(self):
        """비용 순서가 올바른지 확인"""
        assert COST_ORDER[DocType.PURE_TEXT] < COST_ORDER[DocType.SIMPLE_FORM]
        assert COST_ORDER[DocType.SIMPLE_FORM] < COST_ORDER[DocType.MIXED_RICH]


# ─── 청킹 테스트 ───


class TestChunker:
    """스마트 청킹 테스트"""

    def test_single_chunk_small(self):
        """작은 이미지 세트는 단일 청크"""
        from dolphin_service.strategy import ProcessingStrategy

        strategy = ProcessingStrategy(
            use_vision=True, model="test", dpi=150,
            prompt_type="test", max_tokens=1000,
            chunk_pages=8, max_chunk_mb=40,
        )
        images = ["a" * 1000] * 5  # 5개 작은 이미지
        chunks = create_chunks(images, strategy)
        assert len(chunks) == 1
        assert len(chunks[0]) == 5

    def test_page_limit_chunking(self):
        """페이지 제한으로 청크 분할"""
        from dolphin_service.strategy import ProcessingStrategy

        strategy = ProcessingStrategy(
            use_vision=True, model="test", dpi=150,
            prompt_type="test", max_tokens=1000,
            chunk_pages=3, max_chunk_mb=999,
        )
        images = ["a" * 100] * 10  # 10페이지
        chunks = create_chunks(images, strategy)
        assert len(chunks) == 4  # ceil(10/3) = 4
        assert len(chunks[0]) == 3
        assert len(chunks[-1]) == 1

    def test_size_limit_chunking(self):
        """크기 제한으로 청크 분할"""
        from dolphin_service.strategy import ProcessingStrategy

        strategy = ProcessingStrategy(
            use_vision=True, model="test", dpi=150,
            prompt_type="test", max_tokens=1000,
            chunk_pages=100, max_chunk_mb=0.001,  # 1KB
        )
        images = ["a" * 600] * 4  # 각 600B, 청크 1KB → 각 1개씩
        chunks = create_chunks(images, strategy)
        assert len(chunks) == 4

    def test_page_offsets(self):
        """페이지 오프셋 계산"""
        chunks = [["a"] * 5, ["b"] * 3, ["c"] * 2]
        offsets = compute_page_offsets(chunks)
        assert offsets == [0, 5, 8]

    def test_merge_results(self):
        """결과 병합"""
        results = [
            {
                "content": "page1-5",
                "structured_content": {"pages": [{"page_num": 1}]},
                "financial_tables": {"income_statement": {"found": True}},
            },
            {
                "content": "page6-10",
                "structured_content": {"pages": [{"page_num": 6}]},
                "financial_tables": {"balance_sheet": {"found": True}},
            },
        ]
        merged = merge_chunk_results(results, [0, 5])
        assert "page1-5" in merged["content"]
        assert "page6-10" in merged["content"]
        assert merged["financial_tables"]["income_statement"]["found"] is True
        assert merged["financial_tables"]["balance_sheet"]["found"] is True

    def test_empty_chunks(self):
        """빈 청크 처리"""
        from dolphin_service.strategy import ProcessingStrategy

        strategy = ProcessingStrategy(
            use_vision=True, model="test", dpi=150,
            prompt_type="test", max_tokens=1000,
            chunk_pages=5, max_chunk_mb=40,
        )
        chunks = create_chunks([], strategy)
        assert chunks == []


# ─── 프롬프트 테스트 ───


class TestPrompts:
    """프롬프트 레지스트리 테스트"""

    def test_financial_structured(self):
        system, user = get_prompts("financial_structured")
        assert "VC" in system or "투자심사역" in system
        assert "JSON" in user

    def test_legal_extraction(self):
        system, user = get_prompts("legal_extraction")
        assert "법률" in system or "OCR" in system
        assert "법인등기" in user or "등기" in user

    def test_certificate_extraction(self):
        system, user = get_prompts("certificate_extraction")
        assert "인증서" in system or "확인서" in system

    def test_text_only_mode_override(self):
        """output_mode=text_only면 prompt_type과 무관하게 텍스트 프롬프트"""
        system, user = get_prompts("financial_structured", output_mode="text_only")
        assert "텍스트로 추출" in user

    def test_tables_only_mode_override(self):
        system, user = get_prompts("financial_structured", output_mode="tables_only")
        assert "테이블만 추출" in user

    def test_unknown_prompt_type_fallback(self):
        """알 수 없는 prompt_type은 financial_structured로 폴백"""
        system, user = get_prompts("nonexistent_type")
        assert "투자심사" in system


# ─── 전체 분류 요약 테스트 ───


class TestFullClassification:
    """전체 companyData/ 분류 결과 요약"""

    def test_all_documents_classified(self, skip_if_no_data):
        """13개 문서 전체 분류 + 전략이 결정되는지 확인"""
        files = sorted(os.listdir(COMPANY_DATA))
        pdf_files = [f for f in files if f.endswith(".pdf")]
        assert len(pdf_files) == 13

        results = []
        for f in pdf_files:
            result = classify(_path(f))
            strategy = get_strategy(result)
            results.append((f, result, strategy))

        # 모든 파일이 분류됨
        assert len(results) == 13

        # 분류 통계
        doc_types = [r[1].doc_type for r in results]
        vision_count = sum(1 for r in results if r[2].use_vision)
        free_count = sum(1 for r in results if not r[2].use_vision)

        # 적어도 3개 이상은 Vision 불필요 (정관, 재무제표, 주주명부)
        assert free_count >= 3, f"Vision 불필요 문서가 {free_count}개뿐 (최소 3개 기대)"

        # 결과 출력 (pytest -s로 확인)
        print("\n\n=== 문서 분류 결과 ===")
        for filename, result, strategy in results:
            cost = "$0" if not strategy.use_vision else (
                f"~${0.005 * result.total_pages:.2f}"
                if "haiku" in (strategy.model or "")
                else f"~${0.03 * result.total_pages:.2f}"
            )
            print(
                f"  {result.doc_type.value:15s} | "
                f"vision={strategy.use_vision!s:5s} | "
                f"model={str(strategy.model or '-'):30s} | "
                f"pages={result.total_pages:3d} | "
                f"cost={cost:8s} | "
                f"{filename[:50]}"
            )
