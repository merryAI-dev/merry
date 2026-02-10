#!/usr/bin/env python3
"""
End-to-end pipeline benchmark for Merry.

What it measures (optionally):
- Next.js API latency: presign -> upload -> complete -> job create -> job status polling
- Worker latency: SQS -> DynamoDB -> S3 download -> analysis -> S3 artifact upload -> DynamoDB update

Design goals:
- No secrets printed (env values are never logged).
- Safe defaults: creates a temporary SQS queue and deletes it at the end.
- Uses a bench teamId to avoid mixing with real data.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shlex
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMP_ROOT = PROJECT_ROOT / "temp" / "bench"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except Exception:
        return default


def _load_pdf_paths(dataset_dir: Path) -> List[Path]:
    if not dataset_dir.exists():
        raise FileNotFoundError(f"dataset dir not found: {dataset_dir}")
    files = sorted([p for p in dataset_dir.rglob("*.pdf") if p.is_file()])
    return files


def _percentile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if p <= 0:
        return float(sorted_vals[0])
    if p >= 100:
        return float(sorted_vals[-1])
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return float(sorted_vals[f])
    d = k - f
    return float(sorted_vals[f] * (1.0 - d) + sorted_vals[c] * d)


def _summarize_ms(values: List[int]) -> Dict[str, float]:
    vals = sorted([v for v in values if isinstance(v, int) and v >= 0])
    if not vals:
        return {"count": 0, "p50_ms": 0.0, "p90_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0, "avg_ms": 0.0}
    avg = sum(vals) / len(vals)
    return {
        "count": len(vals),
        "p50_ms": _percentile([float(v) for v in vals], 50),
        "p90_ms": _percentile([float(v) for v in vals], 90),
        "p95_ms": _percentile([float(v) for v in vals], 95),
        "max_ms": float(vals[-1]),
        "avg_ms": float(avg),
    }


def _http_json(
    *,
    method: str,
    url: str,
    body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout_seconds: int = 30,
) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
    data = None
    req_headers = {"accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers.setdefault("content-type", "application/json")
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read()
            text = raw.decode("utf-8", errors="replace")
            try:
                payload = json.loads(text) if text else {}
            except Exception:
                payload = {"_raw": text}
            return int(resp.status), payload, {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as e:
        raw = e.read()
        text = raw.decode("utf-8", errors="replace")
        try:
            payload = json.loads(text) if text else {}
        except Exception:
            payload = {"_raw": text}
        return int(e.code), payload, {k.lower(): v for k, v in e.headers.items()}


def _http_put_file(url: str, file_path: Path, content_type: str, timeout_seconds: int = 120) -> int:
    data = file_path.read_bytes()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"content-type": content_type, "content-length": str(len(data))},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        return int(resp.status)


def _extract_cookie(set_cookie: str, name: str) -> Optional[str]:
    # Very small parser: "name=value; ..."
    parts = [p.strip() for p in (set_cookie or "").split(";")]
    if not parts:
        return None
    kv = parts[0]
    if "=" not in kv:
        return None
    k, v = kv.split("=", 1)
    if k.strip() != name:
        return None
    return v.strip()


def _require_env(names: Iterable[str]) -> None:
    missing = [n for n in names if not (os.environ.get(n) or "").strip()]
    if missing:
        raise RuntimeError("Missing required env: " + ", ".join(missing))


def _strip_env(env: Dict[str, str], keys: Iterable[str]) -> None:
    for k in keys:
        env.pop(k, None)


@dataclass
class BenchResult:
    job_id: str
    file_name: str
    file_size_bytes: int
    job_type: str
    presign_ms: int
    upload_ms: int
    complete_ms: int
    create_job_ms: int
    end_to_end_ms: int
    ok: bool
    error: str = ""
    metrics: Dict[str, Any] = None


def _start_next_server(port: int, env: Dict[str, str]) -> subprocess.Popen:
    cmd = ["npm", "-C", "web", "run", "start", "--", "-p", str(port)]
    # Suppress stdout spam; keep stderr for readiness debugging.
    return subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_http_ready(base_url: str, timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    last_err = ""
    while time.time() < deadline:
        try:
            status, _, _ = _http_json(method="GET", url=base_url + "/api/health", timeout_seconds=10)
            if status in (200, 500):  # health can be 500 when env missing, still indicates server is up
                return
            last_err = f"status={status}"
        except Exception as e:
            last_err = str(e)
        time.sleep(0.5)
    raise TimeoutError(f"server not ready: {last_err}")


def _drain_process_output(proc: subprocess.Popen, max_lines: int = 200) -> str:
    lines: List[str] = []
    for _ in range(max_lines):
        if proc.stderr is None:
            break
        line = proc.stderr.readline()
        if not line:
            break
        lines.append(line.rstrip("\n"))
    return "\n".join(lines)


def _create_temp_sqs_queue(queue_name: str, region: str) -> str:
    import boto3

    sqs = boto3.client("sqs", region_name=region)
    resp = sqs.create_queue(QueueName=queue_name, Attributes={})
    return str(resp["QueueUrl"])


def _delete_sqs_queue(queue_url: str, region: str) -> None:
    import boto3

    sqs = boto3.client("sqs", region_name=region)
    try:
        sqs.delete_queue(QueueUrl=queue_url)
    except Exception:
        pass


def _start_worker_subprocess(env: Dict[str, str]) -> subprocess.Popen:
    py = str(PROJECT_ROOT / ".tdd_venv" / "bin" / "python")
    env = dict(env)
    env.setdefault("PYTHONPATH", str(PROJECT_ROOT))
    cmd = [py, "-u", "-m", "worker.main"]
    return subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _stop_process(proc: subprocess.Popen, name: str) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=8)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", default=str(PROJECT_ROOT / "companyData"))
    ap.add_argument("--job-type", default="pdf_evidence", choices=["pdf_evidence", "pdf_parse"])
    ap.add_argument("--runs", type=int, default=13, help="Number of jobs to run (files will be cycled).")
    ap.add_argument("--max-pages", type=int, default=30)
    ap.add_argument("--max-results", type=int, default=20)
    ap.add_argument("--port", type=int, default=3100)
    ap.add_argument("--timeout-seconds", type=int, default=1800)
    ap.add_argument("--no-worker", action="store_true", help="Only exercise API (creates jobs but doesn't process).")
    ap.add_argument("--no-sqs-temp-queue", action="store_true", help="Use existing MERRY_SQS_QUEUE_URL (not recommended).")
    ap.add_argument("--out", default="", help="Output JSON path (default: temp/bench/...)")
    args = ap.parse_args()

    dataset_dir = Path(args.dataset_dir).resolve()
    paths = _load_pdf_paths(dataset_dir)
    if not paths:
        print(f"No PDFs found under {dataset_dir}", file=sys.stderr)
        return 2

    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    run_id = f"{time.strftime('%Y%m%d_%H%M%S')}_{random.randint(1000,9999)}"
    out_json = Path(args.out).resolve() if args.out else (TEMP_ROOT / f"pipeline_{run_id}.json")

    # Validate runtime env (AWS + app storage).
    _require_env(["AWS_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "MERRY_DDB_TABLE", "MERRY_S3_BUCKET"])
    aws_region = (os.environ.get("AWS_REGION") or "").strip()

    # Prepare subprocess env for Next + worker.
    child_env = dict(os.environ)
    # Disable Google OAuth for benchmark login (passcode mode).
    # This forces the workspace passcode flow to be enabled.
    child_env["GOOGLE_CLIENT_ID"] = ""
    child_env["GOOGLE_CLIENT_SECRET"] = ""
    child_env.setdefault("NEXTAUTH_URL", f"http://localhost:{args.port}")
    child_env.setdefault("NEXTAUTH_SECRET", "bench-nextauth-secret")
    child_env.setdefault("WORKSPACE_JWT_SECRET", "bench-workspace-secret")
    child_env.setdefault("WORKSPACE_CODE", "bench")

    # Use a bench team id to avoid mixing with real data.
    team_id = f"bench_{run_id}"
    member_name = "bench"
    passcode = child_env["WORKSPACE_CODE"]

    queue_url: Optional[str] = None
    queue_name: Optional[str] = None
    if args.no_sqs_temp_queue:
        _require_env(["MERRY_SQS_QUEUE_URL"])
        queue_url = (os.environ.get("MERRY_SQS_QUEUE_URL") or "").strip()
    else:
        queue_name = f"merry-bench-{run_id}"
        queue_url = _create_temp_sqs_queue(queue_name, aws_region)
        child_env["MERRY_SQS_QUEUE_URL"] = queue_url

    # Build + start Next.
    print("[bench] building Next.js…")
    build_cmd = ["npm", "-C", "web", "run", "build"]
    subprocess.run(build_cmd, cwd=str(PROJECT_ROOT), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"[bench] starting Next.js on port {args.port}…")
    next_proc = _start_next_server(args.port, child_env)
    try:
        _wait_http_ready(f"http://localhost:{args.port}", timeout_seconds=80)
    except Exception:
        err = _drain_process_output(next_proc)
        _stop_process(next_proc, "next")
        if queue_url and queue_name and not args.no_sqs_temp_queue:
            _delete_sqs_queue(queue_url, aws_region)
        raise RuntimeError(f"Next server not ready. stderr:\n{err}")

    base_url = f"http://localhost:{args.port}"

    # Login via passcode to obtain merry_ws token (even if secure cookie, we attach manually).
    print("[bench] logging in (workspace passcode)…")
    status, payload, headers = _http_json(
        method="POST",
        url=base_url + "/api/auth/workspace",
        body={"teamId": team_id, "memberName": member_name, "passcode": passcode},
        timeout_seconds=15,
    )
    if status != 200 or not payload.get("ok"):
        _stop_process(next_proc, "next")
        if queue_url and queue_name and not args.no_sqs_temp_queue:
            _delete_sqs_queue(queue_url, aws_region)
        raise RuntimeError(f"login failed: http {status} {payload}")

    set_cookie = headers.get("set-cookie", "")
    ws_token = _extract_cookie(set_cookie, "merry_ws")
    if not ws_token:
        # Some servers may emit multiple Set-Cookie headers; fall back to raw header scan.
        ws_token = _extract_cookie(set_cookie, "merry_ws")
    if not ws_token:
        _stop_process(next_proc, "next")
        if queue_url and queue_name and not args.no_sqs_temp_queue:
            _delete_sqs_queue(queue_url, aws_region)
        raise RuntimeError("login did not return merry_ws cookie")

    auth_header = {"cookie": f"merry_ws={ws_token}"}

    worker_proc: Optional[subprocess.Popen] = None
    if not args.no_worker:
        print("[bench] starting worker…")
        worker_proc = _start_worker_subprocess(child_env)
        # Worker prints a first line when it boots; don't block too long.
        time.sleep(1.0)

    results: List[BenchResult] = []

    def pick_file(i: int) -> Path:
        return paths[i % len(paths)]

    print(f"[bench] running {args.runs} jobs ({args.job_type})…")
    started_at = time.time()
    for i in range(args.runs):
        p = pick_file(i)
        file_size = p.stat().st_size

        # 1) presign
        t0 = _now_ms()
        status, presign, _ = _http_json(
            method="POST",
            url=base_url + "/api/uploads/presign",
            body={
                "filename": p.name,
                "contentType": "application/pdf",
                "sizeBytes": file_size,
            },
            headers=auth_header,
            timeout_seconds=30,
        )
        presign_ms = _now_ms() - t0
        if status != 200 or not presign.get("ok"):
            results.append(
                BenchResult(
                    job_id="",
                    file_name=p.name,
                    file_size_bytes=file_size,
                    job_type=args.job_type,
                    presign_ms=presign_ms,
                    upload_ms=0,
                    complete_ms=0,
                    create_job_ms=0,
                    end_to_end_ms=0,
                    ok=False,
                    error=f"presign_failed:{status}",
                    metrics={},
                )
            )
            continue

        file_obj = presign.get("file") if isinstance(presign.get("file"), dict) else {}
        upload_obj = presign.get("upload") if isinstance(presign.get("upload"), dict) else {}

        file_id = str(file_obj.get("fileId") or "")
        upload = upload_obj
        upload_url = str(upload.get("url") or "")
        upload_headers = upload.get("headers") if isinstance(upload.get("headers"), dict) else {}
        content_type = str(upload_headers.get("content-type") or "application/pdf")
        if not file_id or not upload_url:
            results.append(
                BenchResult(
                    job_id="",
                    file_name=p.name,
                    file_size_bytes=file_size,
                    job_type=args.job_type,
                    presign_ms=presign_ms,
                    upload_ms=0,
                    complete_ms=0,
                    create_job_ms=0,
                    end_to_end_ms=0,
                    ok=False,
                    error="presign_missing_fields",
                    metrics={},
                )
            )
            continue

        # 2) upload (PUT to S3)
        t1 = _now_ms()
        try:
            put_status = _http_put_file(upload_url, p, content_type, timeout_seconds=300)
        except Exception as e:
            results.append(
                BenchResult(
                    job_id="",
                    file_name=p.name,
                    file_size_bytes=file_size,
                    job_type=args.job_type,
                    presign_ms=presign_ms,
                    upload_ms=_now_ms() - t1,
                    complete_ms=0,
                    create_job_ms=0,
                    end_to_end_ms=0,
                    ok=False,
                    error=f"upload_failed:{type(e).__name__}",
                    metrics={},
                )
            )
            continue
        upload_ms = _now_ms() - t1
        if put_status not in (200, 201, 204):
            results.append(
                BenchResult(
                    job_id="",
                    file_name=p.name,
                    file_size_bytes=file_size,
                    job_type=args.job_type,
                    presign_ms=presign_ms,
                    upload_ms=upload_ms,
                    complete_ms=0,
                    create_job_ms=0,
                    end_to_end_ms=0,
                    ok=False,
                    error=f"upload_http_{put_status}",
                    metrics={},
                )
            )
            continue

        # 3) complete
        t2 = _now_ms()
        status, complete, _ = _http_json(
            method="POST",
            url=base_url + "/api/uploads/complete",
            body={"fileId": file_id},
            headers=auth_header,
            timeout_seconds=30,
        )
        complete_ms = _now_ms() - t2
        if status != 200 or not complete.get("ok"):
            results.append(
                BenchResult(
                    job_id="",
                    file_name=p.name,
                    file_size_bytes=file_size,
                    job_type=args.job_type,
                    presign_ms=presign_ms,
                    upload_ms=upload_ms,
                    complete_ms=complete_ms,
                    create_job_ms=0,
                    end_to_end_ms=0,
                    ok=False,
                    error=f"complete_failed:{status}",
                    metrics={},
                )
            )
            continue

        # 4) create job (enqueue)
        params: Dict[str, Any] = {}
        if args.job_type == "pdf_evidence":
            params = {"maxPages": args.max_pages, "maxResults": args.max_results}
        elif args.job_type == "pdf_parse":
            params = {"maxPages": args.max_pages, "outputMode": "structured"}

        t3 = _now_ms()
        status, created, _ = _http_json(
            method="POST",
            url=base_url + "/api/jobs",
            body={"jobType": args.job_type, "fileIds": [file_id], "params": params},
            headers=auth_header,
            timeout_seconds=30,
        )
        create_job_ms = _now_ms() - t3
        if status != 200 or not created.get("ok"):
            results.append(
                BenchResult(
                    job_id="",
                    file_name=p.name,
                    file_size_bytes=file_size,
                    job_type=args.job_type,
                    presign_ms=presign_ms,
                    upload_ms=upload_ms,
                    complete_ms=complete_ms,
                    create_job_ms=create_job_ms,
                    end_to_end_ms=0,
                    ok=False,
                    error=f"create_job_failed:{status}",
                    metrics={},
                )
            )
            continue

        job_id = str(created.get("jobId") or "")

        # poll status
        job_start_ms = _now_ms()
        ok = False
        last_error = ""
        metrics: Dict[str, Any] = {}
        deadline = time.time() + min(args.timeout_seconds, 60 * 60)
        while time.time() < deadline:
            st, job_resp, _ = _http_json(
                method="GET",
                url=base_url + f"/api/jobs/{urllib.parse.quote(job_id)}",
                headers=auth_header,
                timeout_seconds=20,
            )
            if st == 200 and job_resp.get("ok") and isinstance(job_resp.get("job"), dict):
                job = job_resp["job"]
                status_str = str(job.get("status") or "")
                if status_str in ("succeeded", "failed"):
                    ok = status_str == "succeeded"
                    last_error = str(job.get("error") or "")
                    metrics = job.get("metrics") if isinstance(job.get("metrics"), dict) else {}
                    break
            time.sleep(1.0)

        end_to_end_ms = _now_ms() - job_start_ms
        results.append(
            BenchResult(
                job_id=job_id,
                file_name=p.name,
                file_size_bytes=file_size,
                job_type=args.job_type,
                presign_ms=presign_ms,
                upload_ms=upload_ms,
                complete_ms=complete_ms,
                create_job_ms=create_job_ms,
                end_to_end_ms=end_to_end_ms,
                ok=ok,
                error=last_error,
                metrics=metrics,
            )
        )

        # progress
        if (i + 1) % max(1, min(10, args.runs)) == 0:
            elapsed = int(time.time() - started_at)
            done = i + 1
            print(f"[bench] {done}/{args.runs} done ({elapsed}s)")

    total_s = int(time.time() - started_at)

    if worker_proc:
        _stop_process(worker_proc, "worker")
    _stop_process(next_proc, "next")
    if queue_url and queue_name and not args.no_sqs_temp_queue:
        _delete_sqs_queue(queue_url, aws_region)

    # Summaries
    presign_list = [r.presign_ms for r in results]
    upload_list = [r.upload_ms for r in results]
    complete_list = [r.complete_ms for r in results]
    create_list = [r.create_job_ms for r in results]
    e2e_list = [r.end_to_end_ms for r in results if r.job_id]

    summary = {
        "run_id": run_id,
        "dataset_dir": str(dataset_dir),
        "job_type": args.job_type,
        "runs": args.runs,
        "unique_files": len(paths),
        "team_id": team_id,
        "port": args.port,
        "total_seconds": total_s,
        "stages": {
            "presign": _summarize_ms(presign_list),
            "upload": _summarize_ms(upload_list),
            "complete": _summarize_ms(complete_list),
            "create_job": _summarize_ms(create_list),
            "end_to_end": _summarize_ms(e2e_list),
        },
        "success": sum(1 for r in results if r.ok),
        "failed": sum(1 for r in results if (r.job_id and not r.ok)),
        "api_failures": sum(1 for r in results if (not r.job_id and not r.ok)),
        "queue_temp": {"created": bool(queue_name and not args.no_sqs_temp_queue), "name": queue_name or ""},
        "notes": [
            "No secret values are stored in this report.",
            "End-to-end includes worker processing if worker was started; otherwise jobs remain queued.",
        ],
    }

    out = {
        "summary": summary,
        "results": [
            {
                "jobId": r.job_id,
                "fileName": r.file_name,
                "fileSizeBytes": r.file_size_bytes,
                "jobType": r.job_type,
                "ok": r.ok,
                "error": r.error,
                "ms": {
                    "presign": r.presign_ms,
                    "upload": r.upload_ms,
                    "complete": r.complete_ms,
                    "createJob": r.create_job_ms,
                    "endToEnd": r.end_to_end_ms,
                },
                "metrics": r.metrics or {},
            }
            for r in results
        ],
    }

    out_json.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[bench] wrote {out_json}")
    print(json.dumps(summary["stages"], ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
