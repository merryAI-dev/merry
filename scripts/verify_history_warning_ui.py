#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError as exc:  # pragma: no cover - environment-specific
    raise SystemExit(
        "Missing Python module 'playwright'. Use the Homebrew Playwright Python interpreter or install the module first."
    ) from exc


REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = REPO_ROOT / "web"
ENV_PATH = WEB_ROOT / ".env.local"
SESSION_COOKIE = "authjs.session-token"


def read_env(name: str) -> str:
    if not ENV_PATH.exists():
        return ""
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if not line.startswith(f"{name}="):
            continue
        value = line.split("=", 1)[1].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            return value[1:-1]
        return value
    return ""


def create_session_token() -> str:
    secret = read_env("NEXTAUTH_SECRET") or read_env("AUTH_SECRET") or read_env("WORKSPACE_JWT_SECRET")
    if not secret:
        raise RuntimeError("Missing auth secret in web/.env.local")

    env = os.environ.copy()
    env.update(
        {
            "AUTH_SESSION_SECRET": secret,
            "AUTH_ALLOWED_DOMAIN": read_env("AUTH_ALLOWED_DOMAIN") or "mysc.co.kr",
            "AUTH_TEAM_ID": read_env("AUTH_TEAM_ID") or "mysc",
        }
    )

    jwt_module = (WEB_ROOT / "node_modules" / "@auth" / "core" / "jwt.js").as_posix()
    js = """
import { encode } from '__JWT_MODULE__';
const token = await encode({
  secret: process.env.AUTH_SESSION_SECRET,
  salt: 'authjs.session-token',
  token: {
    sub: 'codex',
    name: 'Codex',
    email: `codex@${process.env.AUTH_ALLOWED_DOMAIN}`,
    teamId: process.env.AUTH_TEAM_ID,
    memberName: 'Codex',
  },
});
process.stdout.write(token);
""".replace("__JWT_MODULE__", jwt_module)
    return subprocess.check_output(
        ["node", "--input-type=module", "-e", js],
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    ).strip()


def fetch_live_jobs(base_url: str, cookie_value: str) -> dict:
    req = urllib.request.Request(
        f"{base_url}/api/jobs?limit=5",
        headers={"Cookie": f"{SESSION_COOKIE}={cookie_value}"},
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read().decode("utf-8"))


def add_auth_cookie(context, base_url: str, cookie_value: str) -> None:
    host = re.sub(r"^https?://", "", base_url).split("/", 1)[0].split(":", 1)[0]
    context.add_cookies(
        [
            {
                "name": SESSION_COOKIE,
                "value": cookie_value,
                "domain": host,
                "path": "/",
                "httpOnly": True,
                "sameSite": "Lax",
            }
        ]
    )


def save_live_screenshot(browser, base_url: str, cookie_value: str, live_title: str, output_path: Path) -> None:
    context = browser.new_context(viewport={"width": 1440, "height": 1100})
    add_auth_cookie(context, base_url, cookie_value)
    page = context.new_page()
    page.goto(f"{base_url}/history", wait_until="networkidle")
    page.locator("h1", has_text="작업 이력").wait_for(timeout=15000)
    page.get_by_role("button", name=re.compile(re.escape(live_title))).first.wait_for(timeout=15000)
    page.add_style_tag(
        content="""
      .space-y-3 .truncate,
      .space-y-3 .font-mono,
      .space-y-3 .text-xs.text-\\[\\#B0B8C1\\] {
        filter: blur(8px);
      }
    """
    )
    page.screenshot(path=str(output_path), full_page=True)
    context.close()


