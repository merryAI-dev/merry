import { GetObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { NextResponse } from "next/server";

import { getS3Client } from "@/lib/aws/s3";
import { getJob } from "@/lib/jobStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

/** Presigned URL expiry based on artifact age. Older artifacts get longer URLs
 *  since users are more likely to share or download them in bulk. */
function presignExpiry(createdAt: string | undefined): number {
  if (!createdAt) return 5 * 60; // 5 min default
  const ageMs = Date.now() - new Date(createdAt).getTime();
  const ageDays = ageMs / (1000 * 60 * 60 * 24);
  if (ageDays > 30) return 60 * 60; // 1 hour for old artifacts (soon to be IA/expired)
  if (ageDays > 7) return 30 * 60; // 30 min for week-old artifacts
  return 5 * 60; // 5 min for recent artifacts
}

export async function GET(
  req: Request,
  ctx: { params: Promise<{ jobId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { jobId } = await ctx.params;
    const urlObj = new URL(req.url);
    const artifactId = urlObj.searchParams.get("artifactId") ?? "";
    if (!artifactId) return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status: 400 });

    const job = await getJob(ws.teamId, jobId);
    if (!job) return NextResponse.json({ ok: false, error: "NOT_FOUND" }, { status: 404 });

    const artifact = (job.artifacts ?? []).find((a) => a.artifactId === artifactId);
    if (!artifact) return NextResponse.json({ ok: false, error: "NOT_FOUND" }, { status: 404 });

    const expiresIn = presignExpiry(job.createdAt);
    const s3 = getS3Client();
    const url = await getSignedUrl(
      s3,
      new GetObjectCommand({
        Bucket: artifact.s3Bucket,
        Key: artifact.s3Key,
        ResponseContentType: artifact.contentType,
      }),
      { expiresIn },
    );

    return NextResponse.json({ ok: true, url, expiresIn });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}

