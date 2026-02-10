import { NextResponse } from "next/server";
import { z } from "zod";

import { createReportSession, listReportSessions } from "@/lib/reportChat";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const CreateSchema = z.object({
  title: z.string().optional(),
  fundId: z.string().optional(),
  fundName: z.string().optional(),
  companyId: z.string().optional(),
  companyName: z.string().optional(),
  reportDate: z.string().optional(),
  fileTitle: z.string().optional(),
  author: z.string().optional(),
});

export async function GET() {
  try {
    const ws = await requireWorkspaceFromCookies();
    const sessions = await listReportSessions(ws.teamId, 30);
    return NextResponse.json({ ok: true, sessions });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}

export async function POST(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = CreateSchema.parse(await req.json().catch(() => ({})));
    const created = await createReportSession({
      teamId: ws.teamId,
      memberName: ws.memberName,
      title: body.title,
      fundId: body.fundId,
      fundName: body.fundName,
      companyId: body.companyId,
      companyName: body.companyName,
      reportDate: body.reportDate,
      fileTitle: body.fileTitle,
      author: body.author,
    });
    return NextResponse.json({ ok: true, ...created });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}
