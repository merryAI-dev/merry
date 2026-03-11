import { NextResponse } from "next/server";
import { z } from "zod";

import { handleApiError } from "@/lib/apiError";
import { paginate } from "@/lib/pagination";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";
import { addTeamTask, listTeamTasks, updateTeamTask } from "@/lib/teamTasks";

export const runtime = "nodejs";

const AddSchema = z.object({
  title: z.string().min(1).max(500),
  owner: z.string().max(100).optional(),
  due_date: z.string().max(20).optional(),
  notes: z.string().max(5_000).optional(),
});

const UpdateSchema = z.object({
  taskId: z.string().min(1).max(128),
  title: z.string().max(500).optional(),
  status: z.enum(["todo", "in_progress", "done", "blocked"]).optional(),
  owner: z.string().max(100).optional(),
  due_date: z.string().max(20).optional(),
  notes: z.string().max(5_000).optional(),
});

export async function GET(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const all = await listTeamTasks(ws.teamId, true, 100);
    const { items, total, offset, hasMore } = paginate(all, new URL(req.url));
    return NextResponse.json({ ok: true, tasks: items, total, offset, hasMore });
  } catch (err) {
    return handleApiError(err, "GET /api/tasks");
  }
}

export async function POST(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = AddSchema.parse(await req.json());
    const task = await addTeamTask({
      teamId: ws.teamId,
      createdBy: ws.memberName,
      title: body.title,
      owner: body.owner,
      due_date: body.due_date,
      notes: body.notes,
    });
    return NextResponse.json({ ok: true, task });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}

export async function PATCH(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = UpdateSchema.parse(await req.json());
    await updateTeamTask({
      teamId: ws.teamId,
      updatedBy: ws.memberName,
      taskId: body.taskId,
      title: body.title,
      status: body.status,
      owner: body.owner,
      due_date: body.due_date,
      notes: body.notes,
    });
    return NextResponse.json({ ok: true });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}
