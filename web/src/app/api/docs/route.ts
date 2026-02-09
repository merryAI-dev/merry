import { NextResponse } from "next/server";
import { z } from "zod";

import { addTeamDoc, listTeamDocs, seedDefaultDocs, updateTeamDoc } from "@/lib/teamDocs";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const AddSchema = z.object({
  name: z.string().min(1),
  required: z.boolean().optional(),
  owner: z.string().optional(),
  notes: z.string().optional(),
});

const UpdateSchema = z.object({
  docId: z.string().min(1),
  name: z.string().optional(),
  required: z.boolean().optional(),
  uploaded: z.boolean().optional(),
  owner: z.string().optional(),
  notes: z.string().optional(),
});

export async function GET() {
  try {
    const ws = await requireWorkspaceFromCookies();
    await seedDefaultDocs(ws.teamId, ws.memberName);
    const docs = await listTeamDocs(ws.teamId);
    return NextResponse.json({ ok: true, docs });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}

export async function POST(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = AddSchema.parse(await req.json());
    const doc = await addTeamDoc({
      teamId: ws.teamId,
      createdBy: ws.memberName,
      name: body.name,
      required: body.required,
      owner: body.owner,
      notes: body.notes,
    });
    return NextResponse.json({ ok: true, doc });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}

export async function PATCH(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = UpdateSchema.parse(await req.json());
    await updateTeamDoc({
      teamId: ws.teamId,
      updatedBy: ws.memberName,
      docId: body.docId,
      name: body.name,
      required: body.required,
      uploaded: body.uploaded,
      owner: body.owner,
      notes: body.notes,
    });
    return NextResponse.json({ ok: true });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}
