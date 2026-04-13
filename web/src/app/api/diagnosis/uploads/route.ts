import { NextResponse } from "next/server";
import { z } from "zod";

import { startDiagnosisFromUploadedFile } from "@/lib/diagnosisWorkflows";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const BodySchema = z.object({
  fileId: z.string().min(6),
  title: z.string().trim().min(1).max(200).optional(),
});

export async function POST(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = BodySchema.parse(await req.json());
    const started = await startDiagnosisFromUploadedFile({
      teamId: ws.teamId,
      memberName: ws.memberName,
      fileId: body.fileId,
      title: body.title,
    });

    return NextResponse.json({
      ok: true,
      sessionId: started.session.sessionId,
      runId: started.run.runId,
      legacyJobId: started.legacyJobId,
      href: `/diagnosis/sessions/${started.session.sessionId}`,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "BAD_REQUEST";
    const status =
      message === "UNAUTHORIZED" ? 401 :
      message === "FILE_NOT_FOUND" ? 404 :
      message === "FILE_NOT_UPLOADED" ? 400 :
      400;
    return NextResponse.json({ ok: false, error: message }, { status });
  }
}
