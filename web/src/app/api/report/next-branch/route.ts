import { NextResponse } from "next/server";
import { z } from "zod";

import { completeText } from "@/lib/llm";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";
export const maxDuration = 30;

const BodySchema = z.object({
  sessionId: z.string().min(1).max(128),
  decisions: z.array(
    z.object({
      question: z.string(),
      answer: z.string(),
    })
  ),
  companyName: z.string().optional(),
  fundName: z.string().optional(),
});

const SYSTEM_PROMPT = `당신은 VC 투자심사 전문가 메리(Merry)입니다.
심사역이 투자 대상 기업에 대해 의사결정 분기를 진행하고 있습니다.
이전 의사결정 기록을 보고, 다음으로 물어봐야 할 가장 중요한 질문 1개를 생성하세요.

규칙:
- 이미 답변된 질문과 겹치지 않는 새로운 관점의 질문
- 이전 답변을 고려하여 맥락에 맞는 후속 질문 (autoregressive)
- 선택지는 3~5개, 각각 짧고 명확하게
- 질문은 투자심사에 실질적으로 도움이 되는 것
- 반드시 아래 JSON 형식으로만 응답 (다른 텍스트 없이):

{"question":"질문 내용","options":["선택지1","선택지2","선택지3"],"merryComment":"왜 이 질문이 중요한지 한 줄 설명"}`;

export async function POST(req: Request) {
  try {
    await requireWorkspaceFromCookies();
    const body = BodySchema.parse(await req.json());

    const decisionSummary = body.decisions
      .map((d, i) => `${i + 1}. ${d.question} → ${d.answer}`)
      .join("\n");

    const context = [
      body.companyName ? `기업명: ${body.companyName}` : "",
      body.fundName ? `펀드: ${body.fundName}` : "",
    ]
      .filter(Boolean)
      .join("\n");

    const userMessage =
      `지금까지의 의사결정 기록:\n${decisionSummary}\n` +
      (context ? `\n컨텍스트:\n${context}\n` : "") +
      `\n다음 분기 질문을 JSON으로 생성해주세요.`;

    const result = await completeText({
      system: SYSTEM_PROMPT,
      messages: [{ role: "user", content: userMessage }],
      maxTokens: 1024,
      temperature: 0.3,
    });

    // Parse JSON from response — handle potential markdown wrapping
    let text = result.text.trim();
    // Strip markdown code fences if present
    if (text.startsWith("```")) {
      text = text.replace(/^```(?:json)?\n?/, "").replace(/\n?```$/, "").trim();
    }

    const parsed = JSON.parse(text) as {
      question: string;
      options: string[];
      merryComment?: string;
    };

    if (!parsed.question || !Array.isArray(parsed.options)) {
      return NextResponse.json({ ok: false, error: "INVALID_LLM_RESPONSE" }, { status: 500 });
    }

    return NextResponse.json({
      ok: true,
      question: parsed.question,
      options: parsed.options,
      merryComment: parsed.merryComment || "메리가 추천하는 다음 질문이에요.",
    });
  } catch (err) {
    console.error("[next-branch]", err);
    return NextResponse.json(
      { ok: false, error: err instanceof Error ? err.message : "UNKNOWN" },
      { status: 500 }
    );
  }
}
