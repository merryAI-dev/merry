import { NextResponse } from "next/server";
import { z } from "zod";

import { handleApiError } from "@/lib/apiError";
import { paginate } from "@/lib/pagination";
import { addTeamComment, listTeamComments } from "@/lib/teamComments";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const AddSchema = z.object({
  text: z.string().min(1).max(5_000),
});

export async function GET(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const all = await listTeamComments(ws.teamId, 100);
    const { items, total, offset, hasMore } = paginate(all, new URL(req.url));
    return NextResponse.json({ ok: true, comments: items, total, offset, hasMore });
  } catch (err) {
    return handleApiError(err, "GET /api/comments");
  }
}

export async function POST(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = AddSchema.parse(await req.json());
    const comment = await addTeamComment({
      teamId: ws.teamId,
      createdBy: ws.memberName,
      text: body.text,
    });
    return NextResponse.json({ ok: true, comment });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}
