import { NextResponse } from "next/server";
import { z } from "zod";

import { handleApiError } from "@/lib/apiError";
import { paginate } from "@/lib/pagination";
import { addTeamEvent, listTeamEvents } from "@/lib/teamCalendar";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const AddSchema = z.object({
  date: z.string().min(1).max(20),
  title: z.string().min(1).max(500),
  notes: z.string().max(5_000).optional(),
});

export async function GET(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const all = await listTeamEvents(ws.teamId, 100);
    const { items, total, offset, hasMore } = paginate(all, new URL(req.url));
    return NextResponse.json({ ok: true, events: items, total, offset, hasMore });
  } catch (err) {
    return handleApiError(err, "GET /api/calendar");
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
