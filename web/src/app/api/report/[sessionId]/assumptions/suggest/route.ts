import { NextResponse } from "next/server";
import { z } from "zod";

import { completeText } from "@/lib/llm";
import { getSession } from "@/lib/chatStore";
import { getFactPackById, getLatestFactPack } from "@/lib/reportFactsStore";
import { saveAssumptionPack } from "@/lib/reportAssumptionsStore";
import type { Assumption, AssumptionPack, Scenario } from "@/lib/reportPacks";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const BodySchema = z.object({
  factPackId: z.string().optional(),
  mode: z.enum(["exit_projection", "report_base"]),
});

function extractJsonObject(text: string): any | null {
  const s = (text ?? "").trim();
  if (!s) return null;
  const start = s.indexOf("{");
  const end = s.lastIndexOf("}");
  if (start === -1 || end === -1 || end <= start) return null;
  const slice = s.slice(start, end + 1);
  try {
    return JSON.parse(slice);
  } catch {
    return null;
  }
}

function ensureThreeScenarios(raw: unknown): Scenario[] {
  const arr = Array.isArray(raw) ? raw : [];
  const out: Scenario[] = [];
  const seen = new Set<string>();
  for (const it of arr) {
    if (!it || typeof it !== "object") continue;
    const r = it as Record<string, unknown>;
    const k = typeof r["key"] === "string" ? r["key"].trim() : "";
    const key: Scenario["key"] = k === "bull" || k === "bear" ? (k as any) : "base";
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({
      key,
      title: typeof r["title"] === "string" && r["title"].trim() ? r["title"].trim() : key.toUpperCase(),
      overrides: Array.isArray(r["overrides"]) ? (r["overrides"] as any) : [],
    });
  }
  const need = (k: Scenario["key"], title: string) => ({ key: k, title, overrides: [] });
  if (!seen.has("base")) out.push(need("base", "Base"));
  if (!seen.has("bull")) out.push(need("bull", "Bull"));
  if (!seen.has("bear")) out.push(need("bear", "Bear"));
  out.sort((a, b) => (a.key === "base" ? -1 : a.key === "bull" && b.key === "bear" ? -1 : 1));
  return out;
}

function upsertRequiredAssumptions(list: Assumption[]): Assumption[] {
  const required: Array<{ key: string; valueType: Assumption["valueType"]; unit?: string }> = [
    { key: "target_year", valueType: "number", unit: "year" },
    { key: "investment_year", valueType: "number", unit: "year" },
    { key: "investment_date", valueType: "string" },
    { key: "investment_amount", valueType: "number", unit: "KRW" },
    { key: "shares", valueType: "number", unit: "shares" },
    { key: "total_shares", valueType: "number", unit: "shares" },
    { key: "price_per_share", valueType: "number", unit: "KRW" },
    { key: "net_income_target_year", valueType: "number", unit: "KRW" },
    { key: "per_multiples", valueType: "number_array", unit: "x" },
  ];

  const byKey = new Map<string, Assumption>();
  for (const a of list) {
    const k = (a?.key ?? "").trim();
    if (!k) continue;
    byKey.set(k, { ...a, key: k });
  }

  for (const r of required) {
    if (byKey.has(r.key)) {
      const cur = byKey.get(r.key)!;
      byKey.set(r.key, { ...cur, required: true, valueType: cur.valueType || r.valueType, unit: cur.unit || r.unit });
      continue;
    }
    byKey.set(r.key, {
      key: r.key,
      valueType: r.valueType,
      unit: r.unit,
      required: true,
      evidence: [{ note: "확인 필요" }],
    });
  }

  return Array.from(byKey.values());
}

