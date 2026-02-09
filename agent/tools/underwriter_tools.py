"""
Underwriter opinion search tools.

DART underwriter opinion JSONL search, TF-IDF similarity,
PDF market evidence extraction, and data fetching.
"""

import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from ._common import (
    CACHE_VERSION,
    PROJECT_ROOT,
    _normalize_text,
    _sanitize_filename,
    _validate_file_path,
    compute_file_hash,
    compute_payload_hash,
    get_cache_dir,
    load_json,
    logger,
    save_json,
)

# ========================================
# Constants
# ========================================

DEFAULT_UNDERWRITER_DATA_PATH = (
    PROJECT_ROOT
    / "temp"
    / "dart_underwriter_opinion_2025_v5_window"
    / "underwriter_opinion.jsonl"
)

UNDERWRITER_CATEGORY_KEYWORDS = {
    "market_size": {
        "any": ["시장 규모", "시장규모", "TAM", "SAM", "SOM", "CAGR", "연평균", "성장률", "시장 전망", "시장전망", "시장성장"],
        "all": ["시장", "규모"],
    },
    "valuation": {
        "any": ["공모가격", "희망공모가액", "PER", "EV/EBITDA", "PBR", "PSR", "DCF", "할인율"],
        "all": [],
    },
    "comparables": {
        "any": ["비교회사", "비교기업", "유사기업", "선정"],
        "all": [],
    },
    "demand_forecast": {
        "any": ["수요예측", "수요 예측"],
        "all": [],
    },
    "risk": {
        "any": ["위험", "리스크", "유의", "불확실", "변동", "미래예측"],
        "all": [],
    },
}

_UNDERWRITER_TFIDF_CACHE = {
    "path": None,
    "mtime": None,
    "size": None,
    "min_n": None,
    "max_n": None,
    "max_text_chars": None,
    "idf": None,
    "vectors": None,
    "entries": None,
    "texts": None,
}

# ========================================
# Tool definitions
# ========================================

