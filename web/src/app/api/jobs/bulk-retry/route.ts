import { NextResponse } from "next/server";
import { z } from "zod";

import { retryFanoutJob } from "@/lib/fanoutRetry";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const BulkRetrySchema = z.object({
  jobIds: z.array(z.string().min(1)).min(1).max(20),
});

/**
 * POST /api/jobs/bulk-retry
 *
 * Retry multiple failed fan-out jobs in a single request.
 */
export async function POST(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = BulkRetrySchema.parse(await req.json());

    const results: Array<{ jobId: string; ok: boolean; retriedCount?: number; error?: string }> = [];

    for (const jobId of body.jobIds) {
      try {
        const data = await retryFanoutJob(ws.teamId, jobId, "failed");
        results.push({ jobId, ok: true, retriedCount: data.retriedCount });
      } catch (err) {
        results.push({ jobId, ok: false, error: err instanceof Error ? err.message : "FAILED" });
      }
    }

    const ok = results.every((result) => result.ok);
    const failedJobs = results.length - results.filter((result) => result.ok).length;
    const totalRetried = results.filter((result) => result.ok).reduce((sum, result) => sum + (result.retriedCount ?? 0), 0);

    return NextResponse.json(
      {
        ok,
        totalRetried,
        failedJobs,
        results,
      },
      { status: ok ? 200 : 207 },
    );
  } catch (err) {
    const unauthorized = err instanceof Error && err.message === "UNAUTHORIZED";
    return NextResponse.json(
      { ok: false, error: unauthorized ? "UNAUTHORIZED" : "BAD_REQUEST" },
      { status: unauthorized ? 401 : 400 },
    );
  }
}
