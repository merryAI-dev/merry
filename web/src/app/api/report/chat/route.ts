import Anthropic from "@anthropic-ai/sdk";
import { NextResponse } from "next/server";
import { z } from "zod";

import { addReportMessage, getReportMessages } from "@/lib/reportChat";
import { completeText, getLlmProvider } from "@/lib/llm";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const BodySchema = z.object({
  sessionId: z.string().min(1),
  message: z.string().min(1),
});

function safeLlmErrorText(err: unknown): string {
  const name = err instanceof Error ? (err.name || "") : "";
  const msg = err instanceof Error ? (err.message || "") : String(err);

  if (msg.startsWith("Missing env ")) {
    return `환경변수 누락: ${msg.replace("Missing env ", "")}`;
  }

  // AWS SDK errors usually carry a name like AccessDeniedException / ValidationException.
  const lower = (msg || "").toLowerCase();
  if (name === "AccessDeniedException" || lower.includes("accessdenied")) {
    return "Bedrock 권한이 없습니다. IAM에 bedrock:InvokeModel 권한 + Bedrock 모델 접근(Model access) 활성화가 필요합니다.";
  }
  if (name === "UnrecognizedClientException" || lower.includes("security token") || lower.includes("invalidsignature")) {
    return "AWS 자격 증명/리전이 올바르지 않습니다. AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY/AWS_REGION을 확인하세요.";
  }
  if (name === "ResourceNotFoundException" || lower.includes("not found")) {
    return "Bedrock 모델을 찾지 못했습니다. BEDROCK_MODEL_ID와 AWS_REGION을 확인하세요.";
  }
  if (name === "ValidationException" && lower.includes("model")) {
    return `Bedrock 요청이 거부되었습니다(모델/요청 형식). BEDROCK_MODEL_ID를 확인하세요. (${name}: ${msg})`;
  }

  const head = name ? `${name}: ` : "";
  const tail = msg ? msg : "Unknown error";
  return `${head}${tail}`;
}

function buildSystemPrompt() {
  return (
    "당신은 투자심사 보고서 초안을 작성하는 VC 애널리스트입니다. 한국어로 답변하세요.\n" +
    "규칙:\n" +
    "- 추측/과장 금지, 근거 불충분하면 '확인 필요'로 명시\n" +
    "- 숫자/지표/계약조건은 사용자가 준 정보에서만 사용\n" +
    "- 출력은 Markdown. 코드펜스 금지.\n" +
    "- 출력 섹션: (1) 요약, (2) 투자포인트, (3) 리스크, (4) 추가질문, (5) 초안 문단\n"
  );
}

export async function POST(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = BodySchema.parse(await req.json());

    if (!body.sessionId.startsWith("report_")) {
      return NextResponse.json({ ok: false, error: "BAD_SESSION" }, { status: 400 });
    }

    const provider = getLlmProvider();

    await addReportMessage({
      teamId: ws.teamId,
      sessionId: body.sessionId,
      role: "user",
      content: body.message,
      memberName: ws.memberName,
    });

    const history = await getReportMessages(ws.teamId, body.sessionId);
    const messages = history
      .slice(-20)
      .map((m) => ({ role: m.role, content: m.content })) as Array<{ role: "user" | "assistant"; content: string }>;

    const maxTokens = Number(process.env.ANTHROPIC_REPORT_MAX_TOKENS ?? "2000");
    const system = buildSystemPrompt();

    const encoder = new TextEncoder();
    let assistantText = "";

    const readable = new ReadableStream<Uint8Array>({
      async start(controller) {
        try {
          if (provider === "anthropic") {
            const apiKey = process.env.ANTHROPIC_API_KEY;
            if (!apiKey) throw new Error("Missing env ANTHROPIC_API_KEY");
            const client = new Anthropic({ apiKey });
            const model = process.env.ANTHROPIC_REPORT_MODEL ?? "claude-sonnet-4-5-20250929";

            const stream = client.messages
              .stream({
                model,
                system,
                max_tokens: maxTokens,
                messages,
              })
              .on("text", (text) => {
                assistantText += text;
                controller.enqueue(encoder.encode(text));
              });

            const final = await stream.finalMessage().catch(() => null);
            const usageRaw = (final as unknown as { usage?: unknown } | null)?.usage as unknown;
            const u = usageRaw && typeof usageRaw === "object" ? (usageRaw as Record<string, unknown>) : {};
            const usage = {
              inputTokens: typeof u["input_tokens"] === "number" ? (u["input_tokens"] as number) : undefined,
              outputTokens: typeof u["output_tokens"] === "number" ? (u["output_tokens"] as number) : undefined,
            };

            if (assistantText.trim()) {
              await addReportMessage({
                teamId: ws.teamId,
                sessionId: body.sessionId,
                role: "assistant",
                content: assistantText.trim(),
                memberName: ws.memberName,
                metadata: {
                  llm: {
                    provider: "anthropic",
                    model,
                    ...usage,
                  },
                },
              });
            }
            controller.close();
            return;
          }

          const resp = await completeText({
            system,
            maxTokens,
            messages,
            temperature: 0.2,
          });
          assistantText = resp.text || "";
          controller.enqueue(encoder.encode(assistantText));

          if (assistantText.trim()) {
            await addReportMessage({
              teamId: ws.teamId,
              sessionId: body.sessionId,
              role: "assistant",
              content: assistantText.trim(),
              memberName: ws.memberName,
              metadata: {
                llm: {
                  provider: resp.provider,
                  model: resp.model,
                  ...(resp.usage ?? {}),
                },
              },
            });
          }
          controller.close();
        } catch (err) {
          // Avoid throwing a stream error (which becomes an opaque client-side failure).
          // Instead, return a visible error message as assistant output for quick debugging.
          const text = `\n\n[LLM ERROR] ${safeLlmErrorText(err)}\n`;
          try {
            controller.enqueue(encoder.encode(text));
          } catch {
            // ignore
          }
          try {
            controller.close();
          } catch {
            // ignore
          }
        }
      },
    });

    return new Response(readable, {
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
        "Cache-Control": "no-store, no-transform",
      },
    });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    const code =
      err instanceof Error && err.message.startsWith("Missing env ")
        ? "MISSING_LLM_CONFIG"
        : "BAD_REQUEST";
    return NextResponse.json({ ok: false, error: code }, { status });
  }
}