TOOLS = [
    {
        "name": "search_underwriter_opinion",
        "description": "인수인의견(분석기관의 평가의견) JSONL 데이터에서 특정 카테고리/기업/키워드에 맞는 문장과 패턴을 추출합니다. 시장규모 근거, 비교기업 선정, 공모가 산정 논리 등 반복 패턴을 일반화할 때 사용하세요.",
        "input_schema": {
            "type": "object",
            "properties": {
                "jsonl_path": {
                    "type": "string",
                    "description": "underwriter_opinion.jsonl 경로 (선택, 기본: 프로젝트 temp 경로)",
                },
                "category": {
                    "type": "string",
                    "description": "카테고리 (market_size, valuation, comparables, demand_forecast, risk 중 선택)",
                },
                "corp_name": {
                    "type": "string",
                    "description": "기업명 필터 (선택)",
                },
                "query": {
                    "type": "string",
                    "description": "추가 검색어 (선택)",
                },
                "max_results": {
                    "type": "integer",
                    "description": "최대 결과 수 (기본값: 5)",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "문장/본문 최대 길이 (기본값: 800)",
                },
                "min_section_length": {
                    "type": "integer",
                    "description": "섹션 길이 최소값 (기본값: 0)",
                },
                "return_patterns": {
                    "type": "boolean",
                    "description": "일반화된 패턴 문장 반환 여부 (기본값: true)",
                },
                "output_filename": {
                    "type": "string",
                    "description": "결과 저장 파일명 (선택, temp/에 JSON 저장)",
                },
            },
        },
    },
    {
        "name": "search_underwriter_opinion_similar",
        "description": "인수인의견 JSONL 데이터에서 입력 질의와 유사한 문장을 유사도 기반으로 검색합니다. 키워드 매칭이 어려운 경우 보완용으로 사용하세요.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "유사도 검색 질의 (시장/기술/산업 관련 문장 권장)",
                },
                "jsonl_path": {
                    "type": "string",
                    "description": "underwriter_opinion.jsonl 경로 (선택, 기본: 프로젝트 temp 경로)",
                },
                "category": {
                    "type": "string",
                    "description": "카테고리 필터 (market_size, valuation, comparables, demand_forecast, risk 중 선택, 선택사항)",
                },
                "corp_name": {
                    "type": "string",
                    "description": "기업명 필터 (선택)",
                },
                "top_k": {
                    "type": "integer",
                    "description": "상위 결과 수 (기본값: 5)",
                },
                "min_score": {
                    "type": "number",
                    "description": "유사도 최소 점수 (기본값: 0.05)",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "문장/본문 최대 길이 (기본값: 800)",
                },
                "min_section_length": {
                    "type": "integer",
                    "description": "섹션 길이 최소값 (기본값: 0)",
                },
                "max_text_chars": {
                    "type": "integer",
                    "description": "유사도 계산용 텍스트 최대 길이 (기본값: 2000)",
                },
                "return_patterns": {
                    "type": "boolean",
                    "description": "일반화된 패턴 문장 반환 여부 (기본값: true)",
                },
                "output_filename": {
                    "type": "string",
                    "description": "결과 저장 파일명 (선택, temp/에 JSON 저장)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "extract_pdf_market_evidence",
        "description": "PDF에서 시장규모 근거가 될 수 있는 문장을 페이지 번호와 함께 추출합니다. 숫자/단위가 포함된 문장을 우선 수집합니다.",
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
                "max_results": {
                    "type": "integer",
                    "description": "최대 결과 수 (기본값: 20)",
                },
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "추가 키워드 (선택)",
                },
            },
            "required": ["pdf_path"],
        },
    },
    {
        "name": "fetch_underwriter_opinion_data",
        "description": "인수인의견 원천 데이터를 API에서 수집하여 JSONL로 생성합니다. API 키가 필요하며, 결과는 temp/ 하위에 저장됩니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "시작일 (YYYYMMDD, 선택)",
                },
                "end_date": {
                    "type": "string",
                    "description": "종료일 (YYYYMMDD, 선택)",
                },
                "lookback_days": {
                    "type": "integer",
                    "description": "종료일 기준 조회 기간 (일, 기본값: 365)",
                },
                "out_dir": {
                    "type": "string",
                    "description": "출력 디렉토리 (선택, temp/ 하위로 제한)",
                },
                "max_items": {
                    "type": "integer",
                    "description": "최대 처리 건수 (기본값: 200)",
                },
                "last_only": {
                    "type": "boolean",
                    "description": "최종 보고서만 수집 (기본값: true)",
                },
                "include_corrections": {
                    "type": "boolean",
                    "description": "정정/확정 보고서 포함 여부 (기본값: false)",
                },
                "min_length": {
                    "type": "integer",
                    "description": "섹션 최소 길이 (기본값: 600)",
                },
                "min_score": {
                    "type": "number",
                    "description": "섹션 최소 점수 (기본값: 3.0)",
                },
                "api_key": {
                    "type": "string",
                    "description": "API 키 (선택, 없으면 환경변수 사용)",
                },
            },
        },
    },
]

# ========================================
# Helper functions
# ========================================


def _resolve_underwriter_data_path(jsonl_path: str = None) -> tuple:
    candidates = []
    if jsonl_path:
        candidates.append(Path(jsonl_path))

    env_path = os.getenv("UNDERWRITER_DATA_PATH")
    if env_path:
        candidates.append(Path(env_path))

    candidates.append(DEFAULT_UNDERWRITER_DATA_PATH)

    if not jsonl_path:
        temp_root = PROJECT_ROOT / "temp"
        if temp_root.exists():
            patterns = [
                "dart_underwriter_opinion*/underwriter_opinion.jsonl",
                "underwriter_opinion*/underwriter_opinion.jsonl",
                "**/underwriter_opinion.jsonl",
            ]
            seen = set()
            for pattern in patterns:
                for p in temp_root.glob(pattern):
                    if p in seen:
                        continue
                    seen.add(p)
                    candidates.append(p)

    for candidate in candidates:
        if not candidate:
            continue
        try:
            resolved = candidate.resolve()
        except OSError:
            continue

        if resolved.exists():
            return str(resolved), None

    message = (
        "인수인의견 JSONL 파일을 찾을 수 없습니다. "
        "temp/ 하위에 underwriter_opinion.jsonl을 두거나 "
        "UNDERWRITER_DATA_PATH 환경변수를 설정하세요."
    )
    return None, message


