import { NextResponse } from "next/server";
import { z } from "zod";

import { handleApiError } from "@/lib/apiError";
import { resolveReviewQueueRecord } from "@/lib/reviewQueue";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const BodySchema = z.object({
  status: z.enum(["resolved_correct", "resolved_incorrect", "resolved_ambiguous"]),
  reviewedResult: z.boolean().optional(),
  reviewComment: z.string().max(1000).optional(),
});

export async function POST(
  req: Request,
  { params }: { params: Promise<{ queueId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = BodySchema.parse(await req.json());
    const { queueId } = await params;
    const item = await resolveReviewQueueRecord(ws.teamId, queueId, {
      memberName: ws.memberName,
      ...body,
    });
    return NextResponse.json({ ok: true, item });
  } catch (err) {
    const code = err instanceof Error ? err.message : "";
    if (code === "QUEUE_NOT_FOUND") {
      return NextResponse.json({ ok: false, error: code }, { status: 404 });
    }
    if (code === "QUEUE_NOT_OPEN") {
      return NextResponse.json({ ok: false, error: code }, { status: 400 });
    }
    return handleApiError(err, "POST /api/review-queue/[queueId]/resolve");
  }
}
