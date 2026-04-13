import { NextResponse } from "next/server";

import { listDiagnosisHistory } from "@/lib/diagnosisSessionStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

function parseLimit(url: URL): number {
  const raw = Number(url.searchParams.get("limit") ?? "30");
  if (!Number.isFinite(raw)) return 30;
  return Math.min(Math.max(Math.trunc(raw), 1), 100);
}

export async function GET(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const events = await listDiagnosisHistory(ws.teamId, parseLimit(new URL(req.url)));
    return NextResponse.json({ ok: true, events });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}
