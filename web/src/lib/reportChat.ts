import { addMessage, ensureSession, getMessages, getSessionsByPrefix } from "@/lib/chatStore";
import type { ChatMessageRow } from "@/lib/chatStore";

export type ReportSession = {
  sessionId: string;
  slug: string;
  title: string;
  createdAt?: string;
  fundId?: string;
  fundName?: string;
  companyId?: string;
  companyName?: string;
  reportDate?: string;
  fileTitle?: string;
  author?: string;
};

export type ReportMessage = {
  role: "user" | "assistant";
  content: string;
  createdAt?: string;
  member?: string;
  section?: {
    key: string;
    title: string;
    index?: number;
  };
  perspective?: "optimistic" | "pessimistic" | "synthesis";
};

function reportSessionId(sessionSlug: string) {
  return `report_${sessionSlug}`;
}

export function reportSlugFromSessionId(sessionId: string): string | null {
  if (!sessionId.startsWith("report_")) return null;
  const slug = sessionId.slice("report_".length);
  return slug ? slug : null;
}

export async function listReportSessions(teamId: string, limit = 30): Promise<ReportSession[]> {
  const sessions = await getSessionsByPrefix(teamId, "report_", limit);
  return sessions.map((s) => {
    const info = (s.user_info ?? {}) as Record<string, unknown>;
    return {
      sessionId: s.session_id,
      slug: reportSlugFromSessionId(s.session_id) ?? s.session_id,
      title: typeof info["title"] === "string" ? info["title"] : "투자심사 보고서",
      createdAt: s.created_at,
      fundId: typeof info["fundId"] === "string" ? info["fundId"] : undefined,
      fundName: typeof info["fundName"] === "string" ? info["fundName"] : undefined,
      companyId: typeof info["companyId"] === "string" ? info["companyId"] : undefined,
      companyName: typeof info["companyName"] === "string" ? info["companyName"] : undefined,
      reportDate: typeof info["reportDate"] === "string" ? info["reportDate"] : undefined,
      fileTitle: typeof info["fileTitle"] === "string" ? info["fileTitle"] : undefined,
      author: typeof info["author"] === "string" ? info["author"] : undefined,
    };
  });
}

export async function createReportSession(args: {
  teamId: string;
  memberName: string;
  title?: string;
  fundId?: string;
  fundName?: string;
  companyId?: string;
  companyName?: string;
  reportDate?: string;
  fileTitle?: string;
  author?: string;
}): Promise<{ sessionId: string; slug: string }> {
  const slug = crypto.randomUUID().replaceAll("-", "").slice(0, 12);
  const sessionId = reportSessionId(slug);
  const title = (args.title ?? args.fileTitle ?? "투자심사 보고서").trim();
  const reportDate = (args.reportDate ?? "").trim();
  const fileTitle = (args.fileTitle ?? "").trim();
  const author = (args.author ?? args.memberName ?? "").trim();
  const fundId = (args.fundId ?? "").trim();
  const fundName = (args.fundName ?? "").trim();
  const companyId = (args.companyId ?? "").trim();
  const companyName = (args.companyName ?? "").trim();

  await ensureSession(args.teamId, sessionId, {
    type: "report_chat",
    title,
    created_by: args.memberName,
    fundId,
    fundName,
    companyId,
    companyName,
    reportDate,
    fileTitle,
    author,
  });

  return { sessionId, slug };
}

export async function getReportMessages(teamId: string, sessionId: string, maxMessages?: number): Promise<ReportMessage[]> {
  const messages = await getMessages(teamId, sessionId, maxMessages);
  const out: ReportMessage[] = [];
  for (const m of messages) {
    if (m.role !== "user" && m.role !== "assistant") continue;
    const meta = (m.metadata ?? {}) as Record<string, unknown>;
    const member =
      (typeof meta["member"] === "string" ? meta["member"] : undefined) ||
      (typeof meta["created_by"] === "string" ? meta["created_by"] : undefined) ||
      undefined;
    const sectionRaw = meta["section"];
    const sectionObj = sectionRaw && typeof sectionRaw === "object" ? (sectionRaw as Record<string, unknown>) : null;
    const section =
      sectionObj && typeof sectionObj["key"] === "string" && typeof sectionObj["title"] === "string"
        ? {
            key: (sectionObj["key"] as string).trim(),
            title: (sectionObj["title"] as string).trim(),
            index: typeof sectionObj["index"] === "number" && Number.isFinite(sectionObj["index"]) ? (sectionObj["index"] as number) : undefined,
          }
        : undefined;
    const perspectiveRaw = meta["perspective"];
    const perspective =
      perspectiveRaw === "optimistic" || perspectiveRaw === "pessimistic" || perspectiveRaw === "synthesis" ? perspectiveRaw : undefined;
    out.push({
      role: m.role as "user" | "assistant",
      content: m.content,
      createdAt: m.created_at,
      member,
      section: section && section.key && section.title ? section : undefined,
      perspective,
    });
  }
  return out;
}

/* ── File context (첨부 문서) helpers ── */

const ROLE_FILE_CONTEXT = "report_file_context";

/** Max characters per single file extraction stored in DynamoDB. */
const MAX_FILE_CHARS = 80_000;
/** Combined character budget for all file contexts injected into system prompt. */
export const MAX_COMBINED_FILE_CHARS = 60_000;

