import { NextResponse } from "next/server";

import { getAirtableConfig, listFunds } from "@/lib/airtableServer";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

export async function GET() {
  try {
    await requireWorkspaceFromCookies();
    const cfg = getAirtableConfig();
    if (!cfg) {
      return NextResponse.json({ ok: false, error: "AIRTABLE_NOT_CONFIGURED" }, { status: 501 });
    }

    const funds = await listFunds(cfg);
    return NextResponse.json({ ok: true, funds });
  } catch (err) {
    const unauthorized = err instanceof Error && err.message === "UNAUTHORIZED";
    const status = unauthorized ? 401 : 500;
    const code = unauthorized ? "UNAUTHORIZED" : "FAILED";
    return NextResponse.json({ ok: false, error: code }, { status });
  }
}
