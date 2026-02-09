import { addMessage, ensureSession, getMessages } from "@/lib/chatStore";

export type TeamCalendarEvent = {
  id: string;
  date: string;
  title: string;
  notes: string;
  created_by: string;
  created_at: string;
};

function calendarSessionId(teamId: string) {
  return `calendar_${teamId}`;
}

export async function listTeamEvents(teamId: string, limit = 50): Promise<TeamCalendarEvent[]> {
  const messages = await getMessages(teamId, calendarSessionId(teamId));
  const events: TeamCalendarEvent[] = [];

  for (const msg of messages) {
    if (msg.role !== "calendar") continue;
    const meta = (msg.metadata ?? {}) as Record<string, unknown>;
    const id =
      (typeof meta["id"] === "string" ? meta["id"] : undefined) ||
      (typeof msg.id === "string" || typeof msg.id === "number" ? String(msg.id) : undefined) ||
      crypto.randomUUID();
    const date = typeof meta["date"] === "string" ? meta["date"] : "";
    const notes = typeof meta["notes"] === "string" ? meta["notes"] : "";
    const created_by =
      (typeof meta["created_by"] === "string" ? meta["created_by"] : undefined) ||
      (typeof meta["createdBy"] === "string" ? meta["createdBy"] : undefined) ||
      "";
    const created_at =
      (typeof meta["created_at"] === "string" ? meta["created_at"] : undefined) ||
      msg.created_at ||
      "";

    events.push({
      id,
      date,
      title: msg.content || "",
      notes,
      created_by,
      created_at,
    });
  }

  return events
    .sort((a, b) => (a.date || "").localeCompare(b.date || ""))
    .slice(0, limit);
}

export async function addTeamEvent(args: {
  teamId: string;
  createdBy: string;
  date: string;
  title: string;
  notes?: string;
}): Promise<TeamCalendarEvent> {
  const now = new Date().toISOString();
  const event: TeamCalendarEvent = {
    id: crypto.randomUUID().replaceAll("-", "").slice(0, 12),
    date: args.date,
    title: args.title.trim(),
    notes: (args.notes ?? "").trim(),
    created_by: args.createdBy,
    created_at: now,
  };

  const sessionId = calendarSessionId(args.teamId);
  await ensureSession(args.teamId, sessionId, { type: "calendar" });
  await addMessage({
    teamId: args.teamId,
    sessionId,
    role: "calendar",
    content: event.title,
    metadata: event,
  });

  return event;
}