def _match_underwriter_category(text: str, category: str) -> tuple:
    if not category:
        return True, []
    keywords = UNDERWRITER_CATEGORY_KEYWORDS.get(category)
    if not keywords:
        return False, []

    text_lower = text.lower()
    any_terms = [t.lower() for t in keywords.get("any", []) if t]
    all_terms = [t.lower() for t in keywords.get("all", []) if t]

    if all_terms and not all(term in text_lower for term in all_terms):
        return False, []
    if any_terms and not any(term in text_lower for term in any_terms):
        return False, []

    matched = [term for term in any_terms if term in text_lower]
    matched += [term for term in all_terms if term in text_lower and term not in matched]
    return True, matched


def _extract_snippet(text: str, terms: List[str], max_chars: int) -> str:
    if not text:
        return ""

    text_clean = _normalize_text(text)
    if not text_clean:
        return ""

    if terms:
        text_lower = text_clean.lower()
        for term in terms:
            term_lower = term.lower()
            idx = text_lower.find(term_lower)
            if idx >= 0:
                start = max(0, idx - 120)
                end = min(len(text_clean), idx + max_chars)
                return text_clean[start:end].strip()

    return text_clean[:max_chars].strip()


def _split_sentences(text: str) -> List[str]:
    if not text:
        return []
    normalized = text.replace("\n", " ")
    parts = re.split(r"(?<=[.!?])\s+|(?<=\.)\s+|(?<=다\.)\s+", normalized)
    return [_normalize_text(p) for p in parts if _normalize_text(p)]


def _extract_market_size_sentences(text: str, max_sentences: int = 2) -> str:
    if not text:
        return ""
    candidates = []
    for sentence in _split_sentences(text):
        if len(candidates) >= max_sentences:
            break
        if any(keyword in sentence for keyword in ["시장", "TAM", "SAM", "SOM", "CAGR", "연평균", "성장률", "규모"]):
            if re.search(r"\d", sentence):
                candidates.append(sentence)
    if not candidates:
        return ""
    return " ".join(candidates)


def _extract_numeric_phrases(text: str) -> List[str]:
    if not text:
        return []
    pattern = re.compile(
        r"\d+(?:,\d{3})*(?:\.\d+)?\s*(?:조|억|억원|백만|백만원|천만|만원|원|달러|usd|백만달러|억달러|톤|t|kg|%)",
        re.IGNORECASE,
    )
    return pattern.findall(text)


def _generalize_underwriter_text(text: str, corp_name: str = None) -> str:
    if not text:
        return ""
    generalized = text
    if corp_name:
        generalized = re.sub(re.escape(corp_name), "{회사}", generalized)
    generalized = re.sub(r"\b20\d{2}년\b", "{연도}", generalized)
    generalized = re.sub(r"\b20\d{2}\b", "{연도}", generalized)
    generalized = re.sub(
        r"\d+(?:,\d{3})*(?:\.\d+)?\s*(?:조|억|억원|백만|백만원|천만|만원|원|달러|USD|백만달러|억달러)\b",
        "{금액}",
        generalized,
    )
    generalized = re.sub(r"\d+(?:\.\d+)?\s*%", "{비율}", generalized)
    generalized = re.sub(r"\d{1,3}(?:,\d{3})+", "{숫자}", generalized)
    generalized = re.sub(r"\d+", "{숫자}", generalized)
    generalized = re.sub(r"\s+", " ", generalized).strip()
    return generalized


def _parse_underwriter_jsonl(jsonl_path: str) -> List[Dict[str, Any]]:
    entries = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _normalize_similarity_text(text: str, max_chars: int = 2000) -> str:
    if not text:
        return ""
    normalized = text.lower()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\d", "0", normalized)
    normalized = normalized.strip()
    if max_chars and len(normalized) > max_chars:
        normalized = normalized[:max_chars]
    return normalized


def _char_ngram_counts(text: str, min_n: int = 3, max_n: int = 5) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    length = len(text)
    for n in range(min_n, max_n + 1):
        if length < n:
            continue
        for i in range(length - n + 1):
            token = text[i : i + n]
            counts[token] = counts.get(token, 0) + 1
    return counts


