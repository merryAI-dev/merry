import { NextResponse } from "next/server";

import { handleApiError } from "@/lib/apiError";
import { retryFanoutJob, type RetryMode } from "@/lib/fanoutRetry";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

/**
 * POST /api/jobs/[jobId]/retry
 *
 * Retry failed tasks for a fan-out job.
 * Accepts optional body: { mode: "failed" | "all" }
 */
export async function POST(
  req: Request,
  { params }: { params: Promise<{ jobId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { jobId } = await params;

    let mode: RetryMode = "failed";
    try {
      const body = await req.json();
      if (body?.mode === "all") mode = "all";
    } catch {
      // No body or invalid JSON — use default.
    }

    const { retriedCount } = await retryFanoutJob(ws.teamId, jobId, mode);
    return NextResponse.json({ ok: true, retriedCount });
  } catch (err) {
    const code = err instanceof Error ? err.message : "";
    if (code === "NOT_FOUND") {
      return NextResponse.json({ ok: false, error: code }, { status: 404 });
    }
    if (code === "NOT_FANOUT_JOB") {
      return NextResponse.json({ ok: false, error: code }, { status: 400 });
    }
    if (code === "JOB_NOT_TERMINAL") {
      return NextResponse.json({ ok: false, error: code }, { status: 409 });
    }
    if (
      code.startsWith("SQS_BATCH_SEND_FAILED") ||
      code.startsWith("RETRY_COMPENSATION_FAILED") ||
      code.startsWith("INVALID_RESTORE_STATUS")
    ) {
      return NextResponse.json({ ok: false, error: code }, { status: 500 });
    }
    return handleApiError(err, "POST /api/jobs/[jobId]/retry");
  }
}
