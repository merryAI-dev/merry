import { NextResponse } from "next/server";

import { estimateUsd } from "@/lib/cost";
import { listRecentJobs } from "@/lib/jobStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function extractUsage(job: Record<string, unknown>): { model: string; inputTokens: number; outputTokens: number } | null {
  const usage = (job["usage"] && typeof job["usage"] === "object" ? (job["usage"] as Record<string, unknown>) : {}) as Record<
    string,
    unknown
  >;
  const metrics = (job["metrics"] && typeof job["metrics"] === "object" ? (job["metrics"] as Record<string, unknown>) : {}) as Record<
    string,
    unknown
  >;
  const llm = (metrics["llm"] && typeof metrics["llm"] === "object" ? (metrics["llm"] as Record<string, unknown>) : {}) as Record<
    string,
    unknown
  >;

  const model =
    (typeof usage["model"] === "string" ? usage["model"] : undefined) ||
    (typeof llm["model"] === "string" ? llm["model"] : undefined) ||
    (process.env.BEDROCK_MODEL_ID ?? process.env.ANTHROPIC_MODEL ?? "");

  const inputTokens =
    asNumber(usage["inputTokens"]) ??
    asNumber(usage["input_tokens"]) ??
    asNumber(llm["inputTokens"]) ??
    asNumber(llm["input_tokens"]);
  const outputTokens =
    asNumber(usage["outputTokens"]) ??
    asNumber(usage["output_tokens"]) ??
    asNumber(llm["outputTokens"]) ??
    asNumber(llm["output_tokens"]);

  if (inputTokens == null && outputTokens == null) return null;
  return { model, inputTokens: inputTokens ?? 0, outputTokens: outputTokens ?? 0 };
}

export async function GET(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const url = new URL(req.url);
    const n = Math.max(1, Math.min(5000, Number(url.searchParams.get("n") ?? "200") || 200));
    const type = (url.searchParams.get("type") ?? "").trim();

    const jobs = await listRecentJobs(ws.teamId, 120);
    const filtered = jobs.filter((j) => j.status === "succeeded" && (!type || j.type === type));

    let samples = 0;
    let sumIn = 0;
    let sumOut = 0;
    let sumUsd = 0;

    for (const j of filtered) {
      const u = extractUsage(j as unknown as Record<string, unknown>);
      if (!u) continue;
      samples += 1;
      sumIn += u.inputTokens;
      sumOut += u.outputTokens;
      sumUsd += estimateUsd(u.model, { inputTokens: u.inputTokens, outputTokens: u.outputTokens });
    }

    if (samples === 0) {
      return NextResponse.json({
        ok: true,
        samples: 0,
        note: "No jobs with token usage found yet. Run a few jobs with LLM usage instrumentation enabled.",
      });
    }

    const avgIn = sumIn / samples;
    const avgOut = sumOut / samples;
    const avgUsd = sumUsd / samples;

    return NextResponse.json({
      ok: true,
      samples,
      n,
      type: type || null,
      avgInputTokens: Math.round(avgIn),
      avgOutputTokens: Math.round(avgOut),
      avgUsd: Number(avgUsd.toFixed(4)),
      estimateUsd: Number((avgUsd * n).toFixed(2)),
    });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}