def _build_tfidf_index(texts: List[str], min_n: int = 3, max_n: int = 5) -> tuple:
    counts_list = [_char_ngram_counts(text, min_n=min_n, max_n=max_n) for text in texts]
    df: Dict[str, int] = {}
    for counts in counts_list:
        for term in counts.keys():
            df[term] = df.get(term, 0) + 1

    doc_count = len(counts_list)
    idf = {term: math.log((1 + doc_count) / (1 + freq)) + 1 for term, freq in df.items()}

    vectors = []
    for counts in counts_list:
        vec: Dict[str, float] = {}
        norm = 0.0
        for term, tf in counts.items():
            weight = (1 + math.log(tf)) * idf[term]
            vec[term] = weight
            norm += weight * weight
        vectors.append((vec, math.sqrt(norm)))
    return idf, vectors


def _vectorize_query(text: str, idf: Dict[str, float], min_n: int = 3, max_n: int = 5) -> tuple:
    counts = _char_ngram_counts(text, min_n=min_n, max_n=max_n)
    vec: Dict[str, float] = {}
    norm = 0.0
    for term, tf in counts.items():
        if term not in idf:
            continue
        weight = (1 + math.log(tf)) * idf[term]
        vec[term] = weight
        norm += weight * weight
    return vec, math.sqrt(norm)


def _cosine_similarity(vec_a: Dict[str, float], norm_a: float, vec_b: Dict[str, float], norm_b: float) -> float:
    if norm_a == 0 or norm_b == 0:
        return 0.0
    if len(vec_a) > len(vec_b):
        vec_a, vec_b = vec_b, vec_a
        norm_a, norm_b = norm_b, norm_a
    dot = 0.0
    for term, weight in vec_a.items():
        dot += weight * vec_b.get(term, 0.0)
    return dot / (norm_a * norm_b)


def _get_underwriter_tfidf_index(jsonl_path: str, min_n: int = 3, max_n: int = 5, max_text_chars: int = 2000):
    cache = _UNDERWRITER_TFIDF_CACHE
    try:
        stat = os.stat(jsonl_path)
    except OSError:
        return None, "JSONL 파일 정보를 읽을 수 없습니다"

    if (
        cache["path"] == jsonl_path
        and cache["mtime"] == stat.st_mtime
        and cache["size"] == stat.st_size
        and cache["min_n"] == min_n
        and cache["max_n"] == max_n
        and cache["max_text_chars"] == max_text_chars
        and cache["idf"] is not None
        and cache["vectors"] is not None
        and cache["entries"] is not None
        and cache["texts"] is not None
    ):
        return cache, None

    entries = _parse_underwriter_jsonl(jsonl_path)
    texts = []
    for entry in entries:
        combined = f"{entry.get('section_title', '')}\n{entry.get('section_text', '')}"
        texts.append(_normalize_similarity_text(combined, max_chars=max_text_chars))

    idf, vectors = _build_tfidf_index(texts, min_n=min_n, max_n=max_n)

    cache.update(
        {
            "path": jsonl_path,
            "mtime": stat.st_mtime,
            "size": stat.st_size,
            "min_n": min_n,
            "max_n": max_n,
            "max_text_chars": max_text_chars,
            "idf": idf,
            "vectors": vectors,
            "entries": entries,
            "texts": texts,
        }
    )
    return cache, None


# ========================================
# Executor functions
# ========================================


