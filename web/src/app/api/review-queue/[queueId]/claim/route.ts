import { NextResponse } from "next/server";

import { handleApiError } from "@/lib/apiError";
import { claimReviewQueueRecord } from "@/lib/reviewQueue";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

export async function POST(
  _req: Request,
  { params }: { params: Promise<{ queueId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { queueId } = await params;
    const item = await claimReviewQueueRecord(ws.teamId, queueId, ws.memberName);
    return NextResponse.json({ ok: true, item });
  } catch (err) {
    const code = err instanceof Error ? err.message : "";
    if (code === "QUEUE_NOT_FOUND") {
      return NextResponse.json({ ok: false, error: code }, { status: 404 });
    }
    if (code === "QUEUE_ALREADY_CLAIMED" || code === "QUEUE_NOT_OPEN") {
      return NextResponse.json({ ok: false, error: code }, { status: 400 });
    }
    return handleApiError(err, "POST /api/review-queue/[queueId]/claim");
  }
}
