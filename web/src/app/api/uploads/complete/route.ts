import { HeadObjectCommand } from "@aws-sdk/client-s3";
import { NextResponse } from "next/server";
import { z } from "zod";

import { getS3Client } from "@/lib/aws/s3";
import { getUploadFile, markUploadFileUploaded } from "@/lib/jobStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const BodySchema = z.object({
  fileId: z.string().min(6),
});

export async function POST(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = BodySchema.parse(await req.json());

    const file = await getUploadFile(ws.teamId, body.fileId);
    if (!file) {
      return NextResponse.json({ ok: false, error: "NOT_FOUND" }, { status: 404 });
    }

    // Lightweight server-side validation: confirm the object exists.
    const s3 = getS3Client();
    const head = await s3.send(new HeadObjectCommand({ Bucket: file.s3Bucket, Key: file.s3Key }));

    const uploadedAt = new Date().toISOString();
    const etag = typeof head.ETag === "string" ? head.ETag : undefined;
    const sizeBytes = typeof head.ContentLength === "number" ? head.ContentLength : undefined;

    await markUploadFileUploaded({
      teamId: ws.teamId,
      fileId: file.fileId,
      uploadedAt,
      etag,
      sizeBytes,
    });

    return NextResponse.json({ ok: true, uploadedAt, etag, sizeBytes });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}