def execute_search_underwriter_opinion(
    jsonl_path: str = None,
    category: str = None,
    corp_name: str = None,
    query: str = None,
    max_results: int = 5,
    max_chars: int = 800,
    min_section_length: int = 0,
    return_patterns: bool = True,
    output_filename: str = None,
) -> Dict[str, Any]:
    """인수인의견 JSONL에서 관련 문장 및 일반화 패턴 추출"""
    resolved_path, resolve_error = _resolve_underwriter_data_path(jsonl_path)
    if resolve_error:
        return {
            "success": False,
            "error": resolve_error,
            "suggested_action": "인수인의견 데이터 생성 스크립트를 실행하거나 UNDERWRITER_DATA_PATH를 설정하세요.",
        }
    jsonl_path = resolved_path
    category = category.strip().lower() if isinstance(category, str) else category
    try:
        max_results = int(max_results) if max_results is not None else 5
    except (TypeError, ValueError):
        max_results = 5
    try:
        max_chars = int(max_chars) if max_chars is not None else 800
    except (TypeError, ValueError):
        max_chars = 800
    try:
        min_section_length = int(min_section_length) if min_section_length is not None else 0
    except (TypeError, ValueError):
        min_section_length = 0
    if isinstance(return_patterns, str):
        return_patterns = return_patterns.strip().lower() in ("true", "1", "yes", "y")

    is_valid, error = _validate_file_path(
        jsonl_path,
        allowed_extensions=[".jsonl"],
        require_temp_dir=True,
    )
    if not is_valid:
        return {
            "success": False,
            "error": error,
            "suggested_action": "인수인의견 데이터 파일을 temp/ 하위로 이동해 주세요.",
        }

    if not os.path.exists(jsonl_path):
        return {
            "success": False,
            "error": f"파일을 찾을 수 없습니다: {jsonl_path}",
            "suggested_action": "인수인의견 데이터 파일 경로를 확인하세요.",
        }

    try:
        entries = _parse_underwriter_jsonl(jsonl_path)
    except Exception as e:
        logger.error(f"Underwriter JSONL parse failed: {e}", exc_info=True)
        return {"success": False, "error": "JSONL 파싱 실패"}

    results = []
    query_lower = query.lower() if query else None

    for entry in entries:
        section_text = entry.get("section_text") or ""
        section_title = entry.get("section_title") or ""
        combined_text = f"{section_title}\n{section_text}"

        if corp_name:
            if corp_name not in entry.get("corp_name", ""):
                continue

        if min_section_length and entry.get("section_length", 0) < min_section_length:
            continue

        matched_keywords = []
        if category:
            ok, matched_keywords = _match_underwriter_category(combined_text, category)
            if not ok:
                continue

        if query_lower:
            if query_lower not in combined_text.lower():
                continue
            matched_keywords.append(query_lower)

        if category == "market_size":
            snippet = _extract_market_size_sentences(section_text)
        else:
            snippet = ""

        if snippet and max_chars:
            snippet = snippet[:max_chars].strip()

        if not snippet:
            terms = matched_keywords or []
            snippet = _extract_snippet(section_text, terms, max_chars=max_chars)

        score = 0.0
        quality_score = entry.get("quality_score") or 0
        section_length = entry.get("section_length") or 0
        score += float(quality_score)
        score += float(section_length) * 0.0001
        score += len(matched_keywords) * 0.3

        results.append(
            {
                "corp_name": entry.get("corp_name"),
                "rcept_no": entry.get("rcept_no"),
                "report_nm": entry.get("report_nm"),
                "rcept_dt": entry.get("rcept_dt"),
                "section_title": section_title,
                "section_length": section_length,
                "quality_score": quality_score,
                "matched_keywords": matched_keywords,
                "snippet": snippet,
                "score": round(score, 4),
            }
        )

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    results = results[:max_results] if max_results else results

    patterns = []
    if return_patterns:
        seen = set()
        for item in results:
            template = _generalize_underwriter_text(item.get("snippet"), item.get("corp_name"))
            if template and template not in seen:
                patterns.append(template)
                seen.add(template)

    response = {
        "success": True,
        "source_path": jsonl_path,
        "filters": {
            "category": category,
            "corp_name": corp_name,
            "query": query,
            "max_results": max_results,
            "max_chars": max_chars,
            "min_section_length": min_section_length,
        },
        "results": results,
        "patterns": patterns,
    }

    if output_filename:
        sanitized_name = _sanitize_filename(output_filename)
        if not sanitized_name.endswith(".json"):
            sanitized_name += ".json"
        output_dir = PROJECT_ROOT / "temp"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / sanitized_name
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(response, f, ensure_ascii=False, indent=2)
            response["output_file"] = str(output_path)
        except OSError as e:
            logger.error(f"Failed to write underwriter output: {e}", exc_info=True)
            response["output_file_error"] = str(e)

    return response