export async function POST(req: Request, ctx: { params: Promise<{ sessionId: string }> }) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { sessionId } = await ctx.params;
    if (!sessionId.startsWith("report_")) {
      return NextResponse.json({ ok: false, error: "BAD_SESSION" }, { status: 400 });
    }

    const body = BodySchema.parse(await req.json());

    const session = await getSession(ws.teamId, sessionId);
    const info = (session?.user_info ?? {}) as Record<string, unknown>;
    const companyName = typeof info["companyName"] === "string" ? info["companyName"] : "회사";
    const fundName = typeof info["fundName"] === "string" ? info["fundName"] : undefined;

    const factPack =
      body.factPackId ? await getFactPackById(ws.teamId, sessionId, body.factPackId) : await getLatestFactPack(ws.teamId, sessionId);

    const factLines = (factPack?.facts || [])
      .slice(0, 40)
      .map((f) => {
        const val = f.valueType === "number" ? `${f.numberValue ?? ""}${f.unit ? ` ${f.unit}` : ""}` : `${f.stringValue ?? ""}`;
        return `- ${f.factId} | ${f.key} = ${String(val).slice(0, 180)}`;
      })
      .join("\n");

    const system =
      "당신은 VC 투자검토 시스템의 '가정(AssumptionPack) 생성기'입니다.\n" +
      "출력은 반드시 JSON만 (마크다운/코드펜스/설명 문장 금지).\n" +
      "규칙:\n" +
      "- 숫자를 '추측'해서 채우지 말 것. 모르면 numberValue/stringValue/numberArrayValue를 비워두고 evidence에 {\"note\":\"확인 필요\"} 추가\n" +
      "- FactPack에서 근거를 쓴 경우 evidence에 {\"factId\":\"...\"}로 연결\n" +
      "- per_multiples는 1~200, 최대 12개, 중복 제거\n" +
      "- 시나리오는 base/bull/bear 3개를 기본 제공\n";

    const user =
      `세션: ${sessionId}\n` +
      `회사명: ${companyName}\n` +
      (fundName ? `펀드: ${fundName}\n` : "") +
      (factPack ? `FactPackId: ${factPack.factPackId}\n` : "FactPackId: (없음)\n") +
      "\n요청: Exit Projection 계산을 위한 AssumptionPack 초안을 만들어줘.\n" +
      "\n반드시 포함할 assumptions.key 목록:\n" +
      "- target_year (number)\n" +
      "- investment_year (number) 또는 investment_date (string)\n" +
      "- investment_amount (number)\n" +
      "- shares (number)\n" +
      "- total_shares (number)\n" +
      "- price_per_share (number)\n" +
      "- net_income_target_year (number)\n" +
      "- per_multiples (number_array)\n" +
      "\nFactPack (있으면 참고):\n" +
      (factLines ? `${factLines}\n` : "- (없음)\n") +
      "\nJSON 스키마:\n" +
      "{\n" +
      '  "assumptions": [ { "key": "...", "valueType":"number|string|number_array", "numberValue"?:0, "stringValue"?:\"\", "numberArrayValue"?:[], "unit"?:\"\", "required": true, "evidence":[{\"factId\":\"...\"}|{\"note\":\"...\"}] } ],\n' +
      '  "scenarios": [ { "key":"base|bull|bear", "title":"...", "overrides":[] } ]\n' +
      "}\n";

    const llm = await completeText({
      system,
      messages: [{ role: "user", content: user }],
      maxTokens: 1600,
      temperature: 0,
    });

    const parsed = extractJsonObject(llm.text) ?? {};
    const assumptionsRaw = Array.isArray(parsed.assumptions) ? parsed.assumptions : [];
    const assumptions = upsertRequiredAssumptions(assumptionsRaw as any);
    const scenarios = ensureThreeScenarios(parsed.scenarios);

    const now = new Date().toISOString();
    const pack: AssumptionPack = {
      packId: crypto.randomUUID(),
      sessionId,
      companyName,
      fundName,
      createdAt: now,
      createdBy: ws.memberName,
      status: "draft",
      lineage: { reason: "manual" },
      factPackId: factPack?.factPackId,
      assumptions,
      scenarios,
    };

    await saveAssumptionPack({ teamId: ws.teamId, sessionId, pack });
    return NextResponse.json({ ok: true, pack });
  } catch (err) {
    const unauthorized = err instanceof Error && err.message === "UNAUTHORIZED";
    const status = unauthorized ? 401 : 400;
    return NextResponse.json({ ok: false, error: unauthorized ? "UNAUTHORIZED" : "BAD_REQUEST" }, { status });
  }
}

