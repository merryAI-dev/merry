"""
Stock market analysis tools.

yfinance-based stock financials and peer PER analysis.
"""

import time
from typing import Any, Dict, List

from ._common import (
    CACHE_TTL_SECONDS,
    CACHE_VERSION,
    compute_payload_hash,
    get_cache_dir,
    load_json,
    logger,
    save_json,
)

TOOLS = [
    {
        "name": "get_stock_financials",
        "description": "yfinance를 사용하여 상장 기업의 재무 지표를 조회합니다. PER, PSR, 매출, 영업이익률, 시가총액 등을 반환합니다. 한국 주식은 티커 뒤에 .KS(KOSPI) 또는 .KQ(KOSDAQ)를 붙입니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "주식 티커 심볼 (예: AAPL, MSFT, 005930.KS, 035720.KQ)",
                }
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "analyze_peer_per",
        "description": "여러 Peer 기업의 PER을 일괄 조회하고 비교 분석합니다. 평균, 중간값, 범위를 계산하여 적정 PER 배수를 제안합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "비교할 기업 티커 리스트 (예: ['AAPL', 'MSFT', 'GOOGL'])",
                },
                "include_forward_per": {
                    "type": "boolean",
                    "description": "Forward PER 포함 여부 (기본값: true)",
                },
            },
            "required": ["tickers"],
        },
    },
]


def _fetch_stock_info(ticker: str) -> dict:
    """yfinance에서 주식 정보 조회 (Rate Limit 대응)"""
    import yfinance as yf
    import random

    delay = random.uniform(5.0, 10.0)
    logger.info(f"Waiting {delay:.1f}s before fetching {ticker}...")
    time.sleep(delay)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            if not info or (isinstance(info, dict) and info.get("error")):
                if attempt < max_retries - 1:
                    retry_delay = 30 + random.uniform(0, 10)
                    logger.warning(
                        f"Rate limit detected for {ticker}, retrying in {retry_delay:.1f}s "
                        f"(attempt {attempt+1}/{max_retries})..."
                    )
                    time.sleep(retry_delay)
                    continue
            return info

        except Exception as e:
            if attempt < max_retries - 1:
                retry_delay = 30 + random.uniform(0, 10)
                logger.warning(
                    f"Error fetching {ticker}: {e}, retrying in {retry_delay:.1f}s "
                    f"(attempt {attempt+1}/{max_retries})..."
                )
                time.sleep(retry_delay)
            else:
                raise

    return {}


def _format_large_number(value) -> str:
    """큰 숫자를 읽기 쉬운 형식으로 변환"""
    if value is None:
        return "N/A"

    if abs(value) >= 1_000_000_000_000:
        return f"{value / 1_000_000_000_000:.2f}조"
    elif abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    elif abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    else:
        return f"{value:,.0f}"


def _generate_per_summary(stats: Dict[str, Any]) -> str:
    """PER 분석 요약 텍스트 생성"""
    summary_parts = []

    if "trailing_per" in stats:
        tp = stats["trailing_per"]
        summary_parts.append(
            f"Trailing PER: 평균 {tp['mean']}x, 중간값 {tp['median']}x "
            f"(범위: {tp['min']}x ~ {tp['max']}x)"
        )

    if "forward_per" in stats:
        fp = stats["forward_per"]
        summary_parts.append(
            f"Forward PER: 평균 {fp['mean']}x, 중간값 {fp['median']}x "
            f"(범위: {fp['min']}x ~ {fp['max']}x)"
        )

    if "operating_margin" in stats:
        om = stats["operating_margin"]
        summary_parts.append(
            f"영업이익률: 평균 {om['mean']}%, 중간값 {om['median']}% "
            f"(범위: {om['min']}% ~ {om['max']}%)"
        )

    return "\n".join(summary_parts)


