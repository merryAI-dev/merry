import { addMessage, getMessages } from "@/lib/chatStore";

export type ReportStashItem = {
  itemId: string;
  title: string;
  content: string;
  createdAt: string;
  createdBy?: string;
  source?: Record<string, unknown>;
};

const ROLE_ITEM = "report_stash_item";
const ROLE_UPDATE = "report_stash_update";

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  if (!value || typeof value !== "object") return undefined;
  if (Array.isArray(value)) return undefined;
  return value as Record<string, unknown>;
}

export function inferStashTitleFromContent(content: string): string {
  const text = (content ?? "").trim();
  if (!text) return "초안";

  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  if (!lines.length) return "초안";

  const first = lines[0] ?? "";
  const heading = first.match(/^#{1,6}\s+(.*)$/);
  let title = heading ? (heading[1] ?? "").trim() : first;
  title = title.replace(/\s+/g, " ").trim();
  if (!title) return "초안";
  if (title.length > 64) title = title.slice(0, 61) + "...";
  return title;
}

export async function addReportStashItem(args: {
  teamId: string;
  sessionId: string;
  content: string;
  title?: string;
  createdBy: string;
  source?: Record<string, unknown>;
}): Promise<{ itemId: string }> {
  const now = new Date().toISOString();
  const itemId = crypto.randomUUID().replaceAll("-", "").slice(0, 12);
  const title = (args.title ?? inferStashTitleFromContent(args.content)).trim() || "초안";

  await addMessage({
    teamId: args.teamId,
    sessionId: args.sessionId,
    role: ROLE_ITEM,
    content: args.content,
    metadata: {
      item_id: itemId,
      title,
      created_by: args.createdBy,
      created_at: now,
      ...(args.source ? { source: args.source } : {}),
    },
  });

  return { itemId };
}

export async function removeReportStashItem(args: {
  teamId: string;
  sessionId: string;
  itemId: string;
  updatedBy: string;
}) {
  const now = new Date().toISOString();
  await addMessage({
    teamId: args.teamId,
    sessionId: args.sessionId,
    role: ROLE_UPDATE,
    content: `remove:${args.itemId}`,
    metadata: {
      op: "remove",
      item_id: args.itemId,
      updated_by: args.updatedBy,
      updated_at: now,
    },
  });
}

export async function listReportStashItems(teamId: string, sessionId: string): Promise<ReportStashItem[]> {
  const messages = await getMessages(teamId, sessionId);

  const items: Record<string, ReportStashItem> = {};
  const removed = new Set<string>();

  for (const m of messages) {
    const meta = (m.metadata ?? {}) as Record<string, unknown>;
    const itemId = asString(meta["item_id"]) || asString(m.id);
    if (!itemId) continue;

    if (m.role === ROLE_UPDATE) {
      const op = asString(meta["op"]);
      if (op === "remove") {
        removed.add(itemId);
        delete items[itemId];
      }
      continue;
    }

    if (m.role !== ROLE_ITEM) continue;
    if (removed.has(itemId)) continue;

    const createdAt = asString(meta["created_at"]) || asString(m.created_at) || new Date().toISOString();
    const title = asString(meta["title"]) || inferStashTitleFromContent(m.content);
    const createdBy = asString(meta["created_by"]) || undefined;
    const source = asRecord(meta["source"]);

    items[itemId] = {
      itemId,
      title,
      content: m.content || "",
      createdAt,
      createdBy,
      source,
    };
  }

  return Object.values(items).sort((a, b) => (a.createdAt || "").localeCompare(b.createdAt || ""));
}
