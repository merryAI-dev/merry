import { NextResponse } from "next/server";

import { getJob } from "@/lib/jobStore";
import { getLatestComputeSnapshot } from "@/lib/reportAssumptionsStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

export async function GET(_req: Request, ctx: { params: Promise<{ sessionId: string }> }) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { sessionId } = await ctx.params;
    if (!sessionId.startsWith("report_")) {
      return NextResponse.json({ ok: false, error: "BAD_SESSION" }, { status: 400 });
    }

    const snap = await getLatestComputeSnapshot(ws.teamId, sessionId);
    if (!snap) return NextResponse.json({ ok: true, snapshot: null, job: null });

    const job = await getJob(ws.teamId, snap.jobId);
    return NextResponse.json({ ok: true, snapshot: snap, job });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}