def execute_get_stock_financials(ticker: str) -> Dict[str, Any]:
    """yfinance로 상장 기업 재무 지표 조회"""
    try:
        info = _fetch_stock_info(ticker)

        if not info or info.get("regularMarketPrice") is None:
            return {
                "success": False,
                "error": f"티커 '{ticker}'를 찾을 수 없습니다. 티커 형식을 확인하세요. "
                "(미국: AAPL, 한국 KOSPI: 005930.KS, KOSDAQ: 035720.KQ)",
            }

        return {
            "success": True,
            "ticker": ticker,
            "company_name": info.get("longName") or info.get("shortName", "N/A"),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "country": info.get("country", "N/A"),
            "currency": info.get("currency", "USD"),
            "market_cap": info.get("marketCap"),
            "market_cap_formatted": _format_large_number(info.get("marketCap")),
            "trailing_per": info.get("trailingPE"),
            "forward_per": info.get("forwardPE"),
            "psr": info.get("priceToSalesTrailing12Months"),
            "pbr": info.get("priceToBook"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "ev_revenue": info.get("enterpriseToRevenue"),
            "revenue": info.get("totalRevenue"),
            "revenue_formatted": _format_large_number(info.get("totalRevenue")),
            "net_income": info.get("netIncomeToCommon"),
            "net_income_formatted": _format_large_number(info.get("netIncomeToCommon")),
            "operating_margin": info.get("operatingMargins"),
            "profit_margin": info.get("profitMargins"),
            "gross_margin": info.get("grossMargins"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "current_price": info.get("regularMarketPrice"),
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
        }

    except ImportError:
        return {
            "success": False,
            "error": "yfinance가 설치되지 않았습니다. pip install yfinance를 실행하세요.",
        }
    except Exception as e:
        return {"success": False, "error": f"주식 정보 조회 실패: {str(e)}"}


def execute_analyze_peer_per(
    tickers: List[str], include_forward_per: bool = True
) -> Dict[str, Any]:
    """여러 Peer 기업 PER 일괄 조회 및 비교 분석"""
    try:
        import statistics

        now_ts = time.time()
        try:
            payload = {
                "version": CACHE_VERSION,
                "tickers": tickers,
                "include_forward_per": include_forward_per,
                "tool": "analyze_peer_per",
            }
            cache_key = compute_payload_hash(payload)
            cache_dir = get_cache_dir("peer_per", "shared")
            cache_path = cache_dir / f"{cache_key}.json"
            cached = load_json(cache_path)
            if cached:
                cached_ts = cached.get("cached_at_ts")
                if isinstance(cached_ts, (int, float)) and now_ts - cached_ts < CACHE_TTL_SECONDS:
                    cached["cache_hit"] = True
                    return cached
        except Exception:
            cache_path = None

        peer_data = []
        failed_tickers = []
        total = len(tickers)

        logger.info(
            f"[Peer PER 분석] 총 {total}개 기업 조회 시작 "
            f"(예상 소요: {total * 8}~{total * 12}초)"
        )

        for idx, ticker in enumerate(tickers, 1):
            logger.info(f"[{idx}/{total}] {ticker} 조회 중...")

            try:
                info = _fetch_stock_info(ticker)

                if not info or info.get("regularMarketPrice") is None:
                    logger.warning(f"[{idx}/{total}] {ticker} 조회 실패 - 데이터 없음")
                    failed_tickers.append(ticker)
                    continue

                company_name = info.get("longName") or info.get("shortName", "N/A")
                logger.info(f"[{idx}/{total}] {ticker} 완료 - {company_name}")

                data = {
                    "ticker": ticker,
                    "company_name": company_name,
                    "sector": info.get("sector", "N/A"),
                    "industry": info.get("industry", "N/A"),
                    "market_cap": info.get("marketCap"),
                    "market_cap_formatted": _format_large_number(info.get("marketCap")),
                    "trailing_per": info.get("trailingPE"),
                    "forward_per": info.get("forwardPE") if include_forward_per else None,
                    "revenue": info.get("totalRevenue"),
                    "revenue_formatted": _format_large_number(info.get("totalRevenue")),
                    "operating_margin": info.get("operatingMargins"),
                    "profit_margin": info.get("profitMargins"),
                    "revenue_growth": info.get("revenueGrowth"),
                }

                peer_data.append(data)

            except Exception as e:
                logger.warning(f"[{idx}/{total}] {ticker} 조회 실패 - {e}")
                failed_tickers.append(ticker)

        logger.info(
            f"[Peer PER 분석] 완료 - 성공: {len(peer_data)}개, 실패: {len(failed_tickers)}개"
        )

        if not peer_data:
            return {
                "success": False,
                "error": "유효한 티커가 없습니다.",
                "failed_tickers": failed_tickers,
            }

        trailing_pers = [d["trailing_per"] for d in peer_data if d["trailing_per"] is not None]
        forward_pers = [d["forward_per"] for d in peer_data if d.get("forward_per") is not None]
        operating_margins = [
            d["operating_margin"] for d in peer_data if d["operating_margin"] is not None
        ]

        stats = {}

        if trailing_pers:
            stats["trailing_per"] = {
                "mean": round(statistics.mean(trailing_pers), 2),
                "median": round(statistics.median(trailing_pers), 2),
                "min": round(min(trailing_pers), 2),
                "max": round(max(trailing_pers), 2),
                "count": len(trailing_pers),
            }

        if forward_pers:
            stats["forward_per"] = {
                "mean": round(statistics.mean(forward_pers), 2),
                "median": round(statistics.median(forward_pers), 2),
                "min": round(min(forward_pers), 2),
                "max": round(max(forward_pers), 2),
                "count": len(forward_pers),
            }

        if operating_margins:
            stats["operating_margin"] = {
                "mean": round(statistics.mean(operating_margins) * 100, 2),
                "median": round(statistics.median(operating_margins) * 100, 2),
                "min": round(min(operating_margins) * 100, 2),
                "max": round(max(operating_margins) * 100, 2),
                "count": len(operating_margins),
            }

        warnings = []
        outliers = {}
        trailing_pairs = [
            (d["ticker"], d["trailing_per"]) for d in peer_data if d["trailing_per"] is not None
        ]
        if len(trailing_pairs) >= 4:
            values = [val for _, val in trailing_pairs]
            q1, q3 = statistics.quantiles(values, n=4)[0], statistics.quantiles(values, n=4)[2]
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            outlier_tickers = [ticker for ticker, val in trailing_pairs if val < lower or val > upper]
            if outlier_tickers:
                outliers["trailing_per"] = outlier_tickers
                warnings.append(f"Trailing PER 이상치 후보: {', '.join(outlier_tickers)}")

        missing_per = [d["ticker"] for d in peer_data if d["trailing_per"] is None]
        if missing_per:
            warnings.append(f"Trailing PER 미확인: {', '.join(missing_per)}")

        result = {
            "success": True,
            "peer_count": len(peer_data),
            "peers": peer_data,
            "statistics": stats,
            "failed_tickers": failed_tickers,
            "summary": _generate_per_summary(stats),
            "warnings": warnings,
            "outliers": outliers,
            "cache_hit": False,
            "cached_at_ts": now_ts,
        }
        if cache_path:
            save_json(cache_path, result)
        return result

    except ImportError:
        return {
            "success": False,
            "error": "yfinance가 설치되지 않았습니다. pip install yfinance를 실행하세요.",
        }
    except Exception as e:
        return {"success": False, "error": f"Peer PER 분석 실패: {str(e)}"}


EXECUTORS = {
    "get_stock_financials": execute_get_stock_financials,
    "analyze_peer_per": execute_analyze_peer_per,
}
