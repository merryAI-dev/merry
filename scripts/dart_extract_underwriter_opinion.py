#!/usr/bin/env python3
"""
Extracts the "Underwriter's opinion (analyst evaluation)" section from
DART securities registration statements.

Requirements:
- DART API key (environment variable DART_API_KEY or --api-key)
"""
import argparse
import hashlib
import io
import json
import math
import os
import re
import sys
import time
import zipfile
from collections import Counter
from datetime import datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover - optional dependency
    fitz = None


LIST_API_URL = "https://opendart.fss.or.kr/api/list.json"
DOCUMENT_API_URL = "https://opendart.fss.or.kr/api/document.xml"

UNDERWRITER_RE = re.compile(
    r"인수인(?:의)?\s*의견(?:\s*\([^)]*평가\s*의견[^)]*\))?",
    re.IGNORECASE,
)

UNDERWRITER_HEADING_RE = re.compile(
    r"^(?:제\s*\d+\s*장|[IVXLC]+|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]|\d+)[\.\)]?\s*인수인",
    re.IGNORECASE,
)

HEADING_RE = re.compile(
    r"^(?:제\s*\d+\s*장|[IVXLC]+|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ])[\.\)]?\s*\S",
    re.IGNORECASE,
)

AMENDMENT_PREFIX_RE = re.compile(r"^\[", re.IGNORECASE)
EXCLUDED_REPORT_RE = re.compile(r"(채무증권|합병|분할|투자계약증권|증권예탁증권)", re.IGNORECASE)
BASE_REPORT_TOKEN = "증권신고서(지분증권)"

CORRECTION_MARKERS = ("정정 전", "정정 후", "정정사항")
QUALITY_PHRASES = (
    "공모가격",
    "희망공모가액",
    "공모가액",
    "유사기업",
    "평가방법",
    "상대가치",
    "PER",
    "DCF",
    "대표주관회사",
    "주관회사",
    "수요예측",
    "주당 평가가액",
)


def log(message):
    print(message, file=sys.stderr)


