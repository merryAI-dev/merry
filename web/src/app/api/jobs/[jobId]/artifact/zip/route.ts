import { GetObjectCommand, PutObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { NextResponse } from "next/server";
import type { Readable } from "stream";
import archiver from "archiver";

import { getS3Client } from "@/lib/aws/s3";
import { getS3BucketName } from "@/lib/aws/env";
import { getJob } from "@/lib/jobStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

/** Stream all job artifacts into a ZIP and return a presigned download URL. */
export async function GET(
  _req: Request,
  ctx: { params: Promise<{ jobId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { jobId } = await ctx.params;

    const job = await getJob(ws.teamId, jobId);
    if (!job) return NextResponse.json({ ok: false, error: "NOT_FOUND" }, { status: 404 });

    const artifacts = job.artifacts ?? [];
    if (artifacts.length === 0) {
      return NextResponse.json({ ok: false, error: "NO_ARTIFACTS" }, { status: 404 });
    }

    const s3 = getS3Client();
    const bucket = getS3BucketName();

    // Build ZIP in memory (artifacts are typically small CSV/JSON files).
    const zip = archiver("zip", { zlib: { level: 6 } });
    const chunks: Buffer[] = [];

    await new Promise<void>((resolve, reject) => {
      zip.on("data", (chunk: Buffer) => chunks.push(chunk));
      zip.on("end", () => resolve());
      zip.on("error", (err: Error) => reject(err));

      (async () => {
        for (const a of artifacts) {
          try {
            const resp = await s3.send(
              new GetObjectCommand({ Bucket: a.s3Bucket || bucket, Key: a.s3Key }),
            );
            if (resp.Body) {
              const ext = a.contentType === "text/csv" ? ".csv" : ".json";
              const filename = `${a.artifactId}${ext}`;
              zip.append(resp.Body as Readable, { name: filename });
            }
          } catch {
            // Skip missing artifacts.
          }
        }
        zip.finalize();
      })().catch(reject);
    });

    const zipBuffer = Buffer.concat(chunks);
    const zipKey = `artifacts/${ws.teamId}/${jobId}/_bundle.zip`;

    // Upload ZIP to S3.
    await s3.send(
      new PutObjectCommand({
        Bucket: bucket,
        Key: zipKey,
        Body: zipBuffer,
        ContentType: "application/zip",
      }),
    );

    // Generate presigned download URL.
    const url = await getSignedUrl(
      s3,
      new GetObjectCommand({
        Bucket: bucket,
        Key: zipKey,
        ResponseContentType: "application/zip",
        ResponseContentDisposition: `attachment; filename="${jobId}_results.zip"`,
      }),
      { expiresIn: 60 * 10 },
    );

    return NextResponse.json({ ok: true, url });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}
