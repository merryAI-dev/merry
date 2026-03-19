import { NextResponse } from "next/server";
import { z } from "zod";

import { dispatchTool } from "@/lib/finance-calc/tools";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const BodySchema = z.object({
  tool: z.string().min(1).max(64),
  params: z.record(z.string(), z.unknown()),
});

export async function POST(req: Request) {
  try {
    await requireWorkspaceFromCookies();
    const body = BodySchema.parse(await req.json());
    const result = dispatchTool(body.tool, body.params);
    return NextResponse.json(result);
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}