class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip_depth = 0
        self.last_was_newline = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip_depth += 1
            return
        if tag in ("br", "p", "div", "tr", "td", "th", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._append_newline()

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            if self.skip_depth > 0:
                self.skip_depth -= 1
            return
        if tag in ("p", "div", "tr", "td", "th", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._append_newline()

    def handle_data(self, data):
        if self.skip_depth > 0:
            return
        if data:
            self.parts.append(data)
            self.last_was_newline = False

    def _append_newline(self):
        if not self.last_was_newline:
            self.parts.append("\n")
            self.last_was_newline = True

    def get_text(self):
        return "".join(self.parts)


def decode_bytes(data):
    for encoding in ("utf-8", "cp949", "euc-kr"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def html_to_text(html_str):
    parser = HTMLTextExtractor()
    parser.feed(html_str)
    text = parser.get_text()
    return normalize_text(text)


def normalize_text(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def normalize_similarity_text(text, max_chars):
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\d", "0", text)
    text = text.strip()
    if max_chars and len(text) > max_chars:
        text = text[:max_chars]
    return text


def char_ngram_counts(text, min_n=3, max_n=5):
    counts = Counter()
    length = len(text)
    for n in range(min_n, max_n + 1):
        if length < n:
            continue
        for i in range(length - n + 1):
            counts[text[i:i + n]] += 1
    return counts


def tfidf_vectors(texts, min_n=3, max_n=5):
    counts_list = [char_ngram_counts(text, min_n=min_n, max_n=max_n) for text in texts]
    df = Counter()
    for counts in counts_list:
        df.update(counts.keys())

    doc_count = len(counts_list)
    idf = {term: math.log((1 + doc_count) / (1 + freq)) + 1 for term, freq in df.items()}

    vectors = []
    for counts in counts_list:
        vec = {}
        norm = 0.0
        for term, tf in counts.items():
            weight = (1 + math.log(tf)) * idf[term]
            vec[term] = weight
            norm += weight * weight
        vectors.append((vec, math.sqrt(norm)))
    return vectors


def cosine_similarity(vec_a, norm_a, vec_b, norm_b):
    if norm_a == 0 or norm_b == 0:
        return 0.0
    if len(vec_a) > len(vec_b):
        vec_a, vec_b = vec_b, vec_a
        norm_a, norm_b = norm_b, norm_a
    dot = 0.0
    for term, weight in vec_a.items():
        dot += weight * vec_b.get(term, 0.0)
    return dot / (norm_a * norm_b)


def is_heading_line(line):
    if not line:
        return False
    if len(line) > 120:
        return False
    return bool(HEADING_RE.match(line))


def score_underwriter_section(title, text):
    score = 0.0
    if UNDERWRITER_HEADING_RE.match(title):
        score += 2.5
    if UNDERWRITER_RE.search(title):
        score += 1.0

    score += min(len(text) / 1200.0, 4.0)

    phrase_hits = 0
    for phrase in QUALITY_PHRASES:
        if phrase in text:
            phrase_hits += 1
    score += phrase_hits * 0.4

    if any(marker in text for marker in CORRECTION_MARKERS):
        score -= 2.0
    if "정정" in title:
        score -= 1.0
    if any(word in title for word in ("목차", "차례")):
        score -= 1.5

    return score


def find_underwriter_sections(text):
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return []

    toc_indices = [i for i, line in enumerate(lines) if "목차" in line or "차례" in line]

    candidates = [i for i, line in enumerate(lines) if UNDERWRITER_RE.search(line)]

    if not candidates:
        return []

    filtered = []
    for idx in candidates:
        if any(toc_idx <= idx <= toc_idx + 30 for toc_idx in toc_indices):
            continue
        filtered.append(idx)

    if filtered:
        candidates = filtered

    sections = []
    seen_ranges = set()
    for idx in candidates:
        start_idx = idx
        end_idx = None
        for i in range(start_idx + 1, len(lines)):
            if is_heading_line(lines[i]):
                end_idx = i
                break

        if end_idx is None:
            end_idx = len(lines)

        range_key = (start_idx, end_idx)
        if range_key in seen_ranges:
            continue
        seen_ranges.add(range_key)

        section_lines = lines[start_idx:end_idx]
        section_text = normalize_text("\n".join(section_lines))

        notes = []
        if len(candidates) > 1:
            notes.append("multiple_heading_hits")
        if end_idx == len(lines):
            notes.append("no_next_heading")
        if any(marker in section_text for marker in CORRECTION_MARKERS):
            notes.append("correction_markers")
        if len(section_text) < 200:
            notes.append("short_section")

        score = score_underwriter_section(lines[start_idx], section_text)
        confidence = max(0.0, min(1.0, 0.4 + (score * 0.15)))

        sections.append({
            "section_title": lines[start_idx],
            "section_text": section_text,
            "confidence": confidence,
            "quality_score": score,
            "notes": notes,
        })

    return sections


def build_url(base_url, params):
    return f"{base_url}?{urlencode(params)}"


def http_get(url, timeout=30):
    req = Request(url, headers={"User-Agent": "dart-extractor/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_json(url, params, timeout=30):
    data = http_get(build_url(url, params), timeout=timeout)
    return json.loads(data.decode("utf-8"))


def parse_error_xml(data):
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return {"status": None, "message": "invalid_xml"}
    status = root.findtext("status") or root.findtext(".//status")
    message = root.findtext("message") or root.findtext(".//message")
    return {"status": status, "message": message}


def iter_date_ranges(start_date, end_date, max_days=90):
    current = start_date
    while current <= end_date:
        chunk_end = min(current + timedelta(days=max_days - 1), end_date)
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


def list_disclosures(api_key, start_date, end_date, corp_codes, page_count, sleep_sec, last_reprt_at):
    disclosures = {}
    errors = []

    date_ranges = [(start_date, end_date)]
    if not corp_codes:
        date_ranges = list(iter_date_ranges(start_date, end_date))

    for bgn, end in date_ranges:
        for corp_code in corp_codes or [None]:
            page_no = 1
            while True:
                params = {
                    "crtfc_key": api_key,
                    "bgn_de": bgn.strftime("%Y%m%d"),
                    "end_de": end.strftime("%Y%m%d"),
                    "pblntf_ty": "C",
                    "last_reprt_at": last_reprt_at,
                    "page_no": page_no,
                    "page_count": page_count,
                }
                if corp_code:
                    params["corp_code"] = corp_code

                try:
                    data = fetch_json(LIST_API_URL, params)
                except Exception as exc:
                    errors.append({
                        "type": "list_api_error",
                        "error": str(exc),
                        "params": params,
                    })
                    break

                if data.get("status") != "000":
                    errors.append({
                        "type": "list_api_status",
                        "status": data.get("status"),
                        "message": data.get("message"),
                        "params": params,
                    })
                    break

                items = data.get("list", []) or []
                if not items:
                    break

                for item in items:
                    rcept_no = item.get("rcept_no")
                    if rcept_no:
                        disclosures[rcept_no] = item

                total_page = int(data.get("total_page") or 0)
                if total_page and page_no >= total_page:
                    break
                page_no += 1
                if sleep_sec:
                    time.sleep(sleep_sec)

    return disclosures, errors


def iter_document_files(zip_obj):
    for info in zip_obj.infolist():
        if getattr(info, "is_dir", lambda: False)():
            continue
        name = info.filename
        lower_name = name.lower()
        if lower_name.endswith((".html", ".htm", ".pdf", ".xml")):
            yield info


def extract_texts_from_zip(data):
    texts = []
    errors = []

    with zipfile.ZipFile(io.BytesIO(data)) as zip_obj:
        candidates = list(iter_document_files(zip_obj))
        if not candidates:
            return texts, [{"reason": "no_supported_file"}]

        for info in candidates:
            name = info.filename
            lower_name = name.lower()
            raw = zip_obj.read(info)

            if lower_name.endswith((".html", ".htm")):
                html_str = decode_bytes(raw)
                text = html_to_text(html_str)
                if text:
                    texts.append({"text": text, "source": {"file": name, "type": "html"}})
                else:
                    errors.append({"reason": "html_empty", "file": name})
                continue

            if lower_name.endswith(".pdf"):
                if fitz is None:
                    errors.append({"reason": "pymupdf_not_installed", "file": name})
                    continue
                doc = fitz.open(stream=raw, filetype="pdf")
                text = "\n".join(page.get_text("text") for page in doc)
                text = normalize_text(text)
                if text:
                    texts.append({"text": text, "source": {"file": name, "type": "pdf"}})
                else:
                    errors.append({"reason": "pdf_empty", "file": name})
                continue

            if lower_name.endswith(".xml"):
                xml_str = decode_bytes(raw)
                text = html_to_text(xml_str)
                if text:
                    texts.append({"text": text, "source": {"file": name, "type": "xml"}})
                else:
                    errors.append({"reason": "xml_empty", "file": name})
                continue

    return texts, errors


def fingerprint_text(text):
    normalized = re.sub(r"\s+", " ", text).strip()
    digest = hashlib.sha1(normalized[:5000].encode("utf-8")).hexdigest()
    return digest


def dedupe_sections(sections):
    seen = set()
    unique = []
    for section in sections:
        fingerprint = fingerprint_text(section["section_text"])
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(section)
    return unique


def is_target_report(report_nm, include_corrections):
    if BASE_REPORT_TOKEN not in report_nm:
        return False
    if EXCLUDED_REPORT_RE.search(report_nm):
        return False
    if not include_corrections and AMENDMENT_PREFIX_RE.search(report_nm):
        return False
    return True


def apply_similarity_scoring(
    sample_text,
    sections,
    max_chars,
    min_n=3,
    max_n=5,
    window_chars=0,
    window_stride=0,
):
    if not sample_text or not sections:
        return
    normalized_sample = normalize_similarity_text(sample_text, max_chars)
    if not normalized_sample:
        return
    use_window = window_chars and window_chars > 0
    stride = window_stride if window_stride and window_stride > 0 else max(1, window_chars // 2) if use_window else 0

    for section in sections:
        normalized_text = normalize_similarity_text(section["section_text"], max_chars)
        if not normalized_text:
            section["similarity"] = 0.0
            continue

        if use_window and len(normalized_text) > window_chars:
            windows = [
                normalized_text[i:i + window_chars]
                for i in range(0, len(normalized_text) - window_chars + 1, stride)
            ]
        else:
            windows = [normalized_text]

        vectors = tfidf_vectors([normalized_sample] + windows, min_n=min_n, max_n=max_n)
        sample_vec, sample_norm = vectors[0]
        max_sim = 0.0
        for vec, norm in vectors[1:]:
            sim = cosine_similarity(sample_vec, sample_norm, vec, norm)
            if sim > max_sim:
                max_sim = sim
        section["similarity"] = max_sim


def download_document(api_key, rcept_no, timeout=60):
    params = {"crtfc_key": api_key, "rcept_no": rcept_no}
    url = build_url(DOCUMENT_API_URL, params)
    data = http_get(url, timeout=timeout)
    if not zipfile.is_zipfile(io.BytesIO(data)):
        error = parse_error_xml(data)
        return None, {"reason": "not_zip", "error": error}
    return data, None


def write_jsonl(path, rows):
    with open(path, "a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract underwriter opinion sections from DART filings",
    )
    parser.add_argument("--start", required=True, help="Start date (YYYYMMDD)")
    parser.add_argument("--end", required=True, help="End date (YYYYMMDD)")
    parser.add_argument("--out", default="temp/dart_underwriter_opinion", help="Output directory")
    parser.add_argument("--api-key", default=None, help="DART API key")
    parser.add_argument("--corp-code", action="append", help="Corp code (8 digits, repeatable)")
    parser.add_argument("--page-count", type=int, default=100, help="Items per page (1~100)")
    parser.add_argument("--sleep", type=float, default=0.2, help="Delay between requests (seconds)")
    parser.add_argument("--max-items", type=int, default=0, help="Max items to process (0=unlimited)")
    parser.add_argument("--min-length", type=int, default=600, help="Minimum section length to keep")
    parser.add_argument("--min-score", type=float, default=3.0, help="Minimum quality score to keep")
    parser.add_argument("--max-sections", type=int, default=3, help="Max sections per filing (0=unlimited)")
    parser.add_argument("--sample", default=None, help="Sample section for similarity ranking")
    parser.add_argument("--min-similarity", type=float, default=0.0, help="Minimum similarity to keep")
    parser.add_argument("--similarity-weight", type=float, default=4.0, help="Weight for similarity score")
    parser.add_argument(
        "--similarity-max-chars",
        type=int,
        default=20000,
        help="Max chars per text when computing similarity",
    )
    parser.add_argument(
        "--similarity-window-chars",
        type=int,
        default=0,
        help="Window size for similarity matching (0=disabled)",
    )
    parser.add_argument(
        "--similarity-stride",
        type=int,
        default=0,
        help="Stride for similarity windows (0=auto)",
    )
    parser.add_argument(
        "--last-only",
        action="store_true",
        help="Only fetch latest filings (DART last_reprt_at=Y)",
    )
    parser.add_argument(
        "--include-corrections",
        action="store_true",
        help="Include amended/final reports such as [기재정정] or [발행조건확정]",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if load_dotenv:
        load_dotenv()

    api_key = args.api_key or os.getenv("DART_API_KEY")
    if not api_key:
        raise SystemExit("DART_API_KEY is required. Use --api-key or set the env var.")

    start_date = datetime.strptime(args.start, "%Y%m%d")
    end_date = datetime.strptime(args.end, "%Y%m%d")

    os.makedirs(args.out, exist_ok=True)
    results_path = os.path.join(args.out, "underwriter_opinion.jsonl")
    missing_path = os.path.join(args.out, "missing.jsonl")
    errors_path = os.path.join(args.out, "errors.jsonl")
    meta_path = os.path.join(args.out, "meta.json")

    sample_text = None
    if args.sample:
        try:
            with open(args.sample, "r", encoding="utf-8") as f:
                sample_text = f.read()
        except OSError as exc:
            log(f"Warning: failed to read sample file: {exc}")

    disclosures, list_errors = list_disclosures(
        api_key=api_key,
        start_date=start_date,
        end_date=end_date,
        corp_codes=args.corp_code,
        page_count=args.page_count,
        sleep_sec=args.sleep,
        last_reprt_at="Y" if args.last_only else "N",
    )

    if list_errors:
        write_jsonl(errors_path, list_errors)

    items = []
    for item in disclosures.values():
        report_nm = item.get("report_nm", "")
        if is_target_report(report_nm, args.include_corrections):
            items.append(item)

    items.sort(key=lambda x: x.get("rcept_dt", ""))
    if args.max_items and args.max_items > 0:
        items = items[: args.max_items]

    processed = 0
    extracted_reports = 0
    extracted_sections = 0
    missing = 0
    errors = 0
    total_sections_found = 0
    total_sections_filtered = 0

    for item in items:
        rcept_no = item.get("rcept_no")
        report_nm = item.get("report_nm")
        corp_name = item.get("corp_name")
        rcept_dt = item.get("rcept_dt")

        doc_data, doc_error = download_document(api_key, rcept_no)
        if doc_error:
            write_jsonl(errors_path, [{
                "type": "document_download_error",
                "rcept_no": rcept_no,
                "error": doc_error,
                "report_nm": report_nm,
                "corp_name": corp_name,
            }])
            errors += 1
            continue

        texts, parse_errors = extract_texts_from_zip(doc_data)
        if not texts:
            write_jsonl(errors_path, [{
                "type": "document_parse_error",
                "rcept_no": rcept_no,
                "error": parse_errors,
                "report_nm": report_nm,
                "corp_name": corp_name,
            }])
            errors += 1
            continue

        candidates = []
        for entry in texts:
            for section in find_underwriter_sections(entry["text"]):
                section["source"] = entry["source"]
                candidates.append(section)

        candidates = dedupe_sections(candidates)
        total_sections_found += len(candidates)

        if candidates:
            for section in candidates:
                section["heuristic_score"] = section["quality_score"]
            if sample_text:
                apply_similarity_scoring(
                    sample_text=sample_text,
                    sections=candidates,
                    max_chars=args.similarity_max_chars,
                    window_chars=args.similarity_window_chars,
                    window_stride=args.similarity_stride,
                )
                for section in candidates:
                    similarity = section.get("similarity", 0.0)
                    section["quality_score"] += args.similarity_weight * similarity

        candidates.sort(
            key=lambda sec: (sec["quality_score"], len(sec["section_text"])),
            reverse=True,
        )

        kept = [
            sec for sec in candidates
            if len(sec["section_text"]) >= args.min_length
            and sec["quality_score"] >= args.min_score
        ]
        if sample_text and args.min_similarity > 0:
            kept = [
                sec for sec in kept
                if sec.get("similarity", 0.0) >= args.min_similarity
            ]

        if args.max_sections and args.max_sections > 0:
            kept = kept[: args.max_sections]

        total_sections_filtered += max(0, len(candidates) - len(kept))

        if not kept:
            reason = "section_not_found" if not candidates else "filtered_out"
            missing_entry = {
                "rcept_no": rcept_no,
                "report_nm": report_nm,
                "corp_name": corp_name,
                "rcept_dt": rcept_dt,
                "reason": reason,
                "candidate_count": len(candidates),
            }
            if candidates:
                best = candidates[0]
                missing_entry["best_candidate"] = {
                    "section_title": best["section_title"],
                    "section_length": len(best["section_text"]),
                    "quality_score": best["quality_score"],
                    "heuristic_score": best.get("heuristic_score", best["quality_score"]),
                    "similarity": best.get("similarity", 0.0),
                    "source": best.get("source"),
                }
            write_jsonl(missing_path, [missing_entry])
            missing += 1
        else:
            extracted_reports += 1
            extracted_sections += len(kept)
            for rank, section in enumerate(kept, start=1):
                write_jsonl(results_path, [{
                    "rcept_no": rcept_no,
                    "report_nm": report_nm,
                    "corp_name": corp_name,
                    "rcept_dt": rcept_dt,
                    "section_rank": rank,
                    "section_title": section["section_title"],
                    "section_text": section["section_text"],
                    "section_length": len(section["section_text"]),
                    "quality_score": section["quality_score"],
                    "heuristic_score": section.get("heuristic_score", section["quality_score"]),
                    "similarity": section.get("similarity", 0.0),
                    "confidence": section["confidence"],
                    "notes": section["notes"],
                    "source": section.get("source"),
                }])

        processed += 1
        if args.sleep:
            time.sleep(args.sleep)

    meta = {
        "start": args.start,
        "end": args.end,
        "corp_codes": args.corp_code or [],
        "total_candidates": len(items),
        "processed": processed,
        "extracted_reports": extracted_reports,
        "extracted_sections": extracted_sections,
        "missing": missing,
        "errors": errors,
        "min_length": args.min_length,
        "min_score": args.min_score,
        "max_sections": args.max_sections,
        "include_corrections": args.include_corrections,
        "last_only": args.last_only,
        "sample": args.sample,
        "min_similarity": args.min_similarity,
        "similarity_weight": args.similarity_weight,
        "similarity_max_chars": args.similarity_max_chars,
        "similarity_window_chars": args.similarity_window_chars,
        "similarity_stride": args.similarity_stride,
        "total_sections_found": total_sections_found,
        "total_sections_filtered": total_sections_filtered,
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    log(
        "Done: processed "
        f"{processed}, extracted_reports {extracted_reports}, "
        f"extracted_sections {extracted_sections}, missing {missing}, errors {errors}"
    )
    log(f"Output: {results_path}")


if __name__ == "__main__":
    main()
