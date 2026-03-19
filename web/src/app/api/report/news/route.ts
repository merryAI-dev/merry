import { NextResponse } from "next/server";
import { z } from "zod";

import { generateNewsDigest } from "@/lib/newsDigest";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";
export const maxDuration = 30;

const BodySchema = z.object({
  period: z.string().max(10).optional(),
  sector: z.string().max(50).optional(),
});

export async function POST(req: Request) {
  try {
    await requireWorkspaceFromCookies();
    const body = BodySchema.parse(await req.json());
    const result = await generateNewsDigest({ period: body.period, sector: body.sector });
    return NextResponse.json({ ok: true, ...result });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}
