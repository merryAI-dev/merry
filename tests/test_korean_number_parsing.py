"""한국어 복합 숫자 파싱 유닛 테스트."""

import pytest

from dolphin_service.table_extractor import FinancialTableExtractor


@pytest.fixture
def extractor():
    return FinancialTableExtractor()


class TestKoreanCompoundNumbers:
    """복합 한국어 숫자 파싱 검증."""

    def test_simple_billion(self, extractor):
        # 5억 → 500,000,000
        assert extractor._parse_single_numeric("5억") == 500_000_000

    def test_compound_billion_ten_million(self, extractor):
        # 5억2천만 → 520,000,000 (핵심 버그 케이스)
        assert extractor._parse_single_numeric("5억2천만") == 520_000_000

    def test_trillion_compound(self, extractor):
        # 1조3천억 → 1,300,000,000,000
        assert extractor._parse_single_numeric("1조3천억") == 1_300_000_000_000

    def test_billion_with_man(self, extractor):
        # 32억4500만 → 3,245,000,000
        assert extractor._parse_single_numeric("32억4500만") == 3_245_000_000

    def test_pure_number(self, extractor):
        # 순수 숫자
        assert extractor._parse_single_numeric("1234567") == 1_234_567

    def test_comma_separated(self, extractor):
        assert extractor._parse_single_numeric("1,234,567") == 1_234_567

    def test_man_only(self, extractor):
        # 5000만 → 50,000,000
        assert extractor._parse_single_numeric("5000만") == 50_000_000

    def test_trillion_only(self, extractor):
        # 2조 → 2,000,000,000,000
        assert extractor._parse_single_numeric("2조") == 2_000_000_000_000

    def test_negative(self, extractor):
        assert extractor._parse_single_numeric("-5억") == -500_000_000

    def test_triangle_negative(self, extractor):
        assert extractor._parse_single_numeric("△3억2천만") == -320_000_000

    def test_with_won_suffix(self, extractor):
        assert extractor._parse_single_numeric("5억2천만원") == 520_000_000

    def test_with_spaces(self, extractor):
        assert extractor._parse_single_numeric("5억 2천만") == 520_000_000

    def test_baekman(self, extractor):
        # 3백만 → 3,000,000
        assert extractor._parse_single_numeric("3백만") == 3_000_000

    def test_compound_billion_baekman(self, extractor):
        # 1억5백만 → 105,000,000
        assert extractor._parse_single_numeric("1억5백만") == 105_000_000

    def test_none(self, extractor):
        assert extractor._parse_single_numeric(None) is None

    def test_dash(self, extractor):
        assert extractor._parse_single_numeric("-") is None

    def test_na(self, extractor):
        assert extractor._parse_single_numeric("N/A") is None

    def test_empty(self, extractor):
        assert extractor._parse_single_numeric("") is None

    def test_decimal_billion(self, extractor):
        # 1.5억 → 150,000,000
        assert extractor._parse_single_numeric("1.5억") == 150_000_000

    def test_full_compound(self, extractor):
        # 1조2천억3천만 → 1,200,030,000,000
        result = extractor._parse_single_numeric("1조2천억3천만")
        assert result == 1_200_030_000_000
