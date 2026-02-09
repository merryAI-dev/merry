import { addMessage, ensureSession, getMessages } from "@/lib/chatStore";

export type TeamDoc = {
  id: string;
  name: string;
  required: boolean;
  uploaded: boolean;
  owner: string;
  notes: string;
  updated_at?: string;
};

export const DEFAULT_REQUIRED_DOCS: Array<{ name: string; required: boolean }> = [
  { name: "회사 소개서/IR Deck", required: true },
  { name: "사업계획서", required: true },
  { name: "재무제표 (최근 2~3년)", required: true },
  { name: "Cap Table", required: true },
  { name: "투자계약서/텀싯", required: true },
  { name: "주요 계약/특허/지식재산", required: false },
  { name: "주요 고객/매출 지표 자료", required: true },
  { name: "인력/조직도", required: false },
  { name: "시장/산업 리서치", required: false },
  { name: "ESG/임팩트 지표", required: false },
];

function docSessionId(teamId: string) {
  return `docs_${teamId}`;
}

export async function listTeamDocs(teamId: string): Promise<TeamDoc[]> {
  const docs: Record<string, TeamDoc> = {};
  const messages = await getMessages(teamId, docSessionId(teamId));
  for (const msg of messages) {
    if (msg.role !== "team_doc") continue;
    const meta = (msg.metadata ?? {}) as Record<string, unknown>;
    const docId = typeof meta["doc_id"] === "string" ? meta["doc_id"] : undefined;
    if (!docId) continue;
    const current = docs[docId];
    if (!current) {
      const name = typeof meta["name"] === "string" ? meta["name"] : msg.content || "";
      const required = Boolean(meta["required"] ?? false);
      const uploaded = Boolean(meta["uploaded"] ?? false);
      const owner = typeof meta["owner"] === "string" ? meta["owner"] : "";
      const notes = typeof meta["notes"] === "string" ? meta["notes"] : "";
      const updated_at =
        (typeof meta["updated_at"] === "string" ? meta["updated_at"] : undefined) ||
        (typeof meta["created_at"] === "string" ? meta["created_at"] : undefined) ||
        msg.created_at;

      docs[docId] = {
        id: docId,
        name,
        required,
        uploaded,
        owner,
        notes,
        updated_at,
      };
      continue;
    }
    if (typeof meta["name"] === "string") current.name = meta["name"] || current.name;
    if (meta["required"] !== undefined) current.required = Boolean(meta["required"]);
    if (meta["uploaded"] !== undefined) current.uploaded = Boolean(meta["uploaded"]);
    if (typeof meta["owner"] === "string") current.owner = meta["owner"] || "";
    if (typeof meta["notes"] === "string") current.notes = meta["notes"] || "";
    const updated_at =
      (typeof meta["updated_at"] === "string" ? meta["updated_at"] : undefined) ||
      (typeof meta["created_at"] === "string" ? meta["created_at"] : undefined) ||
      msg.created_at;
    current.updated_at = updated_at;
  }

  return Object.values(docs).sort((a, b) => {
    if (a.required !== b.required) return a.required ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
}

export async function seedDefaultDocs(teamId: string, createdBy: string) {
  const existing = new Set((await listTeamDocs(teamId)).map((d) => d.name));
  for (const item of DEFAULT_REQUIRED_DOCS) {
    if (existing.has(item.name)) continue;
    await addTeamDoc({
      teamId,
      createdBy,
      name: item.name,
      required: item.required,
    });
  }
}

export async function addTeamDoc(args: {
  teamId: string;
  createdBy: string;
  name: string;
  required?: boolean;
  owner?: string;
  notes?: string;
}): Promise<TeamDoc> {
  const now = new Date().toISOString();
  const id = crypto.randomUUID().replaceAll("-", "").slice(0, 12);
  const doc: TeamDoc = {
    id,
    name: args.name.trim(),
    required: Boolean(args.required ?? true),
    uploaded: false,
    owner: (args.owner ?? "").trim(),
    notes: (args.notes ?? "").trim(),
    updated_at: now,
  };

  const sessionId = docSessionId(args.teamId);
  await ensureSession(args.teamId, sessionId, { type: "doc_checklist" });
  await addMessage({
    teamId: args.teamId,
    sessionId,
    role: "team_doc",
    content: doc.name,
    metadata: {
      doc_id: doc.id,
      name: doc.name,
      required: doc.required,
      uploaded: doc.uploaded,
      owner: doc.owner,
      notes: doc.notes,
      created_by: args.createdBy,
      created_at: now,
      updated_at: now,
    },
  });

  return doc;
}

export async function updateTeamDoc(args: {
  teamId: string;
  updatedBy: string;
  docId: string;
  name?: string;
  required?: boolean;
  uploaded?: boolean;
  owner?: string;
  notes?: string;
}): Promise<void> {
  const payload: Record<string, unknown> = {
    doc_id: args.docId,
    updated_by: args.updatedBy,
    updated_at: new Date().toISOString(),
  };
  if (args.name !== undefined) payload.name = args.name.trim();
  if (args.required !== undefined) payload.required = Boolean(args.required);
  if (args.uploaded !== undefined) payload.uploaded = Boolean(args.uploaded);
  if (args.owner !== undefined) payload.owner = args.owner.trim();
  if (args.notes !== undefined) payload.notes = args.notes.trim();

  const sessionId = docSessionId(args.teamId);
  await ensureSession(args.teamId, sessionId, { type: "doc_checklist" });
  const name = typeof payload["name"] === "string" ? payload["name"] : "";
  await addMessage({
    teamId: args.teamId,
    sessionId,
    role: "team_doc",
    content: name || `doc:${args.docId}`,
    metadata: payload,
  });
}
