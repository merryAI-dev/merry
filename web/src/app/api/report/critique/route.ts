import Anthropic from "@anthropic-ai/sdk";
import { NextResponse } from "next/server";
import { z } from "zod";

import { getLlmProvider } from "@/lib/llm";
import { buildCritiqueMessages, buildRefinementMessages } from "@/lib/selfCritique";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";
export const maxDuration = 120;

const BodySchema = z.object({
  draft: z.string().min(1).max(50_000),
  context: z.string().max(10_000).optional(),
  refine: z.boolean().optional().default(false),
});

export async function POST(req: Request) {
  try {
    await requireWorkspaceFromCookies();
    const body = BodySchema.parse(await req.json());

    const provider = getLlmProvider();
    if (provider !== "anthropic") {
      return NextResponse.json({ ok: false, error: "ANTHROPIC_ONLY" }, { status: 501 });
    }

    const apiKey = process.env.ANTHROPIC_API_KEY;
    if (!apiKey) {
      return NextResponse.json({ ok: false, error: "MISSING_API_KEY" }, { status: 500 });
    }

    const client = new Anthropic({ apiKey });
    const model = process.env.ANTHROPIC_REPORT_MODEL ?? "claude-sonnet-4-5-20250929";

    // Step 1: Generate critique
    const critiqueMessages = buildCritiqueMessages(body.draft, body.context);
    const critiqueResponse = await client.messages.create({
      model,
      max_tokens: 2048,
      messages: critiqueMessages,
    });

    const critiqueText = critiqueResponse.content
      .filter((b): b is Anthropic.TextBlock => b.type === "text")
      .map((b) => b.text)
      .join("");

    if (!body.refine) {
      return NextResponse.json({ ok: true, critique: critiqueText });
    }

    // Step 2: Generate refined draft conditioned on critique
    const refineMessages = buildRefinementMessages(body.draft, critiqueText);
    const refineResponse = await client.messages.create({
      model,
      max_tokens: 4096,
      messages: refineMessages,
    });

    const refinedDraft = refineResponse.content
      .filter((b): b is Anthropic.TextBlock => b.type === "text")
      .map((b) => b.text)
      .join("");

    return NextResponse.json({
      ok: true,
      critique: critiqueText,
      refinedDraft,
    });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}
