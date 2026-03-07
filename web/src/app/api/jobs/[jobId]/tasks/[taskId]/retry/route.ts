import { NextResponse } from "next/server";

import { handleApiError } from "@/lib/apiError";
import { retryFailedTask } from "@/lib/fanoutRetry";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

export async function POST(
  _req: Request,
  { params }: { params: Promise<{ jobId: string; taskId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { jobId, taskId } = await params;

    await retryFailedTask(ws.teamId, jobId, taskId);
    return NextResponse.json({ ok: true, retriedCount: 1 });
  } catch (err) {
    const code = err instanceof Error ? err.message : "";
    if (code === "TASK_NOT_FOUND") {
      return NextResponse.json({ ok: false, error: code }, { status: 404 });
    }
    if (code === "TASK_NOT_FAILED") {
      return NextResponse.json({ ok: false, error: code }, { status: 400 });
    }
    return handleApiError(err, "POST /api/jobs/[jobId]/tasks/[taskId]/retry");
  }
}
