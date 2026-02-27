"""
Natural Language Converter: structured JSON → natural language sentences.

Following STORM Parse principles, converts extraction results to
natural language for RAG/embedding optimization.
"""

import logging
from typing import Any

from .schemas import ExtractionResult

logger = logging.getLogger(__name__)


def _fmt_money(v: int | None) -> str:
    """Format money in Korean style."""
    if v is None:
        return "미상"
    if abs(v) >= 1_0000_0000:
        return f"{v / 1_0000_0000:.1f}억원"
    if abs(v) >= 1_0000:
        return f"{v / 1_0000:.0f}만원"
    return f"{v:,}원"


def convert_to_natural_language(result, doc_type: str) -> str:
    """
    구조화 데이터 → 자연어 문장 변환 (RAG 최적화).

    Args:
        result: Pydantic 모델 또는 dict
        doc_type: 문서 타입

    Returns:
        Natural language summary string
    """
    try:
        if isinstance(result, dict):
            return _nl_from_dict(result, doc_type)
        return _nl_generic(result)
    except Exception as e:
        logger.warning(f"NL 변환 실패: {e}")
        return f"[{doc_type}] 자연어 변환 중 오류 발생"


def _nl_from_dict(data: dict, doc_type: str) -> str:
    """dict 데이터에서 자연어 변환."""
    if doc_type == "business_reg":
        corp = data.get("corp_name", "회사")
        biz_num = data.get("business_number", "미상")
        rep = data.get("representative", "미상")
        parts = [f"{corp}의 사업자등록번호는 {biz_num}이며, 대표자는 {rep}입니다."]
        if data.get("business_type"):
            parts.append(f"업태는 {data['business_type']}이고 종목은 {data.get('business_item', '미상')}입니다.")
        if data.get("address"):
            parts.append(f"사업장 소재지는 {data['address']}입니다.")
        if data.get("opening_date"):
            parts.append(f"개업일은 {data['opening_date']}입니다.")
        return " ".join(parts)

    elif doc_type == "financial_stmt":
        return _nl_financial_stmt(data)

    elif doc_type == "shareholder":
        return _nl_shareholder(data)

    elif doc_type == "investment_review":
        return _nl_investment_review(data)

    else:
        # 범용 dict 변환
        skip_keys = {"doc_type", "source_file", "extracted_at", "confidence",
                      "raw_fields", "natural_language", "statements"}
        fields = {k: v for k, v in data.items()
                  if v is not None and k not in skip_keys}
        parts = [f"[{doc_type}] 추출 결과:"]
        for k, v in list(fields.items())[:10]:
            parts.append(f"- {k}: {v}")
        return "\n".join(parts)


def _nl_financial_stmt(data: dict) -> str:
    """재무제표 자연어 변환."""
    corp = data.get("corp_name", "회사")
    stmt_type = data.get("statement_type", "재무제표")
    parts = [f"{corp}의 {stmt_type} 추출 결과입니다."]

    for stmt in data.get("statements", []):
        year = stmt.get("year", "?")
        parts.append(f"\n{year}년도:")
        if stmt.get("revenue") is not None:
            parts.append(f"  매출액 {_fmt_money(stmt['revenue'])}")
        if stmt.get("operating_income") is not None:
            parts.append(f"  영업이익 {_fmt_money(stmt['operating_income'])}")
        if stmt.get("net_income") is not None:
            parts.append(f"  당기순이익 {_fmt_money(stmt['net_income'])}")
        if stmt.get("total_assets") is not None:
            parts.append(f"  자산총계 {_fmt_money(stmt['total_assets'])}")
        if stmt.get("equity") is not None:
            parts.append(f"  자본총계 {_fmt_money(stmt['equity'])}")

    if data.get("issue_date"):
        parts.append(f"\n발급일: {data['issue_date']}")

    return "\n".join(parts)


def _nl_shareholder(data: dict) -> str:
    """주주명부 자연어 변환."""
    corp = data.get("corp_name", "회사")
    parts = [f"{corp}의 주주명부입니다."]

    if data.get("base_date"):
        parts.append(f"기준일: {data['base_date']}")

    for sh in data.get("shareholders", []):
        name = sh.get("name", "?")
        shares = sh.get("shares", 0)
        ratio = sh.get("ratio", 0)
        parts.append(f"  {name}: {shares:,}주 ({ratio:.1f}%)")

    if data.get("total_shares"):
        parts.append(f"발행주식 총수: {data['total_shares']:,}주")
    if data.get("capital"):
        parts.append(f"자본금: {_fmt_money(data['capital'])}")

    return "\n".join(parts)


def _nl_investment_review(data: dict) -> str:
    """투자검토자료 자연어 변환."""
    corp = data.get("corp_name", "회사")
    parts = [f"{corp} 투자검토자료 요약입니다."]

    if data.get("representative"):
        parts.append(f"대표자: {data['representative']}")
    if data.get("product_name"):
        parts.append(f"제품/서비스: {data['product_name']}")
    if data.get("founded_date"):
        parts.append(f"설립일: {data['founded_date']}")
    if data.get("employee_count"):
        parts.append(f"직원수: {data['employee_count']}")

    if data.get("cap_table"):
        parts.append(f"\n주주 {len(data['cap_table'])}명 (Cap Table 추출 완료)")

    hist = data.get("historical_financials", {})
    if hist.get("income_statement"):
        years = sorted(hist["income_statement"].keys())
        for y in years[-2:]:
            is_data = hist["income_statement"][y]
            rev = is_data.get("revenue")
            ni = is_data.get("net_income")
            if rev is not None:
                parts.append(f"\n{y}년: 매출 {_fmt_money(rev)}, 순이익 {_fmt_money(ni)}")

    proj = data.get("projected_financials", {})
    if proj:
        years = sorted(proj.keys())
        for y in years[:2]:
            rev = proj[y].get("revenue")
            ni = proj[y].get("net_income")
            if rev is not None:
                parts.append(f"{y}년(E): 매출 {_fmt_money(rev)}, 순이익 {_fmt_money(ni)}")

    parts.append(f"\n이미지 {data.get('image_count', 0)}개, 섹션 {len(data.get('sections', []))}개")

    return "\n".join(parts)


def _nl_generic(result: ExtractionResult) -> str:
    """Generic fallback for Pydantic models."""
    try:
        fields = {k: v for k, v in result.raw_fields.items()
                  if v is not None and not k.startswith("_")}
    except AttributeError:
        return f"[{getattr(result, 'doc_type', '?')}] 추출 결과"
    parts = [f"[{result.doc_type}] 추출 결과:"]
    for k, v in list(fields.items())[:10]:
        parts.append(f"- {k}: {v}")
    return "\n".join(parts)
