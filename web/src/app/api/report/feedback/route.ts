import { NextResponse } from "next/server";
import { z } from "zod";

import { recordFailurePattern, type FailureCategory } from "@/lib/failurePatterns";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const BodySchema = z.object({
  sessionId: z.string().min(1).max(128),
  category: z.enum(["calculation", "analysis", "missing_data", "logic_gap", "tone"]),
  description: z.string().min(1).max(500),
  correction: z.string().max(2000).optional().default(""),
});

export async function POST(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = BodySchema.parse(await req.json());

    if (!body.sessionId.startsWith("report_")) {
      return NextResponse.json({ ok: false, error: "BAD_SESSION" }, { status: 400 });
    }

    await recordFailurePattern({
      teamId: ws.teamId,
      sessionId: body.sessionId,
      category: body.category as FailureCategory,
      description: body.description,
      correction: body.correction,
      memberName: ws.memberName,
    });

    return NextResponse.json({ ok: true });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}
