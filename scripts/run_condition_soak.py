#!/usr/bin/env python3
"""Run a condition_check soak job against a deployed Merry instance."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.bench_pipeline import _extract_cookie, _http_json, _http_put_file

TEMP_ROOT = PROJECT_ROOT / "temp" / "soak"
DEFAULT_STAGE_SIZES = {"50": 50, "200": 200, "800": 800}
AUTHJS_COOKIE = "authjs.session-token"
SECURE_AUTHJS_COOKIE = "__Secure-authjs.session-token"


def _load_pdf_paths(dataset_dir: Path) -> List[Path]:
    if not dataset_dir.exists():
        raise FileNotFoundError(f"dataset dir not found: {dataset_dir}")
    return sorted([path for path in dataset_dir.rglob("*.pdf") if path.is_file()])


def _stage_file_count(stage: str, limit: int) -> int:
    if limit > 0:
        return limit
    if stage not in DEFAULT_STAGE_SIZES:
        raise ValueError(f"unsupported stage: {stage}")
    return DEFAULT_STAGE_SIZES[stage]


def _take_files(paths: List[Path], count: int) -> List[Path]:
    if not paths:
        return []
    selected = [paths[index % len(paths)] for index in range(count)]
    return selected


def _parse_env_lines(text: str) -> Dict[str, str]:
    env: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        env[key] = value
    return env


def _load_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"auth env file not found: {path}")
    return _parse_env_lines(path.read_text(encoding="utf-8"))


def _default_authjs_cookie_name(base_url: str) -> str:
    scheme = urllib.parse.urlparse(base_url).scheme.lower()
    return SECURE_AUTHJS_COOKIE if scheme == "https" else AUTHJS_COOKIE


def _create_authjs_session_token(
    *,
    env_file: Path,
    cookie_name: str,
    team_id: str,
    member_name: str,
    member_email: str,
) -> str:
    env = _load_env_file(env_file)
    secret = env.get("NEXTAUTH_SECRET") or env.get("AUTH_SECRET") or env.get("WORKSPACE_JWT_SECRET")
    if not secret:
        raise RuntimeError(f"auth env file missing NEXTAUTH_SECRET/AUTH_SECRET/WORKSPACE_JWT_SECRET: {env_file}")

    jwt_module = (PROJECT_ROOT / "web" / "node_modules" / "@auth" / "core" / "jwt.js").as_posix()
    js = f"""
