import { GetObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { NextResponse } from "next/server";

import { getS3Client } from "@/lib/aws/s3";
import { getDiagnosisArtifact } from "@/lib/diagnosisSessionStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

export async function GET(
  _req: Request,
  ctx: { params: Promise<{ sessionId: string; artifactId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { sessionId, artifactId } = await ctx.params;
    const artifact = await getDiagnosisArtifact(ws.teamId, sessionId, artifactId);
    if (!artifact) {
      return NextResponse.json({ ok: false, error: "NOT_FOUND" }, { status: 404 });
    }

    const s3 = getS3Client();
    const url = await getSignedUrl(
      s3,
      new GetObjectCommand({
        Bucket: artifact.s3Bucket,
        Key: artifact.s3Key,
        ResponseContentType: artifact.contentType,
      }),
      { expiresIn: 5 * 60 },
    );

    return NextResponse.json({ ok: true, url });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}
