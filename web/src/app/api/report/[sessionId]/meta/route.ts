import { NextResponse } from "next/server";

import { getSession } from "@/lib/chatStore";
import { reportSlugFromSessionId } from "@/lib/reportChat";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

export async function GET(_req: Request, ctx: { params: Promise<{ sessionId: string }> }) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { sessionId } = await ctx.params;
    if (!sessionId.startsWith("report_")) {
      return NextResponse.json({ ok: false, error: "BAD_SESSION" }, { status: 400 });
    }

    const s = await getSession(ws.teamId, sessionId);
    if (!s) {
      return NextResponse.json({ ok: false, error: "NOT_FOUND" }, { status: 404 });
    }

    const info = (s.user_info ?? {}) as Record<string, unknown>;
    const title = typeof info["title"] === "string" ? info["title"] : "투자심사 보고서";
    const slug = reportSlugFromSessionId(sessionId) ?? sessionId;

    return NextResponse.json({
      ok: true,
      session: {
        sessionId,
        slug,
        title,
        createdAt: s.created_at,
        fundId: typeof info["fundId"] === "string" ? info["fundId"] : undefined,
        fundName: typeof info["fundName"] === "string" ? info["fundName"] : undefined,
        companyId: typeof info["companyId"] === "string" ? info["companyId"] : undefined,
        companyName: typeof info["companyName"] === "string" ? info["companyName"] : undefined,
        reportDate: typeof info["reportDate"] === "string" ? info["reportDate"] : undefined,
        fileTitle: typeof info["fileTitle"] === "string" ? info["fileTitle"] : undefined,
        author: typeof info["author"] === "string" ? info["author"] : undefined,
      },
    });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}

