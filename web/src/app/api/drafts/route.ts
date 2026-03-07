import { NextResponse } from "next/server";
import { z } from "zod";

import { handleApiError } from "@/lib/apiError";
import { createDraft, listDrafts } from "@/lib/drafts";
import { paginate } from "@/lib/pagination";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const CreateSchema = z.object({
  title: z.string().min(1).max(500),
  content: z.string().min(1).max(50_000),
});

export async function GET(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const all = await listDrafts(ws.teamId);
    const { items, total, offset, hasMore } = paginate(all, new URL(req.url));
    return NextResponse.json({ ok: true, drafts: items, total, offset, hasMore });
  } catch (err) {
    return handleApiError(err, "GET /api/drafts");
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
