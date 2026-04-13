import { NextResponse } from "next/server";

import { listDiagnosisSessions, syncDiagnosisSessionFromLegacyJob } from "@/lib/diagnosisSessionStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

function parseLimit(url: URL): number {
  const raw = Number(url.searchParams.get("limit") ?? "20");
  if (!Number.isFinite(raw)) return 20;
  return Math.min(Math.max(Math.trunc(raw), 1), 100);
}

export async function GET(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const limit = parseLimit(new URL(req.url));
    const initial = await listDiagnosisSessions(ws.teamId, limit);
    for (const session of initial) {
      if (session.status === "processing" && session.legacyJobId) {
        await syncDiagnosisSessionFromLegacyJob(ws.teamId, session.sessionId);
      }
    }
    const sessions = await listDiagnosisSessions(ws.teamId, limit);
    return NextResponse.json({ ok: true, sessions });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}
