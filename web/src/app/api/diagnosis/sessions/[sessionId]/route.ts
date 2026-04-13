import { NextResponse } from "next/server";

import { getDiagnosisSessionDetail, syncDiagnosisSessionFromLegacyJob } from "@/lib/diagnosisSessionStore";
import { getJob } from "@/lib/jobStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

export async function GET(
  _req: Request,
  ctx: { params: Promise<{ sessionId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { sessionId } = await ctx.params;
    await syncDiagnosisSessionFromLegacyJob(ws.teamId, sessionId);
    const detail = await getDiagnosisSessionDetail(ws.teamId, sessionId);
    if (!detail) {
      return NextResponse.json({ ok: false, error: "NOT_FOUND" }, { status: 404 });
    }

    const legacyJob = detail.legacyJobId ? await getJob(ws.teamId, detail.legacyJobId) : null;
    return NextResponse.json({
      ok: true,
      session: {
        ...detail,
        legacyJob: legacyJob
          ? {
              jobId: legacyJob.jobId,
              status: legacyJob.status,
              artifacts: legacyJob.artifacts ?? [],
              error: legacyJob.error ?? "",
            }
          : null,
      },
    });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}
