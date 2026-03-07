import { NextResponse } from "next/server";
import { z } from "zod";

import { handleApiError } from "@/lib/apiError";
import { paginate } from "@/lib/pagination";
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

export async function GET(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const all = await listReportSessions(ws.teamId, 100);
    const { items, total, offset, hasMore } = paginate(all, new URL(req.url));
    return NextResponse.json({ ok: true, sessions: items, total, offset, hasMore });
  } catch (err) {
    return handleApiError(err, "GET /api/report/sessions");
  }
}

export async function POST(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = CreateSchema.parse(await req.json());
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