def save_warning_screenshot(browser, base_url: str, cookie_value: str, output_path: Path) -> None:
    context = browser.new_context(viewport={"width": 1440, "height": 1280})
    add_auth_cookie(context, base_url, cookie_value)
    page = context.new_page()

    def handle_jobs(route) -> None:
        route.fulfill(
            content_type="application/json",
            body=json.dumps(
                {
                    "ok": True,
                    "jobs": [
                        {
                            "jobId": "mockwarningjob",
                            "type": "condition_check",
                            "status": "succeeded",
                            "title": "조건 검사 QA 샘플",
                            "createdBy": "Codex",
                            "createdAt": "2026-03-07T09:00:00.000Z",
                            "updatedAt": "2026-03-07T09:02:00.000Z",
                            "inputFileIds": ["file_warning"],
                            "artifacts": [],
                            "metrics": {
                                "total": 1,
                                "success_count": 1,
                                "failed_count": 0,
                                "warning_count": 1,
                            },
                            "fanout": True,
                            "totalTasks": 1,
                            "processedCount": 1,
                            "failedCount": 0,
                            "fanoutStatus": "succeeded",
                        }
                    ],
                    "total": 1,
                    "offset": 0,
                    "hasMore": False,
                }
            ),
        )

    def handle_tasks(route) -> None:
        route.fulfill(
            content_type="application/json",
            body=json.dumps(
                {
                    "ok": True,
                    "tasks": [
                        {
                            "taskId": "000",
                            "jobId": "mockwarningjob",
                            "taskIndex": 0,
                            "status": "succeeded",
                            "fileId": "file_warning",
                            "createdAt": "2026-03-07T09:00:00.000Z",
                            "startedAt": "2026-03-07T09:00:10.000Z",
                            "endedAt": "2026-03-07T09:00:22.000Z",
                            "result": {
                                "filename": "mock_warning.pdf",
                                "company_name": "경고기업",
                                "method": "nova_hybrid",
                                "pages": 12,
                                "elapsed_s": 12.4,
                                "parse_warning": "JSON 응답 일부를 복구했습니다.",
                                "raw_response": "{bad json",
                                "conditions": [
                                    {
                                        "condition": "최근 3년 매출 성장",
                                        "result": True,
                                        "evidence": "매출 그래프가 연속 상승합니다.",
                                    }
                                ],
                            },
                        }
                    ],
                }
            ),
        )

    page.route("**/api/jobs?**", handle_jobs)
    page.route("**/api/jobs/mockwarningjob/tasks", handle_tasks)
    page.goto(f"{base_url}/history", wait_until="networkidle")
    page.locator("text=조건 검사 QA 샘플").wait_for(timeout=15000)
    page.locator("text=경고 1").wait_for(timeout=15000)
    page.get_by_role("button", name=re.compile("조건 검사 QA 샘플")).click()
    page.get_by_role("button", name=re.compile(r"mock_warning\.pdf")).click()
    page.locator("text=복구 응답").wait_for(timeout=15000)
    page.locator("text=모델 응답을 복구해서 결과를 생성했습니다.").wait_for(timeout=15000)
    page.get_by_text("원본 응답 일부 보기").click()
    page.locator("text={bad json").wait_for(timeout=15000)
    page.screenshot(path=str(output_path), full_page=True)
    context.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture live and mocked history warning UI screenshots.")
    parser.add_argument("--base-url", default="http://127.0.0.1:3100")
    parser.add_argument("--live-output", default="/tmp/merry-history-live.png")
    parser.add_argument("--warning-output", default="/tmp/merry-history-warning.png")
    parser.add_argument("--skip-live", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cookie_value = create_session_token()
    live_title = ""

    if not args.skip_live:
        live = fetch_live_jobs(args.base_url, cookie_value)
        if not live.get("ok"):
            raise RuntimeError(f"Live API check failed: {live}")
        jobs = live.get("jobs") or []
        if not jobs:
            raise RuntimeError("No live jobs returned from /api/jobs")
        live_title = str(jobs[0]["title"])

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            if not args.skip_live:
                save_live_screenshot(browser, args.base_url, cookie_value, live_title, Path(args.live_output))
            save_warning_screenshot(browser, args.base_url, cookie_value, Path(args.warning_output))
        finally:
            browser.close()

    print(json.dumps(
        {
            "baseUrl": args.base_url,
            "liveTitle": live_title,
            "liveScreenshot": None if args.skip_live else args.live_output,
            "warningScreenshot": args.warning_output,
        },
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
