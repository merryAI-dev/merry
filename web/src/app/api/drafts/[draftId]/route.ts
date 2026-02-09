import { NextResponse } from "next/server";
import { z } from "zod";

import { addDraftVersion, getDraftDetail } from "@/lib/drafts";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const VersionSchema = z.object({
  title: z.string().min(1),
  content: z.string().min(1),
});

export async function GET(
  _req: Request,
  ctx: { params: Promise<{ draftId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { draftId } = await ctx.params;
    const detail = await getDraftDetail(ws.teamId, draftId);
    return NextResponse.json({ ok: true, draftId, ...detail });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}

export async function POST(
  req: Request,
  ctx: { params: Promise<{ draftId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { draftId } = await ctx.params;
    const body = VersionSchema.parse(await req.json());
    const version = await addDraftVersion({
      teamId: ws.teamId,
      draftId,
      createdBy: ws.memberName,
      title: body.title,
      content: body.content,
    });
    return NextResponse.json({ ok: true, ...version });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}
