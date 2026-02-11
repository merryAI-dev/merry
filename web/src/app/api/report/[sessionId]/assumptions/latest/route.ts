import { NextResponse } from "next/server";

import { getLatestAssumptionPack } from "@/lib/reportAssumptionsStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

export async function GET(_req: Request, ctx: { params: Promise<{ sessionId: string }> }) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { sessionId } = await ctx.params;
    if (!sessionId.startsWith("report_")) {
      return NextResponse.json({ ok: false, error: "BAD_SESSION" }, { status: 400 });
    }

    const pack = await getLatestAssumptionPack(ws.teamId, sessionId);
    return NextResponse.json({ ok: true, pack });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}

