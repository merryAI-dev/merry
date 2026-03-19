/**
 * Failure Pattern Memory — GOLF F(x) = {(y⁽ⁱ⁾, c⁽ⁱ⁾) | r⁽ⁱ⁾ = 0}
 *
 * Tracks structured failure patterns from user feedback (👎 / corrections).
 * 2-hit rule: only inject patterns observed 2+ times (prevents noise bias).
 * 4-week stale rule: patterns not seen in 4 weeks are deactivated.
 */

import { addMessage, getMessages } from "@/lib/chatStore";
import type { ChatMessageRow } from "@/lib/chatStore";

const ROLE_FAILURE_PATTERN = "report_failure_pattern";

export type FailureCategory = "calculation" | "analysis" | "missing_data" | "logic_gap" | "tone";

export type FailurePattern = {
  patternId: string;
  category: FailureCategory;
  description: string;
  correction: string;
  frequency: number;
  firstSeen: string;
  lastSeen: string;
};

const STALE_THRESHOLD_MS = 4 * 7 * 24 * 60 * 60 * 1000; // 4 weeks
const MIN_FREQUENCY_FOR_INJECTION = 2; // 2-hit rule

/** Save a failure pattern observation to DynamoDB. */
export async function recordFailurePattern(args: {
  teamId: string;
  sessionId: string;
  category: FailureCategory;
  description: string;
  correction: string;
  memberName: string;
}) {
  const patternId = `fp_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  await addMessage({
    teamId: args.teamId,
    sessionId: args.sessionId,
    role: ROLE_FAILURE_PATTERN,
    content: `[${args.category}] ${args.description}`,
    metadata: {
      mode: "failure_pattern",
      patternId,
      category: args.category,
      description: args.description,
      correction: args.correction,
      frequency: 1,
      firstSeen: new Date().toISOString(),
      lastSeen: new Date().toISOString(),
      member: args.memberName,
    },
  });
}

/** Extract and aggregate failure patterns from message history. */
export function extractFailurePatterns(allMessages: ChatMessageRow[]): FailurePattern[] {
  const raw: Array<{ category: string; description: string; correction: string; createdAt: string }> = [];

  for (const m of allMessages) {
    if (m.role !== ROLE_FAILURE_PATTERN) continue;
    const meta = (m.metadata ?? {}) as Record<string, unknown>;
    const category = typeof meta.category === "string" ? meta.category : "";
    const description = typeof meta.description === "string" ? meta.description : "";
    const correction = typeof meta.correction === "string" ? meta.correction : "";
    if (!category || !description) continue;
    raw.push({ category, description, correction, createdAt: m.created_at ?? "" });
  }

  // Aggregate by category + similar description (simple dedup by first 50 chars)
  const grouped = new Map<string, FailurePattern>();
  for (const r of raw) {
    const key = `${r.category}::${r.description.slice(0, 50)}`;
    const existing = grouped.get(key);
    if (existing) {
      existing.frequency += 1;
      existing.lastSeen = r.createdAt > existing.lastSeen ? r.createdAt : existing.lastSeen;
      if (r.correction && r.correction.length > existing.correction.length) {
        existing.correction = r.correction;
      }
    } else {
      grouped.set(key, {
        patternId: key,
        category: r.category as FailureCategory,
        description: r.description,
        correction: r.correction,
        frequency: 1,
        firstSeen: r.createdAt,
        lastSeen: r.createdAt,
      });
    }
  }

  const now = Date.now();
  return [...grouped.values()]
    .filter((p) => {
      // Remove stale patterns (4+ weeks since last seen)
      const lastSeenMs = new Date(p.lastSeen).getTime();
      return now - lastSeenMs < STALE_THRESHOLD_MS;
    })
    .sort((a, b) => b.frequency - a.frequency);
}

/** Build system prompt block for failure patterns (2-hit rule applied). */
export function buildFailurePatternBlock(patterns: FailurePattern[]): string {
  const active = patterns.filter((p) => p.frequency >= MIN_FREQUENCY_FOR_INJECTION);
  if (!active.length) return "";

  const lines = ["\n[과거 실수 패턴 — 반복하지 마세요]"];
  for (const p of active.slice(0, 5)) {
    lines.push(`- [${p.category}] ${p.description} → ${p.correction} (${p.frequency}회 관찰)`);
  }
  lines.push("");
  return lines.join("\n");
}
