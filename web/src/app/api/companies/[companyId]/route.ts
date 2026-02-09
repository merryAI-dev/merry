import { NextResponse } from "next/server";
import { z } from "zod";

import { getAirtableConfig, getCompanyDetail } from "@/lib/airtableServer";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const ParamsSchema = z.object({
  companyId: z.string().min(3),
});

export async function GET(_req: Request, ctx: { params: Promise<{ companyId: string }> }) {
  try {
    await requireWorkspaceFromCookies();
    const cfg = getAirtableConfig();
    if (!cfg) {
      return NextResponse.json({ ok: false, error: "AIRTABLE_NOT_CONFIGURED" }, { status: 501 });
    }

    const params = ParamsSchema.parse(await ctx.params);
    const company = await getCompanyDetail(cfg, params.companyId);
    return NextResponse.json({ ok: true, company });
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
    return NextResponse.json({ ok: false, error: code }, { status });
  }
}

