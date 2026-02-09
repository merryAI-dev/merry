import { NextResponse } from "next/server";

import { getRecentActivity } from "@/lib/teamActivity";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

export async function GET() {
  try {
    const ws = await requireWorkspaceFromCookies();
    const activity = await getRecentActivity(ws.teamId, 40);
    return NextResponse.json({ ok: true, activity });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}
