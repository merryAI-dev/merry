import { NextResponse } from "next/server";

import { handleApiError } from "@/lib/apiError";
import { paginate } from "@/lib/pagination";
import { getRecentActivity } from "@/lib/teamActivity";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

export async function GET(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const all = await getRecentActivity(ws.teamId, 100);
    const { items, total, offset, hasMore } = paginate(all, new URL(req.url));
    return NextResponse.json({ ok: true, activity: items, total, offset, hasMore });
  } catch (err) {
    return handleApiError(err, "GET /api/activity");
  }
}
