import { NextResponse } from "next/server";
import { z } from "zod";

import { attachDiagnosisContextDocumentFromUploadedFile } from "@/lib/diagnosisWorkflows";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const BodySchema = z.object({
  sessionId: z.string().min(6),
  fileId: z.string().min(6),
});

export async function POST(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = BodySchema.parse(await req.json());
    const attached = await attachDiagnosisContextDocumentFromUploadedFile({
      teamId: ws.teamId,
      memberName: ws.memberName,
      sessionId: body.sessionId,
      fileId: body.fileId,
    });

    return NextResponse.json({
      ok: true,
      document: attached.document,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "BAD_REQUEST";
    const status =
      message === "UNAUTHORIZED" ? 401 :
      message === "NOT_FOUND" || message === "FILE_NOT_FOUND" ? 404 :
      message === "FILE_NOT_UPLOADED" || message === "UNSUPPORTED_CONTEXT_FILE" ? 400 :
      400;
    return NextResponse.json({ ok: false, error: message }, { status });
  }
}
