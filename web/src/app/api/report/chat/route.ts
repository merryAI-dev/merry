import Anthropic from "@anthropic-ai/sdk";
import { InvokeModelWithResponseStreamCommand, type ResponseStream } from "@aws-sdk/client-bedrock-runtime";
import { NextResponse } from "next/server";
import { z } from "zod";

import { addReportMessage, extractFileContexts, buildFileContextBlock } from "@/lib/reportChat";
import { getMessages } from "@/lib/chatStore";
import { getLlmProvider } from "@/lib/llm";
import { getBedrockRuntimeClient } from "@/lib/aws/bedrock";
import { buildMerryPersona } from "@/lib/merryPersona";
import { getJob } from "@/lib/jobStore";
import { getAssumptionPackById, getLatestComputeSnapshot, getLatestLockedAssumptionPack } from "@/lib/reportAssumptionsStore";
import type { Assumption, AssumptionPack } from "@/lib/reportPacks";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";
export const maxDuration = 300;

/** Catch-and-log wrapper: returns null on error instead of silently swallowing. */
function logAndNull<T>(label: string, p: Promise<T>): Promise<T | null> {
  return p.catch((err) => {
    console.warn(`[${label}] suppressed:`, err instanceof Error ? err.message : String(err));
    return null;
  });
}

