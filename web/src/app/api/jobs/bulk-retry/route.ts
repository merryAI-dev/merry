import { NextResponse } from "next/server";
import { z } from "zod";

import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const BulkRetrySchema = z.object({
  jobIds: z.array(z.string().min(1)).min(1).max(20),
});

/**
 * POST /api/jobs/bulk-retry
 *
 * Retry multiple failed fan-out jobs at once.
 * Internally delegates to each job's retry endpoint logic.
 */
export async function POST(req: Request) {
  try {
    await requireWorkspaceFromCookies();
    const body = BulkRetrySchema.parse(await req.json());

    const results: Array<{ jobId: string; ok: boolean; retriedCount?: number; error?: string }> = [];

    for (const jobId of body.jobIds) {
      try {
        // Reuse the same internal fetch to the per-job retry endpoint.
        const origin = new URL(req.url).origin;
        const retryRes = await fetch(`${origin}/api/jobs/${jobId}/retry`, {
          method: "POST",
          headers: {
            cookie: req.headers.get("cookie") ?? "",
            "content-type": "application/json",
          },
          body: JSON.stringify({ mode: "failed" }),
        });
        const data = await retryRes.json();
        results.push({ jobId, ok: data.ok, retriedCount: data.retriedCount, error: data.error });
      } catch (err) {
        results.push({ jobId, ok: false, error: err instanceof Error ? err.message : "FAILED" });
      }
    }

    const totalRetried = results.filter((r) => r.ok).reduce((s, r) => s + (r.retriedCount ?? 0), 0);

    return NextResponse.json({
      ok: true,
      totalRetried,
      results,
    });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}
