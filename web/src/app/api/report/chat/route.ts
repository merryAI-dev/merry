import Anthropic from "@anthropic-ai/sdk";
import { InvokeModelWithResponseStreamCommand } from "@aws-sdk/client-bedrock-runtime";
import { NextResponse } from "next/server";
import { z } from "zod";

import { addReportMessage, getReportMessages } from "@/lib/reportChat";
import { getLlmProvider } from "@/lib/llm";
import { getBedrockRuntimeClient } from "@/lib/aws/bedrock";
import { buildMerryPersona } from "@/lib/merryPersona";
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
  if (lower.includes("use case details") || lower.includes("anthropic use case")) {
    return "Bedrock에서 Anthropic 모델 사용 케이스(Use case details) 제출이 필요합니다. AWS 콘솔 Bedrock > Model access에서 Anthropic 항목을 열고 폼 제출 후 10-15분 뒤 재시도하세요.";
  }
  if (name === "ResourceNotFoundException" || lower.includes("not found")) {
    return "Bedrock 모델을 찾지 못했습니다. BEDROCK_MODEL_ID와 AWS_REGION을 확인하세요.";
  }
  if (name === "ValidationException" && lower.includes("on-demand throughput")) {
    return "해당 Anthropic 모델은 on-demand 호출이 불가합니다. BEDROCK_MODEL_ID를 inference profile ID/ARN으로 설정해야 합니다. 예: apac.anthropic.claude-3-5-sonnet-20241022-v2:0";
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
    buildMerryPersona("report") +
    "- 출력 섹션:\n" +
    "  (1) 시장규모 근거 요약\n" +
    "  (2) 요약(투자 가부는 보류 가능)\n" +
    "  (3) 투자포인트(3-5개)\n" +
    "  (4) 리스크(법무/재무/사업/시장)\n" +
    "  (5) 추가 질문(최대 8개)\n" +
    "  (6) 초안 문단(인수인의견 톤)\n"
  );
}

function toNumberOrUndefined(v: unknown): number | undefined {
  return typeof v === "number" && Number.isFinite(v) ? v : undefined;
}

