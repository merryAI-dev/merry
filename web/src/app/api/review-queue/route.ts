import { NextResponse } from "next/server";

import { handleApiError } from "@/lib/apiError";
import {
  getReviewQueueSummary,
  listReviewQueueRecords,
  syncReviewQueueFromRecentConditionJobs,
} from "@/lib/reviewQueue";
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
    const cursor = url.searchParams.get("cursor") ?? undefined;
    const syncRecent = url.searchParams.get("sync") !== "false";

    const syncedCandidates = syncRecent
      ? await syncReviewQueueFromRecentConditionJobs(ws.teamId, 20)
      : 0;
    const { items, hasMore, nextCursor } = await listReviewQueueRecords(ws.teamId, { status, reason, limit, cursor });
    const summary = await getReviewQueueSummary(ws.teamId);

    return NextResponse.json({ ok: true, items, summary, syncedCandidates, hasMore, nextCursor });
  } catch (err) {
    return handleApiError(err, "GET /api/review-queue");
  }
}
