import { NextResponse } from "next/server";
import { z } from "zod";

import { getAirtableConfig, getFundDetail } from "@/lib/airtableServer";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const ParamsSchema = z.object({
  fundId: z.string().min(3),
});

export async function GET(_req: Request, ctx: { params: Promise<{ fundId: string }> }) {
  try {
    await requireWorkspaceFromCookies();
    const cfg = getAirtableConfig();
    if (!cfg) {
      return NextResponse.json({ ok: false, error: "AIRTABLE_NOT_CONFIGURED" }, { status: 501 });
    }

    const params = ParamsSchema.parse(await ctx.params);
    const detail = await getFundDetail(cfg, params.fundId);
    return NextResponse.json({ ok: true, ...detail });
  } catch (err) {
    const status =
      err instanceof Error && err.message === "UNAUTHORIZED"
        ? 401
        : err instanceof z.ZodError
          ? 400
          : 500;
    const code =
      err instanceof Error && err.message === "UNAUTHORIZED"
        ? "UNAUTHORIZED"
        : err instanceof z.ZodError
          ? "BAD_REQUEST"
          : "FAILED";

    if (code === "FAILED" && err instanceof Error && err.message.startsWith("AIRTABLE_")) {
      return NextResponse.json({ ok: false, error: err.message }, { status: 502 });
    }

    return NextResponse.json({ ok: false, error: code }, { status });
  }
}
