import { createHash } from "crypto";
import { NextResponse } from "next/server";
import { z } from "zod";

import { handleApiError } from "@/lib/apiError";
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
    return handleApiError(err, "GET /api/presence");
  }
}

export async function POST(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = PostSchema.parse(await req.json());
    if (!body.scopeId.startsWith("report_")) {
      return NextResponse.json({ ok: false, error: "BAD_SCOPE" }, { status: 400 });
    }

    const session = (await auth()) as { user?: { email?: string | null; image?: string | null } } | null;
    const email = typeof session?.user?.email === "string" ? session.user.email : "";
    const image = typeof session?.user?.image === "string" ? session.user.image : "";

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