const BodySchema = z.object({
  sessionId: z.string().min(1).max(128),
  message: z.string().min(1).max(50_000),
  packId: z.string().min(6).max(128).optional(),
  section: z
    .object({
      key: z.string().min(1).max(128),
      title: z.string().min(1).max(500),
      index: z.number().int().positive().optional(),
    })
    .optional(),
  perspective: z.enum(["optimistic", "pessimistic"]).optional(),
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

function summarizeAssumptionPack(pack: AssumptionPack): string {
  const byKey = new Map<string, Assumption>();
  for (const a of pack.assumptions || []) {
    if (!a || typeof a !== "object") continue;
    const key = typeof a.key === "string" ? a.key.trim() : "";
    if (!key) continue;
    byKey.set(key, a);
  }

  const fmt = (key: string) => {
    const a = byKey.get(key);
    if (!a) return `- ${key}: (없음)`;
    const vt = typeof a.valueType === "string" ? a.valueType : "";
    const unit = typeof a.unit === "string" && a.unit.trim() ? ` ${a.unit.trim()}` : "";
    if (vt === "string") {
      const v = typeof a.stringValue === "string" ? a.stringValue.trim() : "";
      return `- ${key}: ${v || "[확인 필요]"}${unit}`;
    }
    if (vt === "number_array") {
      const arr = Array.isArray(a.numberArrayValue) ? a.numberArrayValue : [];
      const nums = arr
        .map((n: unknown) => (typeof n === "number" ? n : Number(n)))
        .filter((n: number) => Number.isFinite(n));
      return `- ${key}: ${nums.length ? `[${nums.join(", ")}]` : "[확인 필요]"}${unit}`;
    }
    const n = typeof a.numberValue === "number" && Number.isFinite(a.numberValue) ? a.numberValue : undefined;
    return `- ${key}: ${typeof n === "number" ? String(n) : "[확인 필요]"}${unit}`;
  };

  const lines = [
    `AssumptionPack(${pack.status}) · ${pack.packId}`,
    fmt("target_year"),
    fmt("investment_year"),
    fmt("investment_date"),
    fmt("investment_amount"),
    fmt("shares"),
    fmt("total_shares"),
    fmt("price_per_share"),
    fmt("net_income_target_year"),
    fmt("per_multiples"),
  ];

  return lines.join("\n");
}

function summarizeExitProjectionMetrics(metrics: unknown): string {
  const r = metrics && typeof metrics === "object" ? (metrics as Record<string, unknown>) : null;
  const rows = r && Array.isArray(r["projection_summary"]) ? (r["projection_summary"] as Record<string, unknown>[]) : [];
  if (!rows.length) return "";

  const parsed = rows
    .map((x) => (x && typeof x === "object" ? (x as Record<string, unknown>) : {}))
    .map((x) => {
      const per = typeof x["PER"] === "number" ? (x["PER"] as number) : Number(x["PER"]);
      const irr = typeof x["IRR"] === "number" ? (x["IRR"] as number) : Number(x["IRR"]);
      const mult = typeof x["Multiple"] === "number" ? (x["Multiple"] as number) : Number(x["Multiple"]);
      return {
        per: Number.isFinite(per) ? per : undefined,
        irr: Number.isFinite(irr) ? irr : undefined,
        multiple: Number.isFinite(mult) ? mult : undefined,
      };
    })
    .filter((x) => typeof x.per === "number");

  const best = parsed
    .filter((x) => typeof x.irr === "number")
    .sort((a, b) => (b.irr ?? -Infinity) - (a.irr ?? -Infinity))[0];

  const sample = parsed.slice(0, 6).map((x) => {
    const irr = typeof x.irr === "number" ? `${x.irr.toFixed(1)}%` : "—";
    const mult = typeof x.multiple === "number" ? `${x.multiple.toFixed(2)}x` : "—";
    return `${x.per}x: IRR ${irr}, Multiple ${mult}`;
  });

  const head = best ? `best: ${best.per}x (IRR ${best.irr?.toFixed(1)}%, Multiple ${best.multiple?.toFixed(2)}x)` : "";
  return ["ExitProjection(projection_summary)", head, ...sample].filter(Boolean).join("\n");
}

function buildSystemPrompt(args: {
  section?: { key: string; title: string; index?: number };
  pack?: AssumptionPack | null;
  computeJob?: { jobId: string; status?: string; metrics?: unknown } | null;
  perspective?: "optimistic" | "pessimistic";
  fileContextBlock?: string;
}) {
  const today = new Date().toLocaleDateString("ko-KR", { timeZone: "Asia/Seoul", year: "numeric", month: "long", day: "numeric" });
  let base =
    buildMerryPersona("report") +
    `- 오늘 날짜: ${today}\n` +
    "- 문서 톤: 인수인의견 스타일(근거 중심, 단정적 과장 금지)\n" +
    "- 출력: Markdown(코드펜스 금지)\n" +
    "- 숫자/지표: Locked AssumptionPack 또는 Compute Snapshot에 있는 값만 사용. 없으면 '이 시나리오는 계산 도구로 확인이 필요해요'라고 안내\n" +
    "- 절대 직접 산술 계산 금지 (IRR, Multiple, 기업가치 등). 반드시 Compute Snapshot 값을 참조\n" +
    "- 섹션 작성: 사용자가 특정 섹션만 요청하면 그 섹션만 작성(다른 섹션 금지)\n" +
    "- UI 액션 문구(예: '초안 확정')를 단독 줄로 출력하지 말 것 (앱에서 버튼으로 제공)\n";

  const packBlock =
    args.pack && args.pack.status === "locked"
      ? `\n[Locked AssumptionPack]\n${summarizeAssumptionPack(args.pack)}\n`
      : "";

  const computeBlock =
    args.computeJob && args.computeJob.jobId
      ? `\n[Compute Snapshot]\n- jobId: ${args.computeJob.jobId}\n- status: ${args.computeJob.status ?? "unknown"}\n${
          args.computeJob.metrics ? summarizeExitProjectionMetrics(args.computeJob.metrics) : ""
        }\n`
      : "";

  const contextBlock = packBlock || computeBlock ? `\n[컨텍스트 스냅샷]\n${packBlock}${computeBlock}` : "";

  // Perspective-specific instructions for debate mode
  if (args.perspective === "optimistic") {
    base +=
      "\n[역할: 긍정 메리 🟢]\n" +
      "- 당신은 이 투자건의 긍정적 관점을 대변하는 역할이에요\n" +
      "- 시장 기회, 팀 역량, 기술 우위, 성장 잠재력에 초점을 맞춰\n" +
      "- 리스크를 인정하되 극복 가능한 방안을 함께 제시해\n" +
      "- 비관 메리의 의견이 맥락에 있다면 건설적으로 반박해\n" +
      "- 간결하게, 핵심 포인트 3-5개로 정리해\n";
  }
  if (args.perspective === "pessimistic") {
    base +=
      "\n[역할: 비관 메리 🔴]\n" +
      "- 당신은 devil's advocate 역할로 투자의 위험 요소를 심층 분석해\n" +
      "- 경쟁 위협, 재무 리스크, 시장 불확실성, 실행 리스크에 초점\n" +
      "- 긍정적 요소가 과대평가되었을 가능성을 지적해\n" +
      "- 긍정 메리의 의견이 맥락에 있다면 논리적으로 반론해\n" +
      "- 간결하게, 핵심 포인트 3-5개로 정리해\n";
  }

  const fileBlock = args.fileContextBlock ?? "";

  if (!args.section) return base + contextBlock + fileBlock;

  const idx = typeof args.section.index === "number" ? `${args.section.index}. ` : "";
  const title = args.section.title.trim();
  return (
    base +
    contextBlock +
    fileBlock +
    `- 이번 응답은 다음 섹션만 작성: ${idx}${title}\n` +
    `- 반드시 제목을 "## ${idx}${title}"로 시작\n` +
    "- 해당 섹션에 필요한 정보가 부족하면 [확인 필요] placeholder를 남기고, 마지막에 질문을 최대 5개만 추가\n"
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

    const requestedPackId = (body.packId ?? "").trim();
    const pack =
      requestedPackId
        ? await logAndNull("getAssumptionPackById", getAssumptionPackById(ws.teamId, body.sessionId, requestedPackId))
        : await logAndNull("getLatestLockedPack", getLatestLockedAssumptionPack(ws.teamId, body.sessionId));

    const snap = await logAndNull("getLatestComputeSnapshot", getLatestComputeSnapshot(ws.teamId, body.sessionId));
    const job = snap ? await logAndNull("getJob", getJob(ws.teamId, snap.jobId)) : null;
    const computeJob = job ? { jobId: job.jobId, status: job.status, metrics: job.metrics } : null;

    await addReportMessage({
      teamId: ws.teamId,
      sessionId: body.sessionId,
      role: "user",
      content: body.message,
      memberName: ws.memberName,
      metadata: {
        ...(body.section ? { section: body.section } : {}),
        ...(body.perspective ? { perspective: body.perspective } : {}),
        ...(pack?.packId ? { packId: pack.packId } : {}),
        ...(computeJob?.jobId ? { computeJobId: computeJob.jobId } : {}),
      },
    });

    // Load all messages in one query, then split into file contexts + chat history.
    const allMessages = await getMessages(ws.teamId, body.sessionId);
    const fileContexts = extractFileContexts(allMessages);
    const fileContextBlock = buildFileContextBlock(fileContexts);

    const maxHistory = body.section ? 8 : 20;
    const chatHistory = allMessages
      .filter((m) => m.role === "user" || m.role === "assistant")
      .slice(-maxHistory);
    const messages = chatHistory
      .map((m) => ({ role: m.role, content: m.content })) as Array<{ role: "user" | "assistant"; content: string }>;

    const maxTokens = Number(process.env.ANTHROPIC_REPORT_MAX_TOKENS ?? "8192");
    const system = buildSystemPrompt({ section: body.section, pack, computeJob, perspective: body.perspective, fileContextBlock });

    const encoder = new TextEncoder();
    let assistantText = "";
    const abortController = new AbortController();

    // Propagate client disconnect to abort in-flight LLM calls.
    if (req.signal) {
      req.signal.addEventListener("abort", () => abortController.abort(), { once: true });
    }

    const readable = new ReadableStream<Uint8Array>({
      async start(controller) {
        try {
          if (provider === "anthropic") {
            const apiKey = process.env.ANTHROPIC_API_KEY;
            if (!apiKey) throw new Error("Missing env ANTHROPIC_API_KEY");
            const client = new Anthropic({ apiKey });
            const model = process.env.ANTHROPIC_REPORT_MODEL ?? "claude-sonnet-4-5-20250929";
            const maxRounds = Math.max(1, Math.min(Number(process.env.REPORT_MAX_CONTINUATIONS ?? "4") + 1, 10));

            let loopMessages = [...messages];
            let totalInputTokens = 0;
            let totalOutputTokens = 0;

            for (let round = 0; round < maxRounds; round++) {
              let roundText = "";
              const stream = client.messages
                .stream(
                  {
                    model,
                    system,
                    max_tokens: maxTokens,
                    messages: loopMessages,
                  },
                  { signal: abortController.signal },
                )
                .on("text", (text) => {
                  roundText += text;
                  assistantText += text;
                  controller.enqueue(encoder.encode(text));
                });

              const final = await stream.finalMessage().catch(() => null);
              const usageRaw = (final as unknown as { usage?: unknown } | null)?.usage as unknown;
              const u = usageRaw && typeof usageRaw === "object" ? (usageRaw as Record<string, unknown>) : {};
              totalInputTokens += typeof u["input_tokens"] === "number" ? (u["input_tokens"] as number) : 0;
              totalOutputTokens += typeof u["output_tokens"] === "number" ? (u["output_tokens"] as number) : 0;

              const stopReason = (final as unknown as { stop_reason?: string } | null)?.stop_reason ?? "end_turn";
              if (stopReason === "max_tokens" && round < maxRounds - 1) {
                loopMessages = [
                  ...loopMessages,
                  { role: "assistant" as const, content: roundText },
                  { role: "user" as const, content: "끊긴 부분부터 이어서 작성해줘. 이전 내용을 반복하지 마." },
                ];
                continue;
              }
              break;
            }

            const usage = {
              inputTokens: totalInputTokens || undefined,
              outputTokens: totalOutputTokens || undefined,
            };

            if (assistantText.trim()) {
              await addReportMessage({
                teamId: ws.teamId,
                sessionId: body.sessionId,
                role: "assistant",
                content: assistantText.trim(),
                memberName: ws.memberName,
                metadata: {
                  ...(body.section ? { section: body.section } : {}),
                  ...(pack?.packId ? { packId: pack.packId } : {}),
                  ...(computeJob?.jobId ? { computeJobId: computeJob.jobId } : {}),
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
          assistantText += "\n";
          controller.enqueue(encoder.encode("\n"));

          const modelId = (process.env.BEDROCK_MODEL_ID ?? "").trim();
          if (!modelId) throw new Error("Missing env BEDROCK_MODEL_ID");

          const bedrockClient = getBedrockRuntimeClient();
          const maxRounds = Math.max(1, Math.min(Number(process.env.REPORT_MAX_CONTINUATIONS ?? "4") + 1, 10));
          let loopMessages = messages.map((m) => ({
            role: m.role,
            content: [{ type: "text" as const, text: m.content }],
          }));
          let totalInputTokens = 0;
          let totalOutputTokens = 0;

          for (let round = 0; round < maxRounds; round++) {
            const payload = {
              anthropic_version: "bedrock-2023-05-31",
              max_tokens: maxTokens,
              temperature: 0.2,
              system,
              messages: loopMessages,
            };

            const resp = await bedrockClient.send(
              new InvokeModelWithResponseStreamCommand({
                modelId,
                contentType: "application/json",
                accept: "application/json",
                body: encoder.encode(JSON.stringify(payload)),
              }),
              { abortSignal: abortController.signal },
            );

            const bedrockStream = resp.body;
            if (!bedrockStream) throw new Error("NO_STREAM");

            const decoder = new TextDecoder("utf-8");
            let carry = "";
            let roundText = "";
            let bedrockStopReason = "end_turn";

            const handleObj = (obj: unknown) => {
              try {
                if (!obj || typeof obj !== "object") return;
                const rec = obj as Record<string, unknown>;
                if (rec["type"] === "message_start") {
                  const msg = rec["message"];
                  const usage = msg && typeof msg === "object" ? (msg as Record<string, unknown>)["usage"] : undefined;
                  const u = usage && typeof usage === "object" ? (usage as Record<string, unknown>) : {};
                  const it = toNumberOrUndefined(u["input_tokens"]);
                  if (it) totalInputTokens += it;
                } else if (rec["type"] === "message_delta") {
                  const usage = rec["usage"];
                  const u = usage && typeof usage === "object" ? (usage as Record<string, unknown>) : {};
                  const ot = toNumberOrUndefined(u["output_tokens"]);
                  if (ot) totalOutputTokens += ot;
                  const delta = rec["delta"];
                  if (delta && typeof delta === "object") {
                    const sr = (delta as Record<string, unknown>)["stop_reason"];
                    if (typeof sr === "string") bedrockStopReason = sr;
                  }
                }
                const text = extractAnthropicDeltaText(obj);
                if (!text) return;
                roundText += text;
                assistantText += text;
                controller.enqueue(encoder.encode(text));
              } catch {
                // Ignore per-chunk errors (e.g. client disconnect) to keep streaming.
              }
            };

            for await (const event of bedrockStream as AsyncIterable<ResponseStream>) {
              const evt = event as unknown as Record<string, unknown>;
              const errEvt =
                (evt.internalServerException ??
                evt.modelStreamErrorException ??
                evt.throttlingException ??
                evt.validationException ??
                evt.serviceUnavailableException) as { message?: string } | undefined;
              if (errEvt) {
                const msg = typeof errEvt.message === "string" ? errEvt.message : "Bedrock stream error";
                throw new Error(msg);
              }

              const chunk = (evt.chunk) as { bytes?: Uint8Array } | undefined;
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
                  // Keep going
                }
              }

              const maybeJson = carry.trim();
              if (maybeJson) {
                try {
                  handleObj(JSON.parse(maybeJson));
                  carry = "";
                } catch {
                  // Likely partial JSON
                }
              }
            }

            carry += decoder.decode();
            for (const line of carry.split(/\r?\n/).map((s) => s.trim()).filter(Boolean)) {
              try {
                handleObj(JSON.parse(line));
              } catch {
                // ignore
              }
            }

            if (bedrockStopReason === "max_tokens" && round < maxRounds - 1) {
              loopMessages = [
                ...loopMessages,
                { role: "assistant" as const, content: [{ type: "text" as const, text: roundText }] },
                { role: "user" as const, content: [{ type: "text" as const, text: "끊긴 부분부터 이어서 작성해줘. 이전 내용을 반복하지 마." }] },
              ];
              continue;
            }
            break;
          }

          if (assistantText.trim()) {
            await addReportMessage({
              teamId: ws.teamId,
              sessionId: body.sessionId,
              role: "assistant",
              content: assistantText.trim(),
              memberName: ws.memberName,
              metadata: {
                ...(body.section ? { section: body.section } : {}),
                ...(pack?.packId ? { packId: pack.packId } : {}),
                ...(computeJob?.jobId ? { computeJobId: computeJob.jobId } : {}),
                llm: {
                  provider: "bedrock",
                  model: modelId,
                  inputTokens: totalInputTokens || undefined,
                  outputTokens: totalOutputTokens || undefined,
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
                  ...(body.section ? { section: body.section } : {}),
                  ...(pack?.packId ? { packId: pack.packId } : {}),
                  ...(computeJob?.jobId ? { computeJobId: computeJob.jobId } : {}),
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
