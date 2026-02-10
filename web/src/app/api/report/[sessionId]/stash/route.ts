import { NextResponse } from "next/server";
import { ZodError, z } from "zod";

import { addReportStashItem, inferStashTitleFromContent, listReportStashItems } from "@/lib/reportStash";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const CreateSchema = z.object({
  content: z.string().min(1),
  title: z.string().optional(),
  source: z.record(z.unknown()).optional(),
});

export async function GET(_req: Request, ctx: { params: Promise<{ sessionId: string }> }) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { sessionId } = await ctx.params;
    if (!sessionId.startsWith("report_")) {
      return NextResponse.json({ ok: false, error: "BAD_SESSION" }, { status: 400 });
    }
    const items = await listReportStashItems(ws.teamId, sessionId);
    return NextResponse.json({ ok: true, items });
  } catch (err) {
    const unauthorized = err instanceof Error && err.message === "UNAUTHORIZED";
    return NextResponse.json({ ok: false, error: unauthorized ? "UNAUTHORIZED" : "FAILED" }, { status: unauthorized ? 401 : 500 });
  }
}

export async function POST(req: Request, ctx: { params: Promise<{ sessionId: string }> }) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { sessionId } = await ctx.params;
    if (!sessionId.startsWith("report_")) {
      return NextResponse.json({ ok: false, error: "BAD_SESSION" }, { status: 400 });
    }
    const body = CreateSchema.parse(await req.json());

    const normalized = body.content.trim().replaceAll("\r\n", "\n");
    const existing = await listReportStashItems(ws.teamId, sessionId);
    const dup = existing.find((it) => it.content.trim().replaceAll("\r\n", "\n") === normalized);
    if (dup) {
      return NextResponse.json({ ok: true, itemId: dup.itemId, alreadyExists: true });
    }

    const title = (body.title ?? inferStashTitleFromContent(body.content)).trim();
    const created = await addReportStashItem({
      teamId: ws.teamId,
      sessionId,
      content: body.content.trim(),
      title,
      createdBy: ws.memberName,
      source: body.source,
    });
    return NextResponse.json({ ok: true, itemId: created.itemId });
  } catch (err) {
    const unauthorized = err instanceof Error && err.message === "UNAUTHORIZED";
    if (unauthorized) {
      return NextResponse.json({ ok: false, error: "UNAUTHORIZED" }, { status: 401 });
    }
    if (err instanceof ZodError) {
      return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status: 400 });
    }

    // Unexpected server-side failure (DDB, etc). Log without leaking request content.
    console.error("report stash POST failed", {
      err: err instanceof Error ? (err.message || err.name) : String(err),
    });
    return NextResponse.json({ ok: false, error: "FAILED" }, { status: 500 });
  }
}
