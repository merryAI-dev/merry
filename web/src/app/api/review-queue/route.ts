import { NextResponse } from "next/server";

import { handleApiError } from "@/lib/apiError";
import { listReviewQueueRecords, syncReviewQueueFromRecentConditionJobs } from "@/lib/reviewQueue";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

export async function GET(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const url = new URL(req.url);
    const status = (url.searchParams.get("status") ?? "open") as
      | "open"
      | "all"
      | "queued"
      | "in_review"
      | "resolved_correct"
      | "resolved_incorrect"
      | "resolved_ambiguous"
      | "suppressed";
    const reason = (url.searchParams.get("reason") ?? "all") as
      | "all"
      | "task_error"
      | "company_unrecognized"
      | "parse_warning"
      | "alias_correction"
      | "evidence_missing";
    const limit = Number(url.searchParams.get("limit") ?? 100);
    const syncRecent = url.searchParams.get("sync") !== "false";

    const syncedCandidates = syncRecent
      ? await syncReviewQueueFromRecentConditionJobs(ws.teamId, 20)
      : 0;
    const items = await listReviewQueueRecords(ws.teamId, { status, reason, limit });

    const summary = items.reduce<Record<string, number>>((acc, item) => {
      acc.total = (acc.total ?? 0) + 1;
      acc[item.status] = (acc[item.status] ?? 0) + 1;
      acc[item.queueReason] = (acc[item.queueReason] ?? 0) + 1;
      return acc;
    }, { total: 0 });

    return NextResponse.json({ ok: true, items, summary, syncedCandidates });
  } catch (err) {
    return handleApiError(err, "GET /api/review-queue");
  }
}