export type ReportFileContext = {
  fileId: string;
  originalName: string;
  extractedText: string;
  charCount: number;
  extractedAt: string;
  warnings: string[];
};

/** Truncate extracted text to fit the per-file budget. */
export function truncateExtractedText(text: string, maxChars = MAX_FILE_CHARS): { text: string; truncated: boolean } {
  if (text.length <= maxChars) return { text, truncated: false };
  const headSize = Math.floor(maxChars * 0.67);
  const tailSize = maxChars - headSize - 20; // 20 chars for marker
  return {
    text: text.slice(0, headSize) + "\n\n[... 중략 ...]\n\n" + text.slice(-tailSize),
    truncated: true,
  };
}

export async function addFileContext(args: {
  teamId: string;
  sessionId: string;
  fileId: string;
  originalName: string;
  extractedText: string;
  memberName: string;
  warnings?: string[];
}) {
  const { text: capped } = truncateExtractedText(args.extractedText);
  await addMessage({
    teamId: args.teamId,
    sessionId: args.sessionId,
    role: ROLE_FILE_CONTEXT,
    content: `첨부 문서: ${args.originalName} (${capped.length.toLocaleString()}자)`,
    metadata: {
      mode: "report_chat_upload",
      fileId: args.fileId,
      originalName: args.originalName,
      extractedText: capped,
      charCount: capped.length,
      extractedAt: new Date().toISOString(),
      warnings: args.warnings ?? [],
      member: args.memberName,
    },
  });
}

export function extractFileContexts(allMessages: ChatMessageRow[]): ReportFileContext[] {
  const out: ReportFileContext[] = [];
  for (const m of allMessages) {
    if (m.role !== ROLE_FILE_CONTEXT) continue;
    const meta = (m.metadata ?? {}) as Record<string, unknown>;
    const fileId = typeof meta.fileId === "string" ? meta.fileId : "";
    const originalName = typeof meta.originalName === "string" ? meta.originalName : "";
    const extractedText = typeof meta.extractedText === "string" ? meta.extractedText : "";
    const charCount = typeof meta.charCount === "number" ? meta.charCount : extractedText.length;
    const extractedAt = typeof meta.extractedAt === "string" ? meta.extractedAt : (m.created_at ?? "");
    const warningsRaw = Array.isArray(meta.warnings) ? meta.warnings : [];
    const warnings = warningsRaw.filter((w): w is string => typeof w === "string");
    if (!fileId || !extractedText) continue;
    out.push({ fileId, originalName, extractedText, charCount, extractedAt, warnings });
  }
  return out;
}

/** Build the [첨부 문서] block for the system prompt, respecting combined char budget. */
export function buildFileContextBlock(fileContexts: ReportFileContext[]): string {
  if (!fileContexts.length) return "";

  // Allocate budget: newer files get priority (they come later in the array)
  let remaining = MAX_COMBINED_FILE_CHARS;
  const allocated: { name: string; text: string }[] = [];

  // Process newest first for budget allocation, then reverse for display
  const reversed = [...fileContexts].reverse();
  for (const fc of reversed) {
    if (remaining <= 0) break;
    const budget = Math.min(fc.extractedText.length, remaining);
    const { text } = truncateExtractedText(fc.extractedText, budget);
    allocated.unshift({ name: fc.originalName, text });
    remaining -= text.length;
  }

  if (!allocated.length) return "";

  const lines = ["\n[첨부 문서]"];
  for (const a of allocated) {
    lines.push(`--- 파일: ${a.name} ---`);
    lines.push(a.text);
    lines.push("--- 끝 ---\n");
  }
  return lines.join("\n");
}

/* ── Market intelligence helpers ── */

const ROLE_MARKET_INTEL = "report_market_intel";

export async function addMarketIntel(args: {
  teamId: string;
  sessionId: string;
  content: string;
  memberName: string;
  type: "news" | "signals";
}) {
  await addMessage({
    teamId: args.teamId,
    sessionId: args.sessionId,
    role: ROLE_MARKET_INTEL,
    content: args.content,
    metadata: {
      mode: "report_market_intel",
      type: args.type,
      member: args.memberName,
      created_at: new Date().toISOString(),
    },
  });
}

export function extractMarketIntelBlock(allMessages: ChatMessageRow[]): string {
  // Get the latest market intel message (24h TTL — only use recent ones)
  const cutoff = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
  const intelMessages = allMessages
    .filter((m) => m.role === ROLE_MARKET_INTEL && (m.created_at ?? "") > cutoff)
    .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));

  if (!intelMessages.length) return "";

  // Combine latest news + signals (keep total under 5000 chars)
  const parts: string[] = [];
  let totalLen = 0;
  for (const m of intelMessages) {
    if (totalLen + m.content.length > 5000) break;
    parts.push(m.content);
    totalLen += m.content.length;
  }

  return parts.join("\n");
}

export async function addReportMessage(args: {
  teamId: string;
  sessionId: string;
  role: "user" | "assistant";
  content: string;
  memberName: string;
  metadata?: Record<string, unknown>;
}) {
  await addMessage({
    teamId: args.teamId,
    sessionId: args.sessionId,
    role: args.role,
    content: args.content,
    metadata: {
      mode: "report",
      member: args.memberName,
      created_by: args.memberName,
      created_at: new Date().toISOString(),
      ...(args.metadata ?? {}),
    },
  });
}
