import { NextResponse } from "next/server";
import { z } from "zod";

import { replyInDiagnosisSession } from "@/lib/diagnosisWorkflows";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const BodySchema = z.object({
  content: z.string().trim().min(1).max(20_000),
});

export async function POST(
  req: Request,
  ctx: { params: Promise<{ sessionId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { sessionId } = await ctx.params;
    const body = BodySchema.parse(await req.json());
    const result = await replyInDiagnosisSession({
      teamId: ws.teamId,
      memberName: ws.memberName,
      sessionId,
      content: body.content,
    });
    return NextResponse.json({
      ok: true,
      assistantMessage: result.assistantMessage,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "BAD_REQUEST";
    const status =
      message === "UNAUTHORIZED" ? 401 :
      message === "NOT_FOUND" ? 404 :
      message === "SOURCE_FILE_MISSING" ? 409 :
      400;
    return NextResponse.json({ ok: false, error: message }, { status });
  }
}
