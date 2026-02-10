import { GetObjectCommand } from "@aws-sdk/client-s3";
import { NextResponse } from "next/server";
import { z } from "zod";

import { getS3Client } from "@/lib/aws/s3";
import { addDraftVersion, findDraftVersionBySource, getDraftDetail } from "@/lib/drafts";
import { getJob } from "@/lib/jobStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const BodySchema = z.object({
  jobId: z.string().min(6),
  artifactId: z.string().min(1).optional(),
  baseVersionId: z.string().optional(),
  maxItems: z.number().int().min(1).max(50).optional(),
});

function sanitizeLine(s: string): string {
  return (s || "").replace(/\s+/g, " ").trim();
}

function evidenceToMarkdown(evidence: unknown, maxItems: number): string {
  const items = Array.isArray(evidence) ? evidence : [];
  const lines: string[] = [];
  for (const raw of items.slice(0, Math.max(1, Math.min(maxItems, 50)))) {
    const row = (raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {}) as Record<string, unknown>;
    const page = typeof row["page"] === "number" ? row["page"] : undefined;
    const text = typeof row["text"] === "string" ? sanitizeLine(row["text"]) : "";
    if (!text) continue;
    const prefix = page ? `(p.${page}) ` : "";
    lines.push(`- ${prefix}${text}`);
  }
  if (!lines.length) return "- (추출된 근거가 없습니다)\n";
  return lines.join("\n") + "\n";
}

function insertEvidenceBlock(markdown: string, block: string): string {
  const src = markdown ?? "";
  const evidenceBlock = `\n### 자동 근거 (PDF)\n${block}`;

  // Try to insert under the market/competition section.
  const lines = src.split(/\r?\n/);
  const idx = lines.findIndex((l) => /^##\s+/.test(l) && /시장|경쟁/.test(l));
  if (idx >= 0) {
    // Insert after the heading and a single blank line (if present).
    let insertAt = idx + 1;
    if (lines[insertAt] === "") insertAt += 1;
    const next = [...lines.slice(0, insertAt), evidenceBlock.trimEnd(), "", ...lines.slice(insertAt)];
    return next.join("\n").replace(/\n{3,}/g, "\n\n");
  }

  // Fallback: append at end.
  const trimmed = src.trimEnd();
  const sep = trimmed ? "\n\n" : "";
  return `${trimmed}${sep}## 참고 근거\n${evidenceBlock.trimEnd()}\n`;
}

async function bodyToString(body: unknown): Promise<string> {
  if (!body) return "";
  if (typeof body === "string") return body;
  if (body instanceof Uint8Array) return new TextDecoder().decode(body);
  if (typeof (body as any).transformToString === "function") {
    return (body as any).transformToString();
  }
  const chunks: Buffer[] = [];
  for await (const chunk of body as any) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return Buffer.concat(chunks).toString("utf-8");
}

export async function POST(req: Request, ctx: { params: Promise<{ draftId: string }> }) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { draftId } = await ctx.params;
    const body = BodySchema.parse(await req.json());

    const job = await getJob(ws.teamId, body.jobId);
    if (!job) return NextResponse.json({ ok: false, error: "JOB_NOT_FOUND" }, { status: 404 });
    if (job.status !== "succeeded") {
      return NextResponse.json({ ok: false, error: "JOB_NOT_READY" }, { status: 400 });
    }

    const artifacts = job.artifacts ?? [];
    const wantedId = (body.artifactId ?? "").trim();
    const artifact =
      (wantedId ? artifacts.find((a) => a.artifactId === wantedId) : null) ??
      artifacts.find((a) => a.artifactId === "pdf_evidence_json") ??
      artifacts.find((a) => (a.label || "").includes("근거") && (a.contentType || "").includes("json")) ??
      null;
    if (!artifact) return NextResponse.json({ ok: false, error: "ARTIFACT_NOT_FOUND" }, { status: 404 });

    const existing = await findDraftVersionBySource({
      teamId: ws.teamId,
      draftId,
      source: { kind: "pdf_evidence", jobId: job.jobId, artifactId: artifact.artifactId },
    });
    if (existing) {
      return NextResponse.json({ ok: true, versionId: existing.versionId, alreadyImported: true });
    }

    const detail = await getDraftDetail(ws.teamId, draftId);
    const versions = detail.versions;
    if (!versions.length) {
      return NextResponse.json({ ok: false, error: "NO_VERSION" }, { status: 400 });
    }
    const baseVersionId = (body.baseVersionId ?? "").trim();
    const base =
      (baseVersionId ? versions.find((v) => v.versionId === baseVersionId) : null) ??
      versions[versions.length - 1];

    const s3 = getS3Client();
    const obj = await s3.send(new GetObjectCommand({ Bucket: artifact.s3Bucket, Key: artifact.s3Key }));
    const raw = await bodyToString(obj.Body as unknown);
    const json = JSON.parse(raw || "{}") as Record<string, unknown>;
    const evidence = (json && typeof json === "object" ? (json as any).evidence : null) as unknown;

    const maxItems = typeof body.maxItems === "number" ? body.maxItems : 20;
    const block = evidenceToMarkdown(evidence, maxItems);
    const updated = insertEvidenceBlock(base.content || "", block);

    const title = `${base.title} · 근거추출`;
    const created = await addDraftVersion({
      teamId: ws.teamId,
      draftId,
      createdBy: ws.memberName,
      title,
      content: updated,
      source: { kind: "pdf_evidence", jobId: job.jobId, artifactId: artifact.artifactId },
    });

    return NextResponse.json({ ok: true, versionId: created.versionId, evidenceCount: Array.isArray(evidence) ? evidence.length : 0 });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}

