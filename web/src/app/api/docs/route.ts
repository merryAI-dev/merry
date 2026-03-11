import { NextResponse } from "next/server";
import { z } from "zod";

import { handleApiError } from "@/lib/apiError";
import { paginate } from "@/lib/pagination";
import { addTeamDoc, listTeamDocs, seedDefaultDocs, updateTeamDoc } from "@/lib/teamDocs";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const AddSchema = z.object({
  name: z.string().min(1).max(500),
  required: z.boolean().optional(),
  owner: z.string().max(100).optional(),
  notes: z.string().max(5_000).optional(),
});

const UpdateSchema = z.object({
  docId: z.string().min(1).max(128),
  name: z.string().max(500).optional(),
  required: z.boolean().optional(),
  uploaded: z.boolean().optional(),
  owner: z.string().optional(),
  notes: z.string().optional(),
});

export async function GET(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    await seedDefaultDocs(ws.teamId, ws.memberName);
    const all = await listTeamDocs(ws.teamId);
    const { items, total, offset, hasMore } = paginate(all, new URL(req.url));
    return NextResponse.json({ ok: true, docs: items, total, offset, hasMore });
  } catch (err) {
    return handleApiError(err, "GET /api/docs");
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
