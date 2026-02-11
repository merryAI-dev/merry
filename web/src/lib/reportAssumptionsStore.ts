import { addMessage, getMessages } from "@/lib/chatStore";
import type { AssumptionPack, ComputeSnapshot, CheckResult, ValidationStatus } from "@/lib/reportPacks";

const ROLE_ASSUMPTION_PACK = "report_assumption_pack";
const ROLE_COMPUTE_SNAPSHOT = "report_compute_snapshot";
const ROLE_VALIDATION = "report_validation";

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") return null;
  if (Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

function coerceAssumptionPack(obj: unknown): AssumptionPack | null {
  const r = asRecord(obj);
  if (!r) return null;
  const packId = asString(r.packId);
  const sessionId = asString(r.sessionId);
  const companyName = asString(r.companyName);
  const fundName = asString(r.fundName) || undefined;
  const createdAt = asString(r.createdAt);
  const createdBy = asString(r.createdBy);
  const statusRaw = asString(r.status);
  const status: AssumptionPack["status"] = statusRaw === "validated" || statusRaw === "locked" ? statusRaw : "draft";
  const lineage = asRecord(r.lineage) ?? undefined;
  const factPackId = asString(r.factPackId) || undefined;
  const assumptionsRaw = (r.assumptions as unknown) ?? [];
  const scenariosRaw = (r.scenarios as unknown) ?? [];
  const assumptions = Array.isArray(assumptionsRaw) ? (assumptionsRaw as any[]) : [];
  const scenarios = Array.isArray(scenariosRaw) ? (scenariosRaw as any[]) : [];
  if (!packId || !sessionId || !companyName || !createdAt || !createdBy) return null;
  return {
    packId,
    sessionId,
    companyName,
    fundName,
    createdAt,
    createdBy,
    status,
    lineage: lineage as any,
    factPackId,
    assumptions: assumptions as any,
    scenarios: scenarios as any,
  };
}

function coerceComputeSnapshot(obj: unknown): ComputeSnapshot | null {
  const r = asRecord(obj);
  if (!r) return null;
  const snapshotId = asString(r.snapshotId);
  const sessionId = asString(r.sessionId);
  const packId = asString(r.packId);
  const jobId = asString(r.jobId);
  const createdAt = asString(r.createdAt);
  const createdBy = asString(r.createdBy);
  const derivedSummary = asRecord(r.derivedSummary) ?? undefined;
  if (!snapshotId || !sessionId || !packId || !jobId || !createdAt || !createdBy) return null;
  return { snapshotId, sessionId, packId, jobId, createdAt, createdBy, derivedSummary };
}

export async function saveAssumptionPack(args: { teamId: string; sessionId: string; pack: AssumptionPack }) {
  const summary = `AssumptionPack ${args.pack.packId} (${args.pack.status})`;
  await addMessage({
    teamId: args.teamId,
    sessionId: args.sessionId,
    role: ROLE_ASSUMPTION_PACK,
    content: summary,
    metadata: {
      created_at: new Date().toISOString(),
      assumption_pack: args.pack,
    },
  });
}

export async function getLatestAssumptionPack(teamId: string, sessionId: string): Promise<AssumptionPack | null> {
  const messages = await getMessages(teamId, sessionId);
  const packs: AssumptionPack[] = [];
  for (const m of messages) {
    if (m.role !== ROLE_ASSUMPTION_PACK) continue;
    const meta = asRecord(m.metadata) ?? {};
    const pack = coerceAssumptionPack(meta["assumption_pack"]);
    if (pack) packs.push(pack);
  }
  packs.sort((a, b) => (a.createdAt || "").localeCompare(b.createdAt || ""));
  return packs.length ? packs[packs.length - 1] : null;
}

export async function getAssumptionPackById(teamId: string, sessionId: string, packId: string): Promise<AssumptionPack | null> {
  const id = (packId ?? "").trim();
  if (!id) return null;
  const messages = await getMessages(teamId, sessionId);
  for (const m of messages) {
    if (m.role !== ROLE_ASSUMPTION_PACK) continue;
    const meta = asRecord(m.metadata) ?? {};
    const pack = coerceAssumptionPack(meta["assumption_pack"]);
    if (pack && pack.packId === id) return pack;
  }
  return null;
}

export async function getLatestLockedAssumptionPack(teamId: string, sessionId: string): Promise<AssumptionPack | null> {
  const messages = await getMessages(teamId, sessionId);
  const packs: AssumptionPack[] = [];
  for (const m of messages) {
    if (m.role !== ROLE_ASSUMPTION_PACK) continue;
    const meta = asRecord(m.metadata) ?? {};
    const pack = coerceAssumptionPack(meta["assumption_pack"]);
    if (pack && pack.status === "locked") packs.push(pack);
  }
  packs.sort((a, b) => (a.createdAt || "").localeCompare(b.createdAt || ""));
  return packs.length ? packs[packs.length - 1] : null;
}

export async function getPreviousLockedPackBefore(teamId: string, sessionId: string, createdAt: string): Promise<AssumptionPack | null> {
  const messages = await getMessages(teamId, sessionId);
  const packs: AssumptionPack[] = [];
  for (const m of messages) {
    if (m.role !== ROLE_ASSUMPTION_PACK) continue;
    const meta = asRecord(m.metadata) ?? {};
    const pack = coerceAssumptionPack(meta["assumption_pack"]);
    if (!pack) continue;
    if (pack.status !== "locked") continue;
    if ((pack.createdAt || "") < (createdAt || "")) packs.push(pack);
  }
  packs.sort((a, b) => (a.createdAt || "").localeCompare(b.createdAt || ""));
  return packs.length ? packs[packs.length - 1] : null;
}

export async function saveComputeSnapshot(args: { teamId: string; sessionId: string; snapshot: ComputeSnapshot }) {
  const summary = `ComputeSnapshot ${args.snapshot.jobId} (pack ${args.snapshot.packId})`;
  await addMessage({
    teamId: args.teamId,
    sessionId: args.sessionId,
    role: ROLE_COMPUTE_SNAPSHOT,
    content: summary,
    metadata: {
      created_at: new Date().toISOString(),
      compute_snapshot: args.snapshot,
    },
  });
}

export async function getLatestComputeSnapshot(teamId: string, sessionId: string): Promise<ComputeSnapshot | null> {
  const messages = await getMessages(teamId, sessionId);
  const snaps: ComputeSnapshot[] = [];
  for (const m of messages) {
    if (m.role !== ROLE_COMPUTE_SNAPSHOT) continue;
    const meta = asRecord(m.metadata) ?? {};
    const snap = coerceComputeSnapshot(meta["compute_snapshot"]);
    if (snap) snaps.push(snap);
  }
  snaps.sort((a, b) => (a.createdAt || "").localeCompare(b.createdAt || ""));
  return snaps.length ? snaps[snaps.length - 1] : null;
}

export async function saveValidationResult(args: {
  teamId: string;
  sessionId: string;
  packId: string;
  status: ValidationStatus;
  checks: CheckResult[];
  createdBy: string;
}) {
  await addMessage({
    teamId: args.teamId,
    sessionId: args.sessionId,
    role: ROLE_VALIDATION,
    content: `validation:${args.packId}:${args.status}`,
    metadata: {
      created_at: new Date().toISOString(),
      validation: {
        packId: args.packId,
        status: args.status,
        checks: args.checks,
        createdAt: new Date().toISOString(),
        createdBy: args.createdBy,
      },
    },
  });
}

