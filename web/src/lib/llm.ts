import Anthropic from "@anthropic-ai/sdk";
import { InvokeModelCommand } from "@aws-sdk/client-bedrock-runtime";

import { getBedrockRuntimeClient } from "@/lib/aws/bedrock";

export type LlmProvider = "anthropic" | "bedrock";

export type LlmUsage = {
  inputTokens?: number;
  outputTokens?: number;
};

export type LlmTextResult = {
  provider: LlmProvider;
  model: string;
  text: string;
  usage?: LlmUsage;
};

export type LlmMessage = {
  role: "user" | "assistant";
  content: string;
};

function getProvider(): LlmProvider {
  const raw = (process.env.LLM_PROVIDER ?? "anthropic").trim().toLowerCase();
  return raw === "bedrock" ? "bedrock" : "anthropic";
}

export function getLlmProvider(): LlmProvider {
  return getProvider();
}

function getBedrockModelId(): string {
  const id = process.env.BEDROCK_MODEL_ID;
  if (!id) throw new Error("Missing env BEDROCK_MODEL_ID");
  return id;
}

function getAnthropicApiKey(): string {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) throw new Error("Missing env ANTHROPIC_API_KEY");
  return apiKey;
}

function decodeBody(body: Uint8Array | ArrayBuffer | undefined): string {
  if (!body) return "";
  const bytes = body instanceof Uint8Array ? body : new Uint8Array(body);
  return new TextDecoder("utf-8").decode(bytes);
}

function extractTextBlocks(content: unknown): string {
  if (!Array.isArray(content)) return "";
  const parts: string[] = [];
  for (const block of content) {
    if (!block || typeof block !== "object") continue;
    const t = (block as { type?: unknown }).type;
    const s = (block as { text?: unknown }).text;
    if (t === "text" && typeof s === "string") parts.push(s);
  }
  return parts.join("\n").trim();
}

export async function completeText(args: {
  system: string;
  messages: LlmMessage[];
  maxTokens: number;
  temperature?: number;
  model?: string;
}): Promise<LlmTextResult> {
  const provider = getProvider();

  if (provider === "bedrock") {
    // Anthropic models on Bedrock use an Anthropic-shaped request body.
    const modelId = (args.model ?? getBedrockModelId()).trim();
    const client = getBedrockRuntimeClient();

    const payload = {
      anthropic_version: "bedrock-2023-05-31",
      max_tokens: args.maxTokens,
      temperature: args.temperature ?? 0,
      system: args.system,
      messages: args.messages.map((m) => ({
        role: m.role,
        content: [{ type: "text", text: m.content }],
      })),
    };

    const resp = await client.send(
      new InvokeModelCommand({
        modelId,
        contentType: "application/json",
        accept: "application/json",
        body: new TextEncoder().encode(JSON.stringify(payload)),
      }),
    );

    const jsonText = decodeBody(resp.body as unknown as Uint8Array | ArrayBuffer | undefined);
    const parsed = JSON.parse(jsonText) as Record<string, unknown>;
    const text = extractTextBlocks(parsed["content"]);

    const usageRaw = parsed["usage"];
    const usageObj = usageRaw && typeof usageRaw === "object" ? (usageRaw as Record<string, unknown>) : {};
    const inputTokens =
      typeof usageObj["input_tokens"] === "number"
        ? usageObj["input_tokens"]
        : typeof usageObj["inputTokens"] === "number"
          ? usageObj["inputTokens"]
          : undefined;
    const outputTokens =
      typeof usageObj["output_tokens"] === "number"
        ? usageObj["output_tokens"]
        : typeof usageObj["outputTokens"] === "number"
          ? usageObj["outputTokens"]
          : undefined;

    return { provider, model: modelId, text, usage: { inputTokens, outputTokens } };
  }

  const apiKey = getAnthropicApiKey();
  const client = new Anthropic({ apiKey });
  const model = (args.model ?? process.env.ANTHROPIC_MODEL ?? "claude-sonnet-4-5-20250929").trim();

  const resp = await client.messages.create({
    model,
    system: args.system,
    max_tokens: args.maxTokens,
    temperature: args.temperature ?? 0,
    messages: args.messages.map((m) => ({ role: m.role, content: m.content })),
  });

  const text = extractTextBlocks((resp as unknown as { content?: unknown }).content);
  const usageObj = (resp as unknown as { usage?: unknown }).usage as unknown;
  const u = usageObj && typeof usageObj === "object" ? (usageObj as Record<string, unknown>) : {};
  const inputTokens = typeof u["input_tokens"] === "number" ? (u["input_tokens"] as number) : undefined;
  const outputTokens = typeof u["output_tokens"] === "number" ? (u["output_tokens"] as number) : undefined;

  return { provider, model, text, usage: { inputTokens, outputTokens } };
}