import {{ encode }} from {json.dumps(jwt_module)};
const token = await encode({{
  secret: {json.dumps(secret)},
  salt: {json.dumps(cookie_name)},
  token: {{
    sub: 'codex-soak',
    name: {json.dumps(member_name)},
    email: {json.dumps(member_email)},
    teamId: {json.dumps(team_id)},
    memberName: {json.dumps(member_name)},
  }},
}});
process.stdout.write(token);
"""
    return subprocess.check_output(
        ["node", "--input-type=module", "-e", js],
        text=True,
        cwd=str(PROJECT_ROOT),
    ).strip()


def _login_authjs(base_url: str, env_file: Path, team_id: str, member_name: str, member_email: str, cookie_name: str) -> str:
    _ = base_url
    return _create_authjs_session_token(
        env_file=env_file,
        cookie_name=cookie_name,
        team_id=team_id,
        member_name=member_name,
        member_email=member_email,
    )


def _login_workspace(base_url: str, team_id: str, member_name: str, passcode: str) -> str:
    status, payload, headers = _http_json(
        method="POST",
        url=base_url.rstrip("/") + "/api/auth/workspace",
        body={"teamId": team_id, "memberName": member_name, "passcode": passcode},
        timeout_seconds=20,
    )
    if status != 200 or not payload.get("ok"):
        raise RuntimeError(f"workspace login failed: http {status} {payload}")
    ws_token = _extract_cookie(headers.get("set-cookie", ""), "merry_ws")
    if not ws_token:
        raise RuntimeError("workspace login did not return merry_ws cookie")
    return ws_token


def _build_auth_header(cookie_name: str, cookie_value: str) -> Dict[str, str]:
    return {"cookie": f"{cookie_name}={cookie_value}"}


def _probe_auth(base_url: str, auth_header: Dict[str, str]) -> Dict[str, Any]:
    status, payload, _ = _http_json(
        method="GET",
        url=base_url.rstrip("/") + "/api/jobs?limit=1",
        headers=auth_header,
        timeout_seconds=20,
    )
    if status != 200 or not payload.get("ok"):
        raise RuntimeError(f"auth probe failed: http {status} {payload}")
    return payload


def _make_upload_session_id(path: Path) -> str:
    stem = path.stem.strip().replace(" ", "-")
    compact = "".join(ch for ch in stem if ch.isalnum() or ch in {"-", "_"}).strip("-_")
    compact = compact[:40] or "file"
    digest = hashlib.sha1(f"{path.name}:{path.stat().st_size}".encode("utf-8")).hexdigest()[:16]
    session_id = f"soak-{compact}-{digest}"
    return session_id[:64]


def _upload_file(base_url: str, auth_header: Dict[str, str], path: Path) -> Tuple[str, Dict[str, int]]:
    timings: Dict[str, int] = {}
    t0 = time.time()
    status, presign, _ = _http_json(
        method="POST",
        url=base_url.rstrip("/") + "/api/uploads/presign",
        body={
            "filename": path.name,
            "contentType": "application/pdf",
            "sizeBytes": path.stat().st_size,
            "uploadSessionId": _make_upload_session_id(path),
        },
        headers=auth_header,
        timeout_seconds=30,
    )
    timings["presign_ms"] = int((time.time() - t0) * 1000)
    if status != 200 or not presign.get("ok"):
        raise RuntimeError(f"presign failed for {path.name}: http {status} {presign}")

    file_obj = presign.get("file") if isinstance(presign.get("file"), dict) else {}
    upload_obj = presign.get("upload") if isinstance(presign.get("upload"), dict) else {}
    file_id = str(file_obj.get("fileId") or "")
    upload_url = str(upload_obj.get("url") or "")
    upload_headers = upload_obj.get("headers") if isinstance(upload_obj.get("headers"), dict) else {}
    content_type = str(upload_headers.get("content-type") or "application/pdf")
    if not file_id or not upload_url:
        raise RuntimeError(f"presign missing fields for {path.name}")

    t1 = time.time()
    put_status = _http_put_file(upload_url, path, content_type, timeout_seconds=300)
    timings["upload_ms"] = int((time.time() - t1) * 1000)
    if put_status not in (200, 201, 204):
        raise RuntimeError(f"upload failed for {path.name}: http {put_status}")

    t2 = time.time()
    status, complete, _ = _http_json(
        method="POST",
        url=base_url.rstrip("/") + "/api/uploads/complete",
        body={"fileId": file_id},
        headers=auth_header,
        timeout_seconds=30,
    )
    timings["complete_ms"] = int((time.time() - t2) * 1000)
    if status != 200 or not complete.get("ok"):
        raise RuntimeError(f"complete failed for {path.name}: http {status} {complete}")

    return file_id, timings


def _create_job(
    base_url: str,
    auth_header: Dict[str, str],
    file_ids: List[str],
    conditions: List[str],
) -> str:
    status, payload, _ = _http_json(
        method="POST",
        url=base_url.rstrip("/") + "/api/jobs",
        body={
            "jobType": "condition_check",
            "fileIds": file_ids,
            "params": {"conditions": conditions},
            "title": f"Condition soak {len(file_ids)} files",
        },
        headers=auth_header,
        timeout_seconds=30,
    )
    if status != 200 or not payload.get("ok"):
        raise RuntimeError(f"job create failed: http {status} {payload}")
    return str(payload["jobId"])


def _poll_job(
    base_url: str,
    auth_header: Dict[str, str],
    job_id: str,
    timeout_seconds: int,
    poll_interval_seconds: float,
) -> Dict[str, Any]:
    deadline = time.time() + timeout_seconds
    snapshots: List[Dict[str, Any]] = []
    last_job: Dict[str, Any] = {}
    while time.time() < deadline:
        status, payload, _ = _http_json(
            method="GET",
            url=base_url.rstrip("/") + f"/api/jobs/{urllib.parse.quote(job_id)}",
            headers=auth_header,
            timeout_seconds=20,
        )
        if status != 200 or not payload.get("ok") or not isinstance(payload.get("job"), dict):
            raise RuntimeError(f"job poll failed: http {status} {payload}")
        job = payload["job"]
        last_job = job
        snapshots.append({
            "status": job.get("status"),
            "fanoutStatus": job.get("fanoutStatus"),
            "processedCount": job.get("processedCount"),
            "failedCount": job.get("failedCount"),
            "updatedAt": job.get("updatedAt"),
            "ts": int(time.time()),
        })
        if job.get("status") in {"succeeded", "failed"}:
            return {"job": job, "snapshots": snapshots}
        time.sleep(poll_interval_seconds)
    raise TimeoutError(f"job {job_id} timed out; last snapshot={last_job}")


def _collect_artifacts(base_url: str, auth_header: Dict[str, str], job_id: str, job: Dict[str, Any]) -> List[Dict[str, Any]]:
    artifacts = job.get("artifacts") if isinstance(job.get("artifacts"), list) else []
    collected: List[Dict[str, Any]] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        artifact_id = str(artifact.get("artifactId") or "")
        if not artifact_id:
            continue
        status, payload, _ = _http_json(
            method="GET",
            url=base_url.rstrip("/") + f"/api/jobs/{urllib.parse.quote(job_id)}/artifact?artifactId={urllib.parse.quote(artifact_id)}",
            headers=auth_header,
            timeout_seconds=20,
        )
        collected.append({
            "artifactId": artifact_id,
            "label": artifact.get("label"),
            "contentType": artifact.get("contentType"),
            "sizeBytes": artifact.get("sizeBytes"),
            "presignOk": status == 200 and bool(payload.get("ok")),
            "expiresIn": payload.get("expiresIn") if isinstance(payload, dict) else None,
        })
    return collected


def _summarize_metric_snapshot(job: Dict[str, Any]) -> Dict[str, int]:
    metrics = job.get("metrics") if isinstance(job.get("metrics"), dict) else {}
    keys = [
        "total",
        "success_count",
        "failed_count",
        "warning_count",
        "company_group_count",
        "recognized_company_files",
        "unrecognized_company_files",
        "company_alias_merge_count",
        "company_alias_merged_files",
        "result_cache_hits",
        "parse_cache_hits",
        "rule_condition_count",
        "llm_condition_count",
        "saved_total_tokens",
    ]
    snapshot: Dict[str, int] = {}
    for key in keys:
        value = metrics.get(key, 0)
        try:
            snapshot[key] = int(value)
        except Exception:
            snapshot[key] = 0
    return snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a condition_check soak test against a deployed Merry instance.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--dataset-dir", default=str(PROJECT_ROOT / "companyData"))
    parser.add_argument("--stage", choices=sorted(DEFAULT_STAGE_SIZES.keys()), default="50")
    parser.add_argument("--limit", type=int, default=0, help="Override stage size.")
    parser.add_argument("--auth-mode", choices=["workspace", "authjs"], default="workspace")
    parser.add_argument("--team-id", default="")
    parser.add_argument("--member-name", default="soak")
    parser.add_argument("--member-email", default="")
    parser.add_argument("--passcode", default="")
    parser.add_argument("--auth-env-file", default="")
    parser.add_argument("--cookie-name", default="")
    parser.add_argument("--condition", action="append", dest="conditions", default=[])
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--poll-interval-seconds", type=float, default=3.0)
    parser.add_argument("--out", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_dir = Path(args.dataset_dir).resolve()
    files = _load_pdf_paths(dataset_dir)
    selected = _take_files(files, _stage_file_count(args.stage, args.limit))
    if not selected:
        raise RuntimeError("no pdf files selected for soak run")
    conditions = list(args.conditions or ["업력 3년 미만", "매출 10억 미만"])
    team_id = args.team_id.strip()
    member_name = args.member_name.strip() or "soak"

    if args.auth_mode == "workspace":
        if not team_id:
            raise RuntimeError("--team-id is required for --auth-mode workspace")
        if not args.passcode:
            raise RuntimeError("--passcode is required for --auth-mode workspace")
        cookie_name = "merry_ws"
        cookie_value = _login_workspace(args.base_url, team_id, member_name, args.passcode)
    else:
        env_file = Path(args.auth_env_file).resolve() if args.auth_env_file else Path("/tmp/merry_production.env")
        auth_env = _load_env_file(env_file)
        resolved_team_id = team_id or auth_env.get("AUTH_TEAM_ID", "").strip()
        if not resolved_team_id:
            raise RuntimeError("authjs login needs --team-id or AUTH_TEAM_ID in --auth-env-file")
        cookie_name = args.cookie_name.strip() or _default_authjs_cookie_name(args.base_url)
        member_email = args.member_email.strip() or f"{member_name}@{auth_env.get('AUTH_ALLOWED_DOMAIN', 'mysc.co.kr')}"
        cookie_value = _login_authjs(
            args.base_url,
            env_file,
            resolved_team_id,
            member_name,
            member_email,
            cookie_name,
        )
        team_id = resolved_team_id

    auth_header = _build_auth_header(cookie_name, cookie_value)
    auth_probe = _probe_auth(args.base_url, auth_header)

    upload_timings: List[Dict[str, int]] = []
    file_ids: List[str] = []
    for path in selected:
        file_id, timings = _upload_file(args.base_url, auth_header, path)
        file_ids.append(file_id)
        upload_timings.append(timings)

    create_started = time.time()
    job_id = _create_job(args.base_url, auth_header, file_ids, conditions)
    create_job_ms = int((time.time() - create_started) * 1000)
    poll_result = _poll_job(
        args.base_url,
        auth_header,
        job_id,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
    )
    job = poll_result["job"]
    artifacts = _collect_artifacts(args.base_url, auth_header, job_id, job)

    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("%Y%m%d_%H%M%S")
    output_path = Path(args.out).resolve() if args.out else (TEMP_ROOT / f"condition_soak_{run_id}.json")
    report = {
        "summary": {
            "baseUrl": args.base_url,
            "authMode": args.auth_mode,
            "teamId": team_id,
            "datasetDir": str(dataset_dir),
            "stage": args.stage,
            "selectedFiles": len(selected),
            "conditions": conditions,
            "jobId": job_id,
            "status": job.get("status"),
            "fanoutStatus": job.get("fanoutStatus"),
            "createJobMs": create_job_ms,
            "authProbeJobsVisible": len(auth_probe.get("jobs") or []),
            "metrics": _summarize_metric_snapshot(job),
        },
        "uploads": {
            "count": len(upload_timings),
            "presign_ms_total": sum(item.get("presign_ms", 0) for item in upload_timings),
            "upload_ms_total": sum(item.get("upload_ms", 0) for item in upload_timings),
            "complete_ms_total": sum(item.get("complete_ms", 0) for item in upload_timings),
        },
        "artifacts": artifacts,
        "pollSnapshots": poll_result["snapshots"],
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(output_path), "summary": report["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
