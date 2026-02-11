import { addMessage, getMessages } from "@/lib/chatStore";
import type { FactPack } from "@/lib/reportPacks";

const ROLE_FACT_PACK = "report_fact_pack";

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") return null;
  if (Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

function coerceFactPack(obj: unknown): FactPack | null {
  const r = asRecord(obj);
  if (!r) return null;
  const factPackId = asString(r.factPackId);
  const sessionId = asString(r.sessionId);
  const createdAt = asString(r.createdAt);
  const createdBy = asString(r.createdBy);
  const inputs = asRecord(r.inputs) ?? {};
  const jobIdsRaw = (inputs["jobIds"] as unknown) ?? [];
  const fileIdsRaw = (inputs["fileIds"] as unknown) ?? [];
  const jobIds = Array.isArray(jobIdsRaw) ? jobIdsRaw.map(asString).filter(Boolean) : [];
  const fileIds = Array.isArray(fileIdsRaw) ? fileIdsRaw.map(asString).filter(Boolean) : [];
  const factsRaw = (r.facts as unknown) ?? [];
  const facts = Array.isArray(factsRaw) ? (factsRaw as any[]) : [];
  const warningsRaw = (r.warnings as unknown) ?? [];
  const warnings = Array.isArray(warningsRaw) ? warningsRaw.map(asString).filter(Boolean) : [];
  if (!factPackId || !sessionId || !createdAt || !createdBy) return null;
  return {
    factPackId,
    sessionId,
    createdAt,
    createdBy,
    inputs: { jobIds, fileIds },
    facts: facts as any,
    warnings,
  };
}

export async function saveFactPack(args: { teamId: string; sessionId: string; pack: FactPack }) {
  const summary = `FactPack ${args.pack.factPackId} (${args.pack.facts.length} facts)`;
  await addMessage({
    teamId: args.teamId,
    sessionId: args.sessionId,
    role: ROLE_FACT_PACK,
    content: summary,
    metadata: {
      created_at: new Date().toISOString(),
      fact_pack: args.pack,
    },
  });
}

export async function getLatestFactPack(teamId: string, sessionId: string): Promise<FactPack | null> {
  const messages = await getMessages(teamId, sessionId);
  const packs: FactPack[] = [];
  for (const m of messages) {
    if (m.role !== ROLE_FACT_PACK) continue;
    const meta = asRecord(m.metadata) ?? {};
    const pack = coerceFactPack(meta["fact_pack"]);
    if (pack) packs.push(pack);
  }
  packs.sort((a, b) => (a.createdAt || "").localeCompare(b.createdAt || ""));
  return packs.length ? packs[packs.length - 1] : null;
}

export async function getFactPackById(teamId: string, sessionId: string, factPackId: string): Promise<FactPack | null> {
  const id = (factPackId ?? "").trim();
  if (!id) return null;
  const messages = await getMessages(teamId, sessionId);
  for (const m of messages) {
    if (m.role !== ROLE_FACT_PACK) continue;
    const meta = asRecord(m.metadata) ?? {};
    const pack = coerceFactPack(meta["fact_pack"]);
    if (pack && pack.factPackId === id) return pack;
  }
  return null;
}

