import { NextResponse } from "next/server";

import { cancelJob, getJob } from "@/lib/jobStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

export async function POST(
  _req: Request,
  { params }: { params: Promise<{ jobId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { jobId } = await params;

    const job = await getJob(ws.teamId, jobId);
    if (!job) {
      return NextResponse.json({ ok: false, error: "NOT_FOUND" }, { status: 404 });
    }
    if (!job.fanout) {
      return NextResponse.json({ ok: false, error: "NOT_FANOUT_JOB" }, { status: 400 });
    }

    const cancelled = await cancelJob(ws.teamId, jobId);
    if (!cancelled) {
      return NextResponse.json({ ok: false, error: "CANNOT_CANCEL" }, { status: 409 });
    }

    return NextResponse.json({ ok: true });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}
