import { NextResponse } from "next/server";

import { removeReportStashItem } from "@/lib/reportStash";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

export async function DELETE(
  _req: Request,
  ctx: { params: Promise<{ sessionId: string; itemId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { sessionId, itemId } = await ctx.params;
    if (!sessionId.startsWith("report_")) {
      return NextResponse.json({ ok: false, error: "BAD_SESSION" }, { status: 400 });
    }
    const id = (itemId ?? "").trim();
    if (!id) return NextResponse.json({ ok: false, error: "BAD_ITEM" }, { status: 400 });

    await removeReportStashItem({
      teamId: ws.teamId,
      sessionId,
      itemId: id,
      updatedBy: ws.memberName,
    });
    return NextResponse.json({ ok: true });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}

