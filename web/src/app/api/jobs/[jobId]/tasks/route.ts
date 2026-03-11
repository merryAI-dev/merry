import { NextResponse } from "next/server";

import { withCache } from "@/lib/cache";
import { listTasksByJob } from "@/lib/jobStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ jobId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { jobId } = await params;
    const tasks = await listTasksByJob(ws.teamId, jobId);
    return withCache(NextResponse.json({ ok: true, tasks }), 3, 5);
  } catch (err) {
    const status =
      err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}
