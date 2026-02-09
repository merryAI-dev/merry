import { NextResponse } from "next/server";
import { z } from "zod";

import { createDraft, listDrafts } from "@/lib/drafts";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const CreateSchema = z.object({
  title: z.string().min(1),
  content: z.string().min(1),
});

export async function GET() {
  try {
    const ws = await requireWorkspaceFromCookies();
    const drafts = await listDrafts(ws.teamId);
    return NextResponse.json({ ok: true, drafts });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}

export async function POST(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = CreateSchema.parse(await req.json());
    const created = await createDraft({
      teamId: ws.teamId,
      createdBy: ws.memberName,
      title: body.title,
      content: body.content,
    });
    return NextResponse.json({ ok: true, ...created });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}
