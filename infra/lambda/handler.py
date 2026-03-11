"""
Lambda handler for Ralph PDF parser.
Accepts POST with raw PDF bytes (Content-Type: application/pdf).
Returns JSON parse result.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import tempfile

# ralph/ is at project root; Lambda LAMBDA_TASK_ROOT points there
sys.path.insert(0, os.environ.get("LAMBDA_TASK_ROOT", "/var/task"))


def _run_parser(pdf_path: str, force_pro: bool = False) -> dict:
    from ralph.playground_parser import (
        assess_text_quality,
        build_presentation_prompt,
        call_nova_visual,
        classify_no_vlm,
        extract_text,
        render_first_page,
        render_pages,
        _PROMPT_OCR,
    )

    model_pro  = os.getenv("RALPH_VLM_NOVA_MODEL_ID",      "us.amazon.nova-pro-v1:0")
    model_lite = os.getenv("RALPH_VLM_NOVA_LITE_MODEL_ID", "us.amazon.nova-lite-v1:0")
    region     = os.getenv("RALPH_VLM_NOVA_REGION",        "us-east-1")
    use_vlm    = os.getenv("RALPH_USE_VLM", "true").lower() != "false"

    text, pages, blocks = extract_text(pdf_path)
    quality, is_poor, is_fragmented = assess_text_quality(text, blocks, page_count=pages)
    clf = classify_no_vlm(pdf_path, os.path.basename(pdf_path))

    method = "pymupdf"
    text_structure = "document"
    visual_description = None

    if force_pro and use_vlm:
        try:
            img = render_first_page(pdf_path, dpi=150)
            visual_description = call_nova_visual(img, model_pro, region, _PROMPT_OCR)
            method, text_structure = "nova_pro", "image"
        except Exception as e:
            visual_description = {"error": str(e)}
            method, text_structure = "nova_error", "image"
    elif is_poor and use_vlm:
        try:
            img = render_first_page(pdf_path)
            visual_description = call_nova_visual(img, model_lite, region, _PROMPT_OCR)
            method, text_structure = "nova_hybrid", "image"
        except Exception as e:
            visual_description = {"error": str(e)}
            method, text_structure = "nova_error", "image"
    elif is_fragmented and use_vlm:
        try:
            imgs = render_pages(pdf_path)
            prompt = build_presentation_prompt([{"page": i + 1} for i in range(len(imgs))])
            visual_description = call_nova_visual(imgs, model_pro, region, prompt, max_tokens=5000)
            method, text_structure = "nova_presentation", "presentation"
        except Exception as e:
            visual_description = {"error": str(e)}
            method, text_structure = "nova_error", "presentation"

    return {
        "ok": True,
        "text": text,
        "pages": pages,
        "method": method,
        "text_quality": round(quality, 3),
        "is_poor": is_poor,
        "is_fragmented": is_fragmented,
        "text_structure": text_structure,
        "doc_type": clf.get("doc_type"),
        "confidence": clf.get("confidence", 0.0),
        "detection_method": clf.get("detection_method", "none"),
        "description": clf.get("description"),
        "visual_description": visual_description,
    }


def handler(event: dict, context: object) -> dict:
    # Auth
    secret = os.getenv("PARSER_INTERNAL_SECRET", "")
    if secret:
        headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
        if headers.get("x-parse-token", "") != secret:
            return {
                "statusCode": 401,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"ok": False, "error": "UNAUTHORIZED"}),
            }

    # Query params
    qs = event.get("queryStringParameters") or {}
    force_pro = str(qs.get("force_pro", "false")).lower() == "true"

    # PDF bytes (Lambda Function URL sends binary as base64)
    body = event.get("body") or ""
    is_b64 = event.get("isBase64Encoded", False)
    pdf_bytes = base64.b64decode(body) if is_b64 else (
        body.encode("latin-1") if isinstance(body, str) else body
    )

    if not pdf_bytes:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"ok": False, "error": "EMPTY_BODY"}),
        }

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp_path = f.name

        result = _run_parser(tmp_path, force_pro)
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(result),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"ok": False, "error": str(e)}),
        }
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
