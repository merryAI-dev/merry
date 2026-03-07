import { NextResponse } from "next/server";

import { handleApiError } from "@/lib/apiError";
import { withCache } from "@/lib/cache";
import { getJob } from "@/lib/jobStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

export async function GET(
  _req: Request,
  ctx: { params: Promise<{ jobId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { jobId } = await ctx.params;
    const job = await getJob(ws.teamId, jobId);
    if (!job) return NextResponse.json({ ok: false, error: "NOT_FOUND" }, { status: 404 });
    return withCache(NextResponse.json({ ok: true, job }), 3, 5);
  } catch (err) {
    return handleApiError(err, "GET /api/jobs/[jobId]");
  }
}

