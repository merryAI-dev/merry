import { NextResponse } from "next/server";
import { z } from "zod";

import { setDraftCommentStatus } from "@/lib/drafts";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const BodySchema = z.object({
  commentId: z.string().min(1),
  status: z.enum(["open", "accepted", "rejected"]),
});

export async function POST(
  req: Request,
  ctx: { params: Promise<{ draftId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { draftId } = await ctx.params;
    const body = BodySchema.parse(await req.json());
    await setDraftCommentStatus({
      teamId: ws.teamId,
      draftId,
      commentId: body.commentId,
      status: body.status,
      updatedBy: ws.memberName,
    });
    return NextResponse.json({ ok: true });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}
