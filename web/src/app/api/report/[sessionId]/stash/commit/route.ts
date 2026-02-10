import { NextResponse } from "next/server";
import { z } from "zod";

import { addDraftVersion, createDraft } from "@/lib/drafts";
import { listReportStashItems, removeReportStashItem, type ReportStashItem } from "@/lib/reportStash";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const CommitSchema = z.object({
  draftId: z.string().optional(),
  title: z.string().optional(),
  itemIds: z.array(z.string().min(1)).optional(),
});

function formatStashAsDraftMarkdown(items: ReportStashItem[]): string {
  const parts: string[] = [];
  for (const it of items) {
    const content = (it.content ?? "").trim();
    if (!content) continue;
    const firstLine = content.split(/\r?\n/, 1)[0] ?? "";
    const alreadyHasHeading = /^#{1,6}\s+/.test(firstLine.trim());
    parts.push(alreadyHasHeading ? content : `## ${it.title}\n\n${content}`);
  }
  return parts.join("\n\n---\n\n").trim();
}

export async function POST(req: Request, ctx: { params: Promise<{ sessionId: string }> }) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { sessionId } = await ctx.params;
    if (!sessionId.startsWith("report_")) {
      return NextResponse.json({ ok: false, error: "BAD_SESSION" }, { status: 400 });
    }

    const body = CommitSchema.parse(await req.json().catch(() => ({})));
    const stash = await listReportStashItems(ws.teamId, sessionId);
    const wanted = new Set((body.itemIds ?? []).map((s) => s.trim()).filter(Boolean));
    const items = wanted.size ? stash.filter((it) => wanted.has(it.itemId)) : stash;
    if (!items.length) {
      return NextResponse.json({ ok: false, error: "EMPTY" }, { status: 400 });
    }

    const content = formatStashAsDraftMarkdown(items);
    if (!content) {
      return NextResponse.json({ ok: false, error: "EMPTY_CONTENT" }, { status: 400 });
    }

    const title =
      (body.title ?? "").trim() ||
      `투자심사 보고서 초안 · ${new Date().toISOString().slice(0, 10)}`;

    const targetDraftId = (body.draftId ?? "").trim();
    let draftId: string;
    let versionId: string;
    let createdNew = false;

    if (targetDraftId) {
      const added = await addDraftVersion({
        teamId: ws.teamId,
        draftId: targetDraftId,
        createdBy: ws.memberName,
        title,
        content,
        source: { kind: "report_stash" },
      });
      draftId = targetDraftId;
      versionId = added.versionId;
    } else {
      const created = await createDraft({
        teamId: ws.teamId,
        createdBy: ws.memberName,
        title,
        content,
      });
      draftId = created.draftId;
      versionId = created.versionId;
      createdNew = true;
    }

    for (const it of items) {
      await removeReportStashItem({
        teamId: ws.teamId,
        sessionId,
        itemId: it.itemId,
        updatedBy: ws.memberName,
      });
    }

    return NextResponse.json({ ok: true, draftId, versionId, createdNew, committedCount: items.length });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}

