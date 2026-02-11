import { NextResponse } from "next/server";
import { z } from "zod";

import { validateAssumptionPack } from "@/lib/assumptionPackValidators";
import { getAssumptionPackById, getPreviousLockedPackBefore, saveAssumptionPack, saveValidationResult } from "@/lib/reportAssumptionsStore";
import type { AssumptionPack } from "@/lib/reportPacks";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const BodySchema = z.object({
  packId: z.string().min(6),
});

export async function POST(req: Request, ctx: { params: Promise<{ sessionId: string }> }) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { sessionId } = await ctx.params;
    if (!sessionId.startsWith("report_")) {
      return NextResponse.json({ ok: false, error: "BAD_SESSION" }, { status: 400 });
    }

    const body = BodySchema.parse(await req.json());
    const current = await getAssumptionPackById(ws.teamId, sessionId, body.packId);
    if (!current) return NextResponse.json({ ok: false, error: "NOT_FOUND" }, { status: 404 });

    const prevLocked = await getPreviousLockedPackBefore(ws.teamId, sessionId, current.createdAt);
    const validated = validateAssumptionPack(current, prevLocked);

    await saveValidationResult({
      teamId: ws.teamId,
      sessionId,
      packId: current.packId,
      status: validated.status,
      checks: validated.checks,
      createdBy: ws.memberName,
    });

    if (validated.status === "fail") {
      return NextResponse.json({ ok: true, status: validated.status, checks: validated.checks });
    }

    const now = new Date().toISOString();
    const next: AssumptionPack = {
      ...validated.normalizedPack,
      packId: crypto.randomUUID(),
      createdAt: now,
      createdBy: ws.memberName,
      status: "validated",
      lineage: { parentPackId: current.packId, reason: "manual" },
    };
    await saveAssumptionPack({ teamId: ws.teamId, sessionId, pack: next });
    return NextResponse.json({ ok: true, status: validated.status, checks: validated.checks, packId: next.packId, pack: next });
  } catch (err) {
    const unauthorized = err instanceof Error && err.message === "UNAUTHORIZED";
    const status = unauthorized ? 401 : 400;
    return NextResponse.json({ ok: false, error: unauthorized ? "UNAUTHORIZED" : "BAD_REQUEST" }, { status });
  }
}