function extractAnthropicDeltaText(obj: unknown): string {
  if (!obj || typeof obj !== "object") return "";
  const rec = obj as Record<string, unknown>;

  // Primary: Messages API streaming deltas.
  if (rec["type"] === "content_block_delta") {
    const delta = rec["delta"];
    if (delta && typeof delta === "object") {
      const d = delta as Record<string, unknown>;
      const text = d["text"];
      if (typeof text === "string") return text;
    }
  }

  // Some runtimes may send completion-style chunks.
  const completion = rec["completion"];
  if (typeof completion === "string") return completion;

  return "";
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
    const abortController = new AbortController();

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

          // Bedrock streaming (avoids Vercel first-byte timeout).
          // Send a small prelude first so the client receives bytes immediately; it's trimmed before persistence.
          assistantText += "\n";
          controller.enqueue(encoder.encode("\n"));

          const modelId = (process.env.BEDROCK_MODEL_ID ?? "").trim();
          if (!modelId) throw new Error("Missing env BEDROCK_MODEL_ID");

          const client = getBedrockRuntimeClient();
          const payload = {
            anthropic_version: "bedrock-2023-05-31",
            max_tokens: maxTokens,
            temperature: 0.2,
            system,
            messages: messages.map((m) => ({
              role: m.role,
              content: [{ type: "text", text: m.content }],
            })),
          };

          const resp = await client.send(
            new InvokeModelWithResponseStreamCommand({
              modelId,
              contentType: "application/json",
              accept: "application/json",
              body: encoder.encode(JSON.stringify(payload)),
            }),
            { abortSignal: abortController.signal },
          );

          const stream = resp.body;
          if (!stream) throw new Error("NO_STREAM");

          let inputTokens: number | undefined;
          let outputTokens: number | undefined;
          const decoder = new TextDecoder("utf-8");
          let carry = "";

          const handleObj = (obj: unknown) => {
            // Usage appears on message_start / message_delta for Anthropic.
            if (obj && typeof obj === "object") {
              const rec = obj as Record<string, unknown>;
              if (rec["type"] === "message_start") {
                const msg = rec["message"];
                const usage = msg && typeof msg === "object" ? (msg as Record<string, unknown>)["usage"] : undefined;
                const u = usage && typeof usage === "object" ? (usage as Record<string, unknown>) : {};
                inputTokens = inputTokens ?? toNumberOrUndefined(u["input_tokens"]);
                outputTokens = outputTokens ?? toNumberOrUndefined(u["output_tokens"]);
              } else if (rec["type"] === "message_delta") {
                const usage = rec["usage"];
                const u = usage && typeof usage === "object" ? (usage as Record<string, unknown>) : {};
                outputTokens = toNumberOrUndefined(u["output_tokens"]) ?? outputTokens;
              }
            }

            const text = extractAnthropicDeltaText(obj);
            if (!text) return;
            assistantText += text;
            controller.enqueue(encoder.encode(text));
          };

          for await (const event of stream as any) {
            const evt = event as any;
            const errEvt =
              evt?.internalServerException ??
              evt?.modelStreamErrorException ??
              evt?.throttlingException ??
              evt?.validationException ??
              evt?.serviceUnavailableException;
            if (errEvt) {
              const msg = typeof errEvt?.message === "string" ? errEvt.message : "Bedrock stream error";
              throw new Error(msg);
            }

            const chunk = (event as any)?.chunk;
            const bytes: Uint8Array | undefined = chunk?.bytes;
            if (!bytes) continue;

            carry += decoder.decode(bytes, { stream: true });

            while (true) {
              const nl = carry.indexOf("\n");
              if (nl === -1) break;
              const line = carry.slice(0, nl).trim();
              carry = carry.slice(nl + 1);
              if (!line) continue;
              try {
                handleObj(JSON.parse(line));
              } catch {
                // Keep going; worst-case we drop one malformed line.
              }
            }

            const maybeJson = carry.trim();
            if (maybeJson) {
              try {
                handleObj(JSON.parse(maybeJson));
                carry = "";
              } catch {
                // Likely partial JSON; wait for more bytes.
              }
            }
          }

          // Flush any remaining decoder bytes and try one last parse pass.
          carry += decoder.decode();
          for (const line of carry.split(/\r?\n/).map((s) => s.trim()).filter(Boolean)) {
            try {
              handleObj(JSON.parse(line));
            } catch {
              // ignore
            }
          }

          if (assistantText.trim()) {
            await addReportMessage({
              teamId: ws.teamId,
              sessionId: body.sessionId,
              role: "assistant",
              content: assistantText.trim(),
              memberName: ws.memberName,
              metadata: {
                llm: {
                  provider: "bedrock",
                  model: modelId,
                  inputTokens,
                  outputTokens,
                },
              },
            });
          }
          controller.close();
        } catch (err) {
          // Avoid throwing a stream error (which becomes an opaque client-side failure).
          // Instead, return a visible error message as assistant output for quick debugging.
          const text = `\n\n[LLM ERROR] ${safeLlmErrorText(err)}\n`;
          assistantText += text;
          try {
            controller.enqueue(encoder.encode(text));
          } catch {
            // ignore
          }
          try {
            if (assistantText.trim()) {
              const p = getLlmProvider();
              const model =
                p === "anthropic"
                  ? (process.env.ANTHROPIC_REPORT_MODEL ?? "claude-sonnet-4-5-20250929").trim()
                  : (process.env.BEDROCK_MODEL_ID ?? "").trim();
              await addReportMessage({
                teamId: ws.teamId,
                sessionId: body.sessionId,
                role: "assistant",
                content: assistantText.trim(),
                memberName: ws.memberName,
                metadata: {
                  llm: { provider: p, model, error: true },
                },
              });
            }
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
      cancel() {
        try {
          abortController.abort();
        } catch {
          // ignore
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
