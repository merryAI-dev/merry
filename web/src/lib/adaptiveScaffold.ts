/**
 * Adaptive Scaffold Injection — GOLF Section 4.2
 *
 * Tracks success/failure rate per session and injects scaffolds
 * only in low-reward regimes (failure rate > τ).
 *
 * Scaffold fading: when failure rate drops below τ, scaffolds are removed
 * to preserve autonomous reasoning (GOLF Table 11: always > adaptive by 27.37%).
 *
 * Vygotsky's ZPD: scaffold only where the learner can't do it alone.
 */

import type { ChatMessageRow } from "@/lib/chatStore";
import type { FailurePattern } from "@/lib/failurePatterns";

const ROLE_RESPONSE_OUTCOME = "report_response_outcome";

/** Default failure rate threshold for scaffold injection. */
const DEFAULT_TAU = 0.5;
/** Number of recent outcomes to consider. */
const WINDOW_SIZE = 6;

export type ResponseOutcome = {
  messageId: string;
  outcome: "success" | "failure";
  timestamp: string;
};

/** Extract response outcomes from message history. */
export function extractOutcomes(allMessages: ChatMessageRow[]): ResponseOutcome[] {
  const outcomes: ResponseOutcome[] = [];
  for (const m of allMessages) {
    if (m.role !== ROLE_RESPONSE_OUTCOME) continue;
    const meta = (m.metadata ?? {}) as Record<string, unknown>;
    const outcome = meta.outcome === "success" || meta.outcome === "failure" ? meta.outcome : null;
    const messageId = typeof meta.messageId === "string" ? meta.messageId : "";
    if (!outcome || !messageId) continue;
    outcomes.push({ messageId, outcome, timestamp: m.created_at ?? "" });
  }
  return outcomes.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
}

/** Calculate recent failure rate within the sliding window. */
export function calculateFailureRate(outcomes: ResponseOutcome[], windowSize = WINDOW_SIZE): number {
  if (outcomes.length === 0) return 0;
  const recent = outcomes.slice(-windowSize);
  const failures = recent.filter((o) => o.outcome === "failure").length;
  return failures / recent.length;
}

/** Determine if scaffold injection should be triggered. */
export function shouldInjectScaffold(outcomes: ResponseOutcome[], tau = DEFAULT_TAU): boolean {
  // Need at least 2 outcomes before making scaffold decisions
  if (outcomes.length < 2) return false;
  return calculateFailureRate(outcomes) > tau;
}

/**
 * Build scaffold block for system prompt injection.
 * Combines failure patterns (warnings) + success patterns (guidance).
 */
export function buildScaffoldBlock(args: {
  failurePatterns: FailurePattern[];
  failureRate: number;
}): string {
  const { failurePatterns, failureRate } = args;

  if (failureRate <= DEFAULT_TAU) return ""; // No scaffold needed — autonomous mode

  const lines = [
    `\n[적응형 가이드 — 최근 실패율 ${(failureRate * 100).toFixed(0)}%]`,
    "최근 응답에서 오류가 감지되어 추가 가이드를 제공합니다:",
    "",
  ];

  // Inject failure pattern warnings
  if (failurePatterns.length > 0) {
    lines.push("**주의 패턴:**");
    for (const p of failurePatterns.slice(0, 3)) {
      lines.push(`- [${p.category}] ${p.description} → 올바른 방법: ${p.correction}`);
    }
    lines.push("");
  }

  // General scaffold guidance
  lines.push("**체크리스트 (응답 전 확인):**");
  lines.push("1. 숫자를 쓰기 전: Compute Snapshot/AssumptionPack에 있는 값인가?");
  lines.push("2. 주장 후: 근거(자료/데이터)를 명시했는가?");
  lines.push("3. 계산이 필요한가? → 직접 계산하지 말고 '계산 도구 필요'로 안내");
  lines.push("");

  return lines.join("\n");
}
