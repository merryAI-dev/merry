import { GetObjectCommand } from "@aws-sdk/client-s3";
import { NextResponse } from "next/server";
import { z } from "zod";

import { getS3Client } from "@/lib/aws/s3";
import { getJob } from "@/lib/jobStore";
import { saveFactPack } from "@/lib/reportFactsStore";
import type { Fact, FactPack } from "@/lib/reportPacks";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const BodySchema = z.object({
  sourceJobIds: z.array(z.string().min(1)).min(1).max(6),
});

async function readBodyToString(body: any): Promise<string> {
  if (!body) return "";
  // AWS SDK v3 in Node returns a Readable with async iterator.
  if (typeof body === "string") return body;
  if (body instanceof Uint8Array) return new TextDecoder("utf-8").decode(body);
  const chunks: Uint8Array[] = [];
  for await (const chunk of body as AsyncIterable<Uint8Array>) {
    chunks.push(typeof chunk === "string" ? new TextEncoder().encode(chunk) : chunk);
  }
  const total = chunks.reduce((n, c) => n + c.length, 0);
  const merged = new Uint8Array(total);
  let offset = 0;
  for (const c of chunks) {
    merged.set(c, offset);
    offset += c.length;
  }
  return new TextDecoder("utf-8").decode(merged);
}

function parseFirstNumber(text: string): number | undefined {
  const m = (text ?? "").match(/([-+]?\d+(?:\.\d+)?)/);
  if (!m) return undefined;
  const n = Number(m[1]);
  return Number.isFinite(n) ? n : undefined;
}

function inferUnit(text: string): string | undefined {
  const t = (text ?? "").toLowerCase();
  if (t.includes("%") || t.includes("퍼센트") || t.includes("percent")) return "%";
  if (t.includes("krw") || t.includes("₩") || t.includes("원")) return "KRW";
  if (t.includes("usd") || t.includes("달러") || t.includes("$")) return "USD";
  if (t.includes("year") || t.includes("년")) return "year";
  return undefined;
}

function trimText(s: string, max = 320): string {
  const t = (s ?? "").trim().replaceAll("\r\n", "\n");
  if (t.length <= max) return t;
  return t.slice(0, max - 3) + "...";
}

function coerceEvidenceArray(obj: unknown): Array<Record<string, unknown>> {
  if (!obj || typeof obj !== "object") return [];
  const rec = obj as Record<string, unknown>;
  const ev = rec["evidence"];
  if (!Array.isArray(ev)) return [];
  return ev.map((x) => (x && typeof x === "object" ? (x as Record<string, unknown>) : {}));
}

export async function POST(req: Request, ctx: { params: Promise<{ sessionId: string }> }) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { sessionId } = await ctx.params;
    if (!sessionId.startsWith("report_")) {
      return NextResponse.json({ ok: false, error: "BAD_SESSION" }, { status: 400 });
    }

    const body = BodySchema.parse(await req.json());
    const jobIds = Array.from(new Set(body.sourceJobIds.map((s) => s.trim()).filter(Boolean)));
    if (!jobIds.length) return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status: 400 });

    const facts: Fact[] = [];
    const warnings: string[] = [];
    const fileIds: string[] = [];

    const s3 = getS3Client();

    for (const jobId of jobIds) {
      const job = await getJob(ws.teamId, jobId);
      if (!job) {
        warnings.push(`잡을 찾지 못했습니다: ${jobId}`);
        continue;
      }
      if (job.type !== "pdf_evidence") {
        warnings.push(`pdf_evidence 잡이 아닙니다: ${jobId} (${job.type})`);
        continue;
      }
      if (job.status !== "succeeded") {
        warnings.push(`아직 완료되지 않은 잡입니다: ${jobId} (${job.status})`);
        continue;
      }
      const fileId = (job.inputFileIds || [])[0];
      if (fileId) fileIds.push(fileId);

      const artifact =
        (job.artifacts || []).find((a) => a.artifactId === "pdf_evidence_json") ??
        (job.artifacts || []).find((a) => (a.contentType || "").includes("json")) ??
        null;
      if (!artifact) {
        warnings.push(`아티팩트를 찾지 못했습니다: ${jobId}`);
        continue;
      }

      const objResp = await s3.send(new GetObjectCommand({ Bucket: artifact.s3Bucket, Key: artifact.s3Key }));
      const text = await readBodyToString(objResp.Body as any);
      let parsed: unknown = null;
      try {
        parsed = JSON.parse(text);
      } catch {
        warnings.push(`아티팩트 JSON 파싱 실패: ${jobId}/${artifact.artifactId}`);
        continue;
      }

      const evidence = coerceEvidenceArray(parsed);
      const packWarnings = (parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>)["warnings"] : undefined) as unknown;
      if (Array.isArray(packWarnings)) {
        for (const w of packWarnings) {
          if (typeof w === "string" && w.trim()) warnings.push(w.trim());
        }
      }

      evidence.slice(0, 80).forEach((e, idx) => {
        const page = typeof e["page"] === "number" ? (e["page"] as number) : Number(e["page"]);
        const pageNum = Number.isFinite(page) && page > 0 ? page : undefined;
        const lineText = typeof e["text"] === "string" ? e["text"] : "";
        const trimmed = trimText(lineText, 500);

        const baseSource = {
          kind: "pdf_evidence_line" as const,
          jobId,
          ...(fileId ? { fileId } : {}),
          page: pageNum ?? 0,
          text: trimmed,
        };

        facts.push({
          factId: crypto.randomUUID(),
          key: `evidence_text_p${pageNum ?? 0}_${idx + 1}`,
          valueType: "string",
          stringValue: trimmed,
          source: baseSource,
          confidence: "medium",
        });

        const numbers = Array.isArray(e["numbers"]) ? (e["numbers"] as unknown[]) : [];
        numbers.slice(0, 6).forEach((n, j) => {
          const raw = typeof n === "string" ? n : String(n);
          const unit = inferUnit(raw);
          const num = parseFirstNumber(raw);
          if (typeof num === "number") {
            facts.push({
              factId: crypto.randomUUID(),
              key: `evidence_num_p${pageNum ?? 0}_${idx + 1}_n${j + 1}`,
              valueType: "number",
              numberValue: num,
              unit,
              source: baseSource,
              confidence: unit === "%" ? "high" : "medium",
            });
          } else {
            facts.push({
              factId: crypto.randomUUID(),
              key: `evidence_phrase_p${pageNum ?? 0}_${idx + 1}_n${j + 1}`,
              valueType: "string",
              stringValue: trimText(raw, 160),
              unit,
              source: baseSource,
              confidence: "low",
            });
          }
        });
      });
    }

    const now = new Date().toISOString();
    const pack: FactPack = {
      factPackId: crypto.randomUUID(),
      sessionId,
      createdAt: now,
      createdBy: ws.memberName,
      inputs: { jobIds, fileIds: Array.from(new Set(fileIds)) },
      facts: facts.slice(0, 300),
      warnings: Array.from(new Set(warnings)).slice(0, 40),
    };

    await saveFactPack({ teamId: ws.teamId, sessionId, pack });
    return NextResponse.json({ ok: true, factPackId: pack.factPackId, warnings: pack.warnings });
  } catch (err) {
    const unauthorized = err instanceof Error && err.message === "UNAUTHORIZED";
    const status = unauthorized ? 401 : 400;
    return NextResponse.json({ ok: false, error: unauthorized ? "UNAUTHORIZED" : "BAD_REQUEST" }, { status });
  }
}

