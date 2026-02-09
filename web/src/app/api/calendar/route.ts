import { NextResponse } from "next/server";
import { z } from "zod";

import { addTeamEvent, listTeamEvents } from "@/lib/teamCalendar";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const AddSchema = z.object({
  date: z.string().min(1),
  title: z.string().min(1),
  notes: z.string().optional(),
});

export async function GET() {
  try {
    const ws = await requireWorkspaceFromCookies();
    const events = await listTeamEvents(ws.teamId, 30);
    return NextResponse.json({ ok: true, events });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}

export async function POST(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = AddSchema.parse(await req.json());
    const event = await addTeamEvent({
      teamId: ws.teamId,
      createdBy: ws.memberName,
      date: body.date,
      title: body.title,
      notes: body.notes,
    });
    return NextResponse.json({ ok: true, event });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}
