import { addMessage, ensureSession, getMessages, getSessionsByPrefix } from "@/lib/chatStore";

export type ReportSession = {
  sessionId: string;
  title: string;
  createdAt?: string;
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

export async function listReportSessions(teamId: string, limit = 30): Promise<ReportSession[]> {
  const sessions = await getSessionsByPrefix(teamId, "report_", limit);
  return sessions.map((s) => {
    const info = (s.user_info ?? {}) as Record<string, unknown>;
    return {
      sessionId: s.session_id,
      title: typeof info["title"] === "string" ? info["title"] : "투자심사 보고서",
      createdAt: s.created_at,
    };
  });
}

export async function createReportSession(args: {
  teamId: string;
  memberName: string;
  title?: string;
}): Promise<{ sessionId: string }> {
  const slug = crypto.randomUUID().replaceAll("-", "").slice(0, 12);
  const sessionId = reportSessionId(slug);
  const title = (args.title ?? "투자심사 보고서").trim();

  await ensureSession(args.teamId, sessionId, {
    type: "report_chat",
    title,
    created_by: args.memberName,
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
