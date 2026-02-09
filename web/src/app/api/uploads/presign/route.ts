import { PutObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { NextResponse } from "next/server";
import { z } from "zod";

import { getS3Client } from "@/lib/aws/s3";
import { getS3BucketName } from "@/lib/aws/env";
import { putUploadFile } from "@/lib/jobStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const BodySchema = z.object({
  filename: z.string().min(1),
  contentType: z.string().optional().default("application/octet-stream"),
  sizeBytes: z.number().int().positive().max(1024 * 1024 * 1024).optional(), // 1GB guardrail
});

function inferExt(filename: string): string {
  const name = filename.trim();
  const dot = name.lastIndexOf(".");
  if (dot === -1) return "";
  const ext = name.slice(dot).toLowerCase();
  return ext;
}

function isAllowedExt(ext: string): boolean {
  return ext === ".pdf" || ext === ".xlsx" || ext === ".xls" || ext === ".docx";
}

export async function POST(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = BodySchema.parse(await req.json());

    const ext = inferExt(body.filename);
    if (ext && !isAllowedExt(ext)) {
      return NextResponse.json({ ok: false, error: "UNSUPPORTED_FILE" }, { status: 400 });
    }

    const fileId = crypto.randomUUID().replaceAll("-", "").slice(0, 16);
    const bucket = getS3BucketName();
    const key = `uploads/${ws.teamId}/${fileId}${ext || ""}`;
    const createdAt = new Date().toISOString();

    const s3 = getS3Client();
    const url = await getSignedUrl(
      s3,
      new PutObjectCommand({
        Bucket: bucket,
        Key: key,
        ContentType: body.contentType,
      }),
      { expiresIn: 60 * 10 },
    );

    await putUploadFile({
      fileId,
      teamId: ws.teamId,
      status: "presigned",
      originalName: body.filename,
      contentType: body.contentType,
      sizeBytes: body.sizeBytes,
      s3Bucket: bucket,
      s3Key: key,
      createdBy: ws.memberName,
      createdAt,
    });

    return NextResponse.json({
      ok: true,
      file: { fileId, bucket, key, contentType: body.contentType, sizeBytes: body.sizeBytes, originalName: body.filename },
      upload: { method: "PUT", url, headers: { "content-type": body.contentType } },
    });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}