def execute_search_underwriter_opinion_similar(
    query: str,
    jsonl_path: str = None,
    category: str = None,
    corp_name: str = None,
    top_k: int = 5,
    min_score: float = 0.05,
    max_chars: int = 800,
    min_section_length: int = 0,
    max_text_chars: int = 2000,
    return_patterns: bool = True,
    output_filename: str = None,
) -> Dict[str, Any]:
    """인수인의견 JSONL에서 유사도 기반 문장 검색"""
    if not query or not str(query).strip():
        return {"success": False, "error": "query가 비어 있습니다"}

    resolved_path, resolve_error = _resolve_underwriter_data_path(jsonl_path)
    if resolve_error:
        return {
            "success": False,
            "error": resolve_error,
            "suggested_action": "인수인의견 데이터 생성 스크립트를 실행하거나 UNDERWRITER_DATA_PATH를 설정하세요.",
        }
    jsonl_path = resolved_path
    category = category.strip().lower() if isinstance(category, str) else category

    try:
        top_k = int(top_k) if top_k is not None else 5
    except (TypeError, ValueError):
        top_k = 5
    try:
        max_chars = int(max_chars) if max_chars is not None else 800
    except (TypeError, ValueError):
        max_chars = 800
    try:
        min_section_length = int(min_section_length) if min_section_length is not None else 0
    except (TypeError, ValueError):
        min_section_length = 0
    try:
        max_text_chars = int(max_text_chars) if max_text_chars is not None else 2000
    except (TypeError, ValueError):
        max_text_chars = 2000
    try:
        min_score = float(min_score) if min_score is not None else 0.05
    except (TypeError, ValueError):
        min_score = 0.05
    if isinstance(return_patterns, str):
        return_patterns = return_patterns.strip().lower() in ("true", "1", "yes", "y")

    is_valid, error = _validate_file_path(
        jsonl_path,
        allowed_extensions=[".jsonl"],
        require_temp_dir=True,
    )
    if not is_valid:
        return {
            "success": False,
            "error": error,
            "suggested_action": "인수인의견 데이터 파일을 temp/ 하위로 이동해 주세요.",
        }

    if not os.path.exists(jsonl_path):
        return {
            "success": False,
            "error": f"파일을 찾을 수 없습니다: {jsonl_path}",
            "suggested_action": "인수인의견 데이터 파일 경로를 확인하세요.",
        }

    index, index_error = _get_underwriter_tfidf_index(
        jsonl_path,
        min_n=3,
        max_n=5,
        max_text_chars=max_text_chars,
    )
    if index_error:
        return {"success": False, "error": index_error}

    query_text = _normalize_similarity_text(str(query), max_chars=max_text_chars)
    query_vec, query_norm = _vectorize_query(query_text, index["idf"], min_n=3, max_n=5)

    results = []
    for entry, (vec, norm) in zip(index["entries"], index["vectors"]):
        section_text = entry.get("section_text") or ""
        section_title = entry.get("section_title") or ""
        combined_text = f"{section_title}\n{section_text}"

        if corp_name and corp_name not in entry.get("corp_name", ""):
            continue

        if min_section_length and entry.get("section_length", 0) < min_section_length:
            continue

        if category:
            ok, _ = _match_underwriter_category(combined_text, category)
            if not ok:
                continue

        score = _cosine_similarity(query_vec, query_norm, vec, norm)
        if score < min_score:
            continue

        snippet = _extract_snippet(section_text, [], max_chars=max_chars)
        results.append(
            {
                "corp_name": entry.get("corp_name"),
                "rcept_no": entry.get("rcept_no"),
                "report_nm": entry.get("report_nm"),
                "rcept_dt": entry.get("rcept_dt"),
                "section_title": section_title,
                "section_length": entry.get("section_length"),
                "quality_score": entry.get("quality_score"),
                "snippet": snippet,
                "score": round(score, 6),
            }
        )

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    if top_k:
        results = results[:top_k]

    patterns = []
    if return_patterns:
        seen = set()
        for item in results:
            template = _generalize_underwriter_text(item.get("snippet"), item.get("corp_name"))
            if template and template not in seen:
                patterns.append(template)
                seen.add(template)

    response = {
        "success": True,
        "source_path": jsonl_path,
        "filters": {
            "query": query,
            "category": category,
            "corp_name": corp_name,
            "top_k": top_k,
            "min_score": min_score,
            "max_chars": max_chars,
            "min_section_length": min_section_length,
            "max_text_chars": max_text_chars,
        },
        "results": results,
        "patterns": patterns,
    }

    if output_filename:
        sanitized_name = _sanitize_filename(output_filename)
        if not sanitized_name.endswith(".json"):
            sanitized_name += ".json"
        output_dir = PROJECT_ROOT / "temp"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / sanitized_name
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(response, f, ensure_ascii=False, indent=2)
            response["output_file"] = str(output_path)
        except OSError as e:
            logger.error(f"Failed to write underwriter similarity output: {e}", exc_info=True)
            response["output_file_error"] = str(e)

    return response


