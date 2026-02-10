import { addMessage, ensureSession, getMessages, getSessionsByPrefix } from "@/lib/chatStore";

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
}): Promise<{ sessionId: string }> {
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

  return { sessionId };
}

export async function getReportMessages(teamId: string, sessionId: string): Promise<ReportMessage[]> {
  const messages = await getMessages(teamId, sessionId);
  const out: ReportMessage[] = [];
  for (const m of messages) {
    if (m.role !== "user" && m.role !== "assistant") continue;
    const meta = (m.metadata ?? {}) as Record<string, unknown>;
    const member =
      (typeof meta["member"] === "string" ? meta["member"] : undefined) ||
      (typeof meta["created_by"] === "string" ? meta["created_by"] : undefined) ||
      undefined;
    out.push({
      role: m.role as "user" | "assistant",
      content: m.content,
      createdAt: m.created_at,
      member,
    });
  }
  return out;
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
