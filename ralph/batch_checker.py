"""
PDF 문서 일괄 조건 검사 CLI (Vercel 우회용 로컬 실행).

사용:
    python ralph/batch_checker.py <pdf_folder> --conditions "조건1" "조건2" ...
    python ralph/batch_checker.py <pdf_folder> --conditions-file conditions.txt
    python ralph/batch_checker.py <pdf_folder> --conditions "조건1" "조건2" --output results.csv

출력:
    results.csv  — filename, company_name, 조건1_result, 조건1_evidence, 조건2_result, ...
    콘솔에 진행상황 출력

환경변수 (선택):
    RALPH_VLM_NOVA_MODEL_ID  (기본: us.amazon.nova-pro-v1:0)
    RALPH_VLM_NOVA_REGION    (기본: us-east-1)
    RALPH_USE_VLM            (기본: true)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path


def _setup_path() -> None:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def process_pdf(pdf_path: str, conditions: list[str], model_id: str, region: str, use_vlm: bool) -> dict:
    """
    단일 PDF를 처리: 텍스트 추출 → 조건 검사.
    playground_parser와 condition_checker 로직을 직접 호출.
    """
    from ralph.playground_parser import (
        extract_text,
        assess_text_quality,
        render_first_page,
        render_pages,
        analyze_pages,
        call_nova_visual,
        build_presentation_prompt,
        _PROMPT_OCR,
    )
    from ralph.condition_checker import check_conditions_nova

    model_lite = os.getenv("RALPH_VLM_NOVA_LITE_MODEL_ID", "us.amazon.nova-lite-v1:0")

    # 1. 텍스트 추출
    text, pages, blocks = extract_text(pdf_path)
    quality, is_poor, is_fragmented = assess_text_quality(text, blocks, page_count=pages)

    extracted_text = ""
    method = "pymupdf"

    # 2. VLM 처리 (필요한 경우)
    if use_vlm and is_poor:
        try:
            img = render_first_page(pdf_path)
            vd = call_nova_visual(img, model_lite, region, _PROMPT_OCR)
            extracted_text = vd.get("readable_text", "") or ""
            method = "nova_hybrid"
        except Exception as e:
            extracted_text = ""
            method = f"nova_error: {e}"
    elif use_vlm and is_fragmented:
        try:
            page_images = render_pages(pdf_path, max_pages=10, dpi=100)
            pages_info = analyze_pages(pdf_path, max_pages=10)
            prompt = build_presentation_prompt(pages_info)
            vd = call_nova_visual(page_images, model_id, region, prompt, max_tokens=5000)
            extracted_text = vd.get("readable_text", "") or ""
            method = "nova_presentation"
        except Exception as e:
            extracted_text = ""
            method = f"nova_error: {e}"

    # 텍스트 합산 (Nova 결과 우선, PyMuPDF 보완)
    full_text = "\n\n".join(filter(None, [extracted_text, text]))

    # 3. 조건 검사
    check = check_conditions_nova(full_text, conditions, model_id, region)

    return {
        "method": method,
        "pages": pages,
        "company_name": check.get("company_name"),
        "conditions": check.get("conditions", []),
        "error": check.get("error") if not check.get("ok", True) else None,
    }


def main() -> None:
    _setup_path()

    parser = argparse.ArgumentParser(description="PDF 일괄 조건 검사")
    parser.add_argument("pdf_folder", help="PDF 파일들이 있는 폴더 경로")
    parser.add_argument("--conditions", nargs="+", help="검사 조건 목록")
    parser.add_argument("--conditions-file", help="조건 목록 텍스트 파일 (줄당 1개 조건)")
    parser.add_argument("--output", default="results.csv", help="출력 CSV 파일명 (기본: results.csv)")
    parser.add_argument("--no-vlm", action="store_true", help="VLM 사용 안 함 (PyMuPDF만)")
    parser.add_argument("--delay", type=float, default=1.0, help="파일 간 대기 시간(초), API 스로틀링 방지")
    args = parser.parse_args()

    # 조건 로드
    conditions: list[str] = []
    if args.conditions_file:
        with open(args.conditions_file, encoding="utf-8") as f:
            conditions = [ln.strip() for ln in f if ln.strip()]
    if args.conditions:
        conditions.extend(args.conditions)

    if not conditions:
        print("오류: --conditions 또는 --conditions-file 로 조건을 지정하세요", file=sys.stderr)
        sys.exit(1)

    # PDF 파일 목록
    folder = Path(args.pdf_folder)
    pdf_files = sorted(folder.glob("*.pdf"))
    if not pdf_files:
        print(f"오류: {folder} 에 PDF 파일이 없습니다", file=sys.stderr)
        sys.exit(1)

    model_id = os.getenv("RALPH_VLM_NOVA_MODEL_ID", "us.amazon.nova-pro-v1:0")
    region = os.getenv("RALPH_VLM_NOVA_REGION", "us-east-1")
    use_vlm = not args.no_vlm

    print(f"▶ {len(pdf_files)}개 파일 처리 시작")
    print(f"  조건 {len(conditions)}개: {conditions}")
    print(f"  출력: {args.output}\n")

    # CSV 헤더 구성
    fieldnames = ["filename", "company_name", "method", "pages", "error"]
    for c in conditions:
        short = c[:30].replace(" ", "_")
        fieldnames += [f"{short}_result", f"{short}_evidence"]

    rows: list[dict] = []
    ok_count = 0
    err_count = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        name = pdf_path.name
        print(f"[{i:3d}/{len(pdf_files)}] {name} … ", end="", flush=True)
        t0 = time.time()

        try:
            res = process_pdf(str(pdf_path), conditions, model_id, region, use_vlm)
            elapsed = time.time() - t0

            row: dict = {
                "filename": name,
                "company_name": res.get("company_name") or "",
                "method": res.get("method", ""),
                "pages": res.get("pages", ""),
                "error": res.get("error") or "",
            }

            cond_results = res.get("conditions", [])
            for j, c in enumerate(conditions):
                short = c[:30].replace(" ", "_")
                if j < len(cond_results):
                    cr = cond_results[j]
                    row[f"{short}_result"] = "✓" if cr.get("result") else "✗"
                    row[f"{short}_evidence"] = cr.get("evidence", "")
                else:
                    row[f"{short}_result"] = ""
                    row[f"{short}_evidence"] = ""

            rows.append(row)
            ok_count += 1
            print(f"완료 ({elapsed:.1f}s) — {res.get('company_name') or '기업명 미확인'}")

        except Exception as e:
            elapsed = time.time() - t0
            row = {
                "filename": name,
                "company_name": "",
                "method": "error",
                "pages": "",
                "error": str(e),
            }
            for c in conditions:
                short = c[:30].replace(" ", "_")
                row[f"{short}_result"] = ""
                row[f"{short}_evidence"] = ""
            rows.append(row)
            err_count += 1
            print(f"오류 ({elapsed:.1f}s) — {e}")

        # API 스로틀링 방지
        if i < len(pdf_files) and args.delay > 0:
            time.sleep(args.delay)

    # CSV 저장
    output_path = Path(args.output)
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✓ 완료: {ok_count}개 성공, {err_count}개 오류")
    print(f"  결과 저장: {output_path.resolve()}")


if __name__ == "__main__":
    main()