def execute_extract_pdf_market_evidence(
    pdf_path: str,
    max_pages: int = 30,
    max_results: int = 20,
    keywords: List[str] = None,
) -> Dict[str, Any]:
    """PDF에서 시장규모 근거 문장을 추출"""
    is_valid, error = _validate_file_path(pdf_path, allowed_extensions=[".pdf"], require_temp_dir=True)
    if not is_valid:
        return {"success": False, "error": error}

    if not os.path.exists(pdf_path):
        return {"success": False, "error": f"파일을 찾을 수 없습니다: {pdf_path}"}

    try:
        max_pages = int(max_pages) if max_pages is not None else 30
    except (TypeError, ValueError):
        max_pages = 30
    try:
        max_results = int(max_results) if max_results is not None else 20
    except (TypeError, ValueError):
        max_results = 20

    base_keywords = [
        "시장",
        "규모",
        "전망",
        "성장",
        "성장률",
        "CAGR",
        "TAM",
        "SAM",
        "SOM",
        "수요",
        "가격",
        "매출",
        "톤",
        "kg",
        "달러",
    ]
    if keywords:
        base_keywords.extend([str(k) for k in keywords if k])

    import fitz  # PyMuPDF

    doc = None
    try:
        try:
            file_hash = compute_file_hash(Path(pdf_path))
            payload = {
                "version": CACHE_VERSION,
                "file_hash": file_hash,
                "max_pages": max_pages,
                "max_results": max_results,
                "keywords": base_keywords,
                "tool": "extract_pdf_market_evidence",
            }
            cache_key = compute_payload_hash(payload)
            cache_dir = get_cache_dir("market_evidence", "shared")
            cache_path = cache_dir / f"{cache_key}.json"
            cached = load_json(cache_path)
            if cached:
                cached["cache_hit"] = True
                return cached
        except Exception:
            cache_path = None

        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        pages_to_read = min(total_pages, max_pages)

        evidence = []
        seen = set()

        for page_idx in range(pages_to_read):
            page = doc[page_idx]
            text = page.get_text()
            for line in text.splitlines():
                line_text = _normalize_text(line)
                if not line_text:
                    continue

                if not any(keyword in line_text for keyword in base_keywords):
                    continue

                if not re.search(r"\d", line_text):
                    continue

                numbers = _extract_numeric_phrases(line_text)
                if not numbers:
                    continue

                key = (page_idx + 1, line_text)
                if key in seen:
                    continue
                seen.add(key)

                matched = [kw for kw in base_keywords if kw in line_text]
                evidence.append(
                    {
                        "page": page_idx + 1,
                        "text": line_text,
                        "numbers": numbers,
                        "matched_keywords": matched[:10],
                        "source": f"PDF p.{page_idx + 1}",
                    }
                )

                if len(evidence) >= max_results:
                    break
            if len(evidence) >= max_results:
                break

        warnings = []
        if not evidence:
            warnings.append("시장규모 근거 문장을 찾지 못했습니다. 키워드나 페이지 범위를 확장하세요.")

        result = {
            "success": True,
            "file_path": pdf_path,
            "total_pages": total_pages,
            "pages_read": pages_to_read,
            "evidence": evidence,
            "evidence_count": len(evidence),
            "warnings": warnings,
            "cache_hit": False,
            "cached_at": datetime.utcnow().isoformat(),
        }
        try:
            file_hash = compute_file_hash(Path(pdf_path))
            payload = {
                "version": CACHE_VERSION,
                "file_hash": file_hash,
                "max_pages": max_pages,
                "max_results": max_results,
                "keywords": base_keywords,
                "tool": "extract_pdf_market_evidence",
            }
            cache_key = compute_payload_hash(payload)
            cache_dir = get_cache_dir("market_evidence", "shared")
            cache_path = cache_dir / f"{cache_key}.json"
            save_json(cache_path, result)
        except Exception:
            pass

        return result
    except Exception as e:
        logger.error(f"PDF market evidence extraction failed: {e}", exc_info=True)
        return {"success": False, "error": f"시장규모 근거 추출 실패: {str(e)}"}
    finally:
        if doc:
            doc.close()


