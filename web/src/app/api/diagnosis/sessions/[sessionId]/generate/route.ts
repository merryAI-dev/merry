import { NextResponse } from "next/server";

import { generateDiagnosisReport } from "@/lib/diagnosisWorkflows";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

export async function POST(
  _req: Request,
  ctx: { params: Promise<{ sessionId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { sessionId } = await ctx.params;
    const result = await generateDiagnosisReport({
      teamId: ws.teamId,
      memberName: ws.memberName,
      sessionId,
    });
    return NextResponse.json({
      ok: true,
      assistantMessage: result.assistantMessage,
      artifact: result.artifact,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "BAD_REQUEST";
    const status =
      message === "UNAUTHORIZED" ? 401 :
      message === "NOT_FOUND" ? 404 :
      message === "SOURCE_FILE_MISSING" ? 409 :
      message === "REPORT_NOT_GENERATED" ? 502 :
      400;
    return NextResponse.json({ ok: false, error: message }, { status });
  }
}
