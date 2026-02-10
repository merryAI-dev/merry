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
    if (unauthorized) {
      return NextResponse.json({ ok: false, error: "UNAUTHORIZED" }, { status: 401 });
    }

    // Pass through Airtable codes for quicker debugging (no secrets included).
    const msg = err instanceof Error ? err.message : "";
    if (msg.startsWith("AIRTABLE_")) {
      return NextResponse.json({ ok: false, error: msg }, { status: 502 });
    }

    return NextResponse.json({ ok: false, error: "FAILED" }, { status: 500 });
  }
}
