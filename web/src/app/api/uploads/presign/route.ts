import { PutObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { NextResponse } from "next/server";
import { z } from "zod";

import { getDdbDocClient } from "@/lib/aws/ddb";
import { getDdbTableName } from "@/lib/aws/env";
import { getS3Client } from "@/lib/aws/s3";
import { getS3BucketName } from "@/lib/aws/env";
import { putUploadFile } from "@/lib/jobStore";
import { validateFilename, validateMimeType } from "@/lib/validation";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB per file.
const PRESIGN_EXPIRY_SECONDS = Number(process.env.MERRY_PRESIGN_EXPIRY_SECONDS ?? 600); // 10 minutes

const BodySchema = z.object({
  filename: z.string().min(1).max(500),
  contentType: z.string().optional().default("application/octet-stream"),
  sizeBytes: z.number().int().positive().max(MAX_FILE_SIZE).optional(),
  /** Client-generated idempotency key to prevent duplicate uploads. */
  uploadSessionId: z.string().min(8).max(64).optional(),
});

function inferExt(filename: string): string {
  const name = filename.trim();
  const dot = name.lastIndexOf(".");
  if (dot === -1) return "";
  const ext = name.slice(dot).toLowerCase();
  return ext;
}

const ALLOWED_EXTS = new Set([".pdf", ".xlsx", ".xls", ".docx", ".png", ".jpg", ".jpeg", ".gif", ".webp"]);

function isAllowedExt(ext: string): boolean {
  return ALLOWED_EXTS.has(ext);
}

export async function POST(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = BodySchema.parse(await req.json());

    // Validate filename (path traversal, control chars, etc.).
    const fnCheck = validateFilename(body.filename);
    if (!fnCheck.ok) {
      return NextResponse.json({ ok: false, error: fnCheck.reason }, { status: 400 });
    }

    const ext = inferExt(body.filename);
    if (ext && !isAllowedExt(ext)) {
      return NextResponse.json({ ok: false, error: "UNSUPPORTED_FILE" }, { status: 400 });
    }

    // Validate MIME type matches extension.
    const mimeCheck = validateMimeType(body.contentType, body.filename);
    if (!mimeCheck.ok) {
      return NextResponse.json({ ok: false, error: mimeCheck.reason }, { status: 400 });
    }

    // Idempotency check: if uploadSessionId provided, reuse existing presign.
    if (body.uploadSessionId) {
      try {
        const ddb = getDdbDocClient();
        const existing = await ddb.send(
          new (await import("@aws-sdk/lib-dynamodb")).GetCommand({
            TableName: getDdbTableName(),
            Key: { pk: `TEAM#${ws.teamId}#UPLOAD_SESSION`, sk: `SID#${body.uploadSessionId}` },
          }),
        );
        if (existing.Item && typeof existing.Item.fileId === "string") {
          const cached = existing.Item;
          return NextResponse.json({
            ok: true,
            file: {
              fileId: cached.fileId,
              bucket: cached.s3Bucket,
              key: cached.s3Key,
              contentType: body.contentType,
              sizeBytes: body.sizeBytes,
              originalName: body.filename,
            },
            upload: { method: "PUT", url: cached.presignUrl, headers: { "content-type": body.contentType } },
            deduplicated: true,
          });
        }
      } catch {
        // Dedup lookup failed — proceed with normal flow.
      }
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
      { expiresIn: PRESIGN_EXPIRY_SECONDS },
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

    // Store idempotency mapping (TTL 1 hour).
    // Use ConditionExpression to prevent race condition between concurrent requests
    // with the same uploadSessionId — only the first writer wins.
    if (body.uploadSessionId) {
      try {
        const ddb = getDdbDocClient();
        await ddb.send(
          new (await import("@aws-sdk/lib-dynamodb")).PutCommand({
            TableName: getDdbTableName(),
            Item: {
              pk: `TEAM#${ws.teamId}#UPLOAD_SESSION`,
              sk: `SID#${body.uploadSessionId}`,
              entity: "upload_session",
              fileId,
              s3Bucket: bucket,
              s3Key: key,
              presignUrl: url,
              ttl: Math.floor(Date.now() / 1000) + 3600, // 1 hour
            },
            ConditionExpression: "attribute_not_exists(pk)",
          }),
        );
      } catch {
        // Best-effort: dedup store failed or condition check failed (duplicate), upload still works.
      }
    }

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

