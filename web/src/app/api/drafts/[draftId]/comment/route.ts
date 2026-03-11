import { NextResponse } from "next/server";
import { z } from "zod";

import { addDraftComment } from "@/lib/drafts";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const BodySchema = z.object({
  versionId: z.string().min(1).max(128),
  kind: z.enum(["수정", "좋음", "대안"]),
  text: z.string().min(1).max(5_000),
  anchor: z.object({
    start: z.number().int().min(0),
    end: z.number().int().min(0),
    quote: z.string().min(1).max(2_000),
    context: z.string().max(2_000).optional(),
  }),
  threadId: z.string().max(128).optional(),
  parentId: z.string().max(128).optional(),
});

export async function POST(
  req: Request,
  ctx: { params: Promise<{ draftId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { draftId } = await ctx.params;
    const body = BodySchema.parse(await req.json());
    const comment = await addDraftComment({
      teamId: ws.teamId,
      draftId,
      versionId: body.versionId,
      createdBy: ws.memberName,
      kind: body.kind,
      text: body.text,
      anchor: body.anchor,
      threadId: body.threadId,
      parentId: body.parentId,
    });
    return NextResponse.json({ ok: true, ...comment });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}
