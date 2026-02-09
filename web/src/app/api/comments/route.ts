import { NextResponse } from "next/server";
import { z } from "zod";

import { addTeamComment, listTeamComments } from "@/lib/teamComments";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const AddSchema = z.object({
  text: z.string().min(1),
});

export async function GET() {
  try {
    const ws = await requireWorkspaceFromCookies();
    const comments = await listTeamComments(ws.teamId, 30);
    return NextResponse.json({ ok: true, comments });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
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
