import { NextResponse } from "next/server";
import { z } from "zod";

import { getAssumptionPackById, saveAssumptionPack } from "@/lib/reportAssumptionsStore";
import type { Assumption, AssumptionPack, Scenario } from "@/lib/reportPacks";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const BodySchema = z.object({
  pack: z.unknown(),
});

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") return null;
  if (Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

function asOptionalString(value: unknown): string | undefined {
  const s = typeof value === "string" ? value.trim() : "";
  return s ? s : undefined;
}

function coerceAssumptions(raw: unknown): Assumption[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((x) => (x && typeof x === "object" ? (x as Record<string, unknown>) : {}))
    .map((r) => {
      const key = asString(r["key"]).trim();
      const valueTypeRaw = asString(r["valueType"]).trim();
      const valueType: Assumption["valueType"] =
        valueTypeRaw === "string" || valueTypeRaw === "number_array" ? (valueTypeRaw as any) : "number";
      const numberValue = typeof r["numberValue"] === "number" ? (r["numberValue"] as number) : undefined;
      const stringValue = typeof r["stringValue"] === "string" ? (r["stringValue"] as string) : undefined;
      const numberArrayValue = Array.isArray(r["numberArrayValue"])
        ? (r["numberArrayValue"] as unknown[])
            .map((n) => (typeof n === "number" ? n : Number(n)))
            .filter((n) => Number.isFinite(n))
        : undefined;
      const unit = asOptionalString(r["unit"]);
      const required = Boolean(r["required"]);
      const evidenceRaw = r["evidence"];
      const evidence = Array.isArray(evidenceRaw)
        ? evidenceRaw
            .map((e) => (e && typeof e === "object" ? (e as Record<string, unknown>) : {}))
            .map((e) => (typeof e["factId"] === "string" && e["factId"].trim() ? { factId: e["factId"].trim() } : typeof e["note"] === "string" && e["note"].trim() ? { note: e["note"].trim() } : null))
            .filter(Boolean) as any
        : [];
      return { key, valueType, numberValue, stringValue, numberArrayValue, unit, required, evidence };
    })
    .filter((a) => a.key);
}

function coerceScenarios(raw: unknown): Scenario[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((x) => (x && typeof x === "object" ? (x as Record<string, unknown>) : {}))
    .map((r) => {
      const keyRaw = asString(r["key"]).trim();
      const key: Scenario["key"] = keyRaw === "bull" || keyRaw === "bear" ? (keyRaw as any) : "base";
      const title = asString(r["title"]).trim() || (key === "base" ? "Base" : key === "bull" ? "Bull" : "Bear");
      const overridesRaw = r["overrides"];
      const overrides = Array.isArray(overridesRaw) ? (overridesRaw as any[]) : [];
      return { key, title, overrides };
    });
}

export async function POST(req: Request, ctx: { params: Promise<{ sessionId: string }> }) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { sessionId } = await ctx.params;
    if (!sessionId.startsWith("report_")) {
      return NextResponse.json({ ok: false, error: "BAD_SESSION" }, { status: 400 });
    }

    const body = BodySchema.parse(await req.json());
    const rec = asRecord(body.pack);
    if (!rec) return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status: 400 });

    const parentPackId = asOptionalString(rec["packId"]);
    const companyName = asString(rec["companyName"]).trim();
    if (!companyName) return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status: 400 });

    const now = new Date().toISOString();
    const nextPackId = crypto.randomUUID();
    const pack: AssumptionPack = {
      packId: nextPackId,
      sessionId,
      companyName,
      fundName: asOptionalString(rec["fundName"]),
      createdAt: now,
      createdBy: ws.memberName,
      status: "draft",
      lineage: parentPackId ? { parentPackId, reason: "manual" } : { reason: "manual" },
      factPackId: asOptionalString(rec["factPackId"]),
      assumptions: coerceAssumptions(rec["assumptions"]),
      scenarios: coerceScenarios(rec["scenarios"]),
    };

    await saveAssumptionPack({ teamId: ws.teamId, sessionId, pack });

    // If parent exists but cannot be found, still allow save (client-side edits).
    if (parentPackId) {
      await getAssumptionPackById(ws.teamId, sessionId, parentPackId).catch(() => null);
    }

    return NextResponse.json({ ok: true, packId: pack.packId, pack });
  } catch (err) {
    const unauthorized = err instanceof Error && err.message === "UNAUTHORIZED";
    const status = unauthorized ? 401 : 400;
    return NextResponse.json({ ok: false, error: unauthorized ? "UNAUTHORIZED" : "BAD_REQUEST" }, { status });
  }
}

