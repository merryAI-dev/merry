import { createHash } from "crypto";
import { NextResponse } from "next/server";
import { z } from "zod";

import { auth } from "@/auth";
import { listReportPresence, upsertReportPresence } from "@/lib/presenceStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const PostSchema = z.object({
  scope: z.literal("report"),
  scopeId: z.string().min(1),
});

function hashKey(raw: string): string {
  return createHash("sha256").update(raw).digest("hex").slice(0, 20);
}

export async function GET(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const url = new URL(req.url);
    const scope = (url.searchParams.get("scope") ?? "").trim();
    const scopeId = (url.searchParams.get("scopeId") ?? "").trim();
    if (scope !== "report" || !scopeId.startsWith("report_")) {
      return NextResponse.json({ ok: false, error: "BAD_SCOPE" }, { status: 400 });
    }

    const members = await listReportPresence({ teamId: ws.teamId, sessionId: scopeId, withinSeconds: 60 });
    return NextResponse.json({ ok: true, members });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}

export async function POST(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = PostSchema.parse(await req.json());
    if (!body.scopeId.startsWith("report_")) {
      return NextResponse.json({ ok: false, error: "BAD_SCOPE" }, { status: 400 });
    }

    const session = await auth();
    const email = typeof (session as any)?.user?.email === "string" ? String((session as any).user.email) : "";
    const image = typeof (session as any)?.user?.image === "string" ? String((session as any).user.image) : "";

    const memberKey = hashKey((email || ws.memberName).toLowerCase());
    await upsertReportPresence({
      teamId: ws.teamId,
      sessionId: body.scopeId,
      memberKey,
      memberName: ws.memberName,
      memberImage: image || undefined,
    });

    return NextResponse.json({ ok: true });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}

