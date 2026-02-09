import { NextResponse } from "next/server";
import { z } from "zod";

import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";
import { addTeamTask, listTeamTasks, updateTeamTask } from "@/lib/teamTasks";

export const runtime = "nodejs";

const AddSchema = z.object({
  title: z.string().min(1),
  owner: z.string().optional(),
  due_date: z.string().optional(),
  notes: z.string().optional(),
});

const UpdateSchema = z.object({
  taskId: z.string().min(1),
  title: z.string().optional(),
  status: z.enum(["todo", "in_progress", "done", "blocked"]).optional(),
  owner: z.string().optional(),
  due_date: z.string().optional(),
  notes: z.string().optional(),
});

export async function GET() {
  try {
    const ws = await requireWorkspaceFromCookies();
    const tasks = await listTeamTasks(ws.teamId, true, 80);
    return NextResponse.json({ ok: true, tasks });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
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
