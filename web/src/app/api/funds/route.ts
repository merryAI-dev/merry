import { NextResponse } from "next/server";

import { getAirtableConfig, listFunds } from "@/lib/airtableServer";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const SAFE_AIRTABLE_CODES = ["AIRTABLE_NOT_FOUND", "AIRTABLE_RATE_LIMIT", "AIRTABLE_INVALID_REQUEST"];

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

    // Only pass known safe Airtable error codes to client.
    const msg = err instanceof Error ? err.message : "";
    if (msg.startsWith("AIRTABLE_")) {
      const safeCode = SAFE_AIRTABLE_CODES.includes(msg) ? msg : "AIRTABLE_ERROR";
      return NextResponse.json({ ok: false, error: safeCode }, { status: 502 });
    }

    return NextResponse.json({ ok: false, error: "FAILED" }, { status: 500 });
  }
}
