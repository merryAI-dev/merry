export type TokenUsage = {
  inputTokens?: number;
  outputTokens?: number;
};

export type LlmPrice = {
  inputUsdPer1M: number;
  outputUsdPer1M: number;
};

function parseFloatEnv(name: string): number | null {
  const raw = process.env[name];
  if (!raw) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

export function getDefaultPriceForModel(modelId: string): LlmPrice {
  // Optional override for all models.
  const in1m = parseFloatEnv("LLM_INPUT_USD_PER_1M");
  const out1m = parseFloatEnv("LLM_OUTPUT_USD_PER_1M");
  if (in1m != null && out1m != null) return { inputUsdPer1M: in1m, outputUsdPer1M: out1m };

  const m = (modelId || "").toLowerCase();
  // Reasonable defaults (update via env as needed).
  if (m.includes("haiku")) return { inputUsdPer1M: 0.25, outputUsdPer1M: 1.25 };
  if (m.includes("opus")) return { inputUsdPer1M: 15, outputUsdPer1M: 75 };
  // Sonnet as default.
  return { inputUsdPer1M: 6, outputUsdPer1M: 30 };
}

export function estimateUsd(modelId: string, usage: TokenUsage): number {
  const price = getDefaultPriceForModel(modelId);
  const input = usage.inputTokens ?? 0;
  const output = usage.outputTokens ?? 0;
  return (input / 1_000_000) * price.inputUsdPer1M + (output / 1_000_000) * price.outputUsdPer1M;
}