def execute_fetch_underwriter_opinion_data(
    start_date: str = None,
    end_date: str = None,
    lookback_days: int = 365,
    out_dir: str = None,
    max_items: int = 200,
    last_only: bool = True,
    include_corrections: bool = False,
    min_length: int = 600,
    min_score: float = 3.0,
    api_key: str = None,
) -> Dict[str, Any]:
    """인수인의견 원천 데이터 수집 및 JSONL 생성"""
    api_key = api_key or os.getenv("DART_API_KEY")
    if not api_key:
        return {
            "success": False,
            "error": "API 키가 필요합니다. tool 입력 또는 환경변수로 설정하세요.",
        }

    today = datetime.now().date()
    if end_date:
        end_str = end_date.strip()
    else:
        end_str = today.strftime("%Y%m%d")

    if start_date:
        start_str = start_date.strip()
    else:
        try:
            lookback_days = int(lookback_days) if lookback_days is not None else 365
        except (TypeError, ValueError):
            lookback_days = 365
        start_str = (today - timedelta(days=lookback_days)).strftime("%Y%m%d")

    if not re.match(r"^\d{8}$", start_str) or not re.match(r"^\d{8}$", end_str):
        return {"success": False, "error": "start_date/end_date 형식은 YYYYMMDD 이어야 합니다."}

    if out_dir:
        out_path = Path(out_dir)
        if not out_path.is_absolute():
            out_path = (PROJECT_ROOT / out_path).resolve()
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = (PROJECT_ROOT / "temp" / f"underwriter_opinion_{timestamp}").resolve()

    temp_root = (PROJECT_ROOT / "temp").resolve()
    try:
        out_path.relative_to(temp_root)
    except ValueError:
        return {"success": False, "error": "출력 디렉토리는 temp/ 하위여야 합니다."}

    out_path.mkdir(parents=True, exist_ok=True)

    try:
        max_items = int(max_items) if max_items is not None else 200
    except (TypeError, ValueError):
        max_items = 200
    try:
        min_length = int(min_length) if min_length is not None else 600
    except (TypeError, ValueError):
        min_length = 600
    try:
        min_score = float(min_score) if min_score is not None else 3.0
    except (TypeError, ValueError):
        min_score = 3.0

    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "dart_extract_underwriter_opinion.py"),
        "--start",
        start_str,
        "--end",
        end_str,
        "--out",
        str(out_path),
        "--api-key",
        api_key,
        "--max-items",
        str(max_items),
        "--min-length",
        str(min_length),
        "--min-score",
        str(min_score),
    ]

    if last_only:
        cmd.append("--last-only")
    if include_corrections:
        cmd.append("--include-corrections")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError as e:
        return {"success": False, "error": f"데이터 수집 실행 실패: {str(e)}"}

    if result.returncode != 0:
        err_tail = (result.stderr or "").strip().splitlines()[-5:]
        return {
            "success": False,
            "error": "데이터 수집 실패",
            "details": "\n".join(err_tail),
        }

    output_file = out_path / "underwriter_opinion.jsonl"
    if not output_file.exists():
        return {"success": False, "error": "결과 JSONL 파일을 찾을 수 없습니다."}

    return {
        "success": True,
        "output_dir": str(out_path),
        "output_file": str(output_file),
        "start_date": start_str,
        "end_date": end_str,
        "max_items": max_items,
    }


EXECUTORS = {
    "search_underwriter_opinion": execute_search_underwriter_opinion,
    "search_underwriter_opinion_similar": execute_search_underwriter_opinion_similar,
    "extract_pdf_market_evidence": execute_extract_pdf_market_evidence,
    "fetch_underwriter_opinion_data": execute_fetch_underwriter_opinion_data,
}
