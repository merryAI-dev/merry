import { NextResponse } from "next/server";
import { z } from "zod";
import * as XLSX from "xlsx";

import { runParserS3 } from "@/app/api/ralph/parse/handler";
import { addFileContext } from "@/lib/reportChat";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";
import { getS3Client } from "@/lib/aws/s3";
import { GetObjectCommand } from "@aws-sdk/client-s3";

export const runtime = "nodejs";
export const maxDuration = 120;

const BodySchema = z.object({
  sessionId: z.string().min(1).max(128),
  fileId: z.string().min(1).max(64),
  s3Key: z.string().min(1).max(512),
  s3Bucket: z.string().min(1).max(256),
  originalName: z.string().min(1).max(500),
});

const EXCEL_EXTS = new Set([".xlsx", ".xls"]);
const TEXT_EXTS = new Set([".txt", ".md", ".csv", ".json", ".tsv", ".log", ".xml", ".html", ".htm", ".yaml", ".yml"]);

function getExt(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot).toLowerCase() : "";
}

/** Read a plain text file from S3. */
async function readTextFromS3(s3Key: string, s3Bucket: string): Promise<string> {
  const s3 = getS3Client();
  const res = await s3.send(new GetObjectCommand({ Bucket: s3Bucket, Key: s3Key }));
  const body = res.Body;
  if (!body) throw new Error("S3_EMPTY_BODY");
  const chunks: Uint8Array[] = [];
  for await (const chunk of body as AsyncIterable<Uint8Array>) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf-8");
}

/** Parse an Excel file from S3 into a text representation. */
async function parseExcelFromS3(s3Key: string, s3Bucket: string): Promise<string> {
  const s3 = getS3Client();
  const res = await s3.send(new GetObjectCommand({ Bucket: s3Bucket, Key: s3Key }));
  const body = res.Body;
  if (!body) throw new Error("S3_EMPTY_BODY");

  const chunks: Uint8Array[] = [];
  // @ts-expect-error -- Body is a Readable stream in Node
  for await (const chunk of body) {
    chunks.push(chunk as Uint8Array);
  }
  const buffer = Buffer.concat(chunks);

  const workbook = XLSX.read(buffer, { type: "buffer" });
  const parts: string[] = [];

  for (const sheetName of workbook.SheetNames) {
    const sheet = workbook.Sheets[sheetName];
    if (!sheet) continue;

    // Convert to CSV for readable text representation
    const csv = XLSX.utils.sheet_to_csv(sheet, { blankrows: false });
    if (!csv.trim()) continue;

    parts.push(`[시트: ${sheetName}]\n${csv}`);
  }

  return parts.join("\n\n");
}

function extractTextFromParserResult(result: Record<string, unknown>): string {
  // The parser returns different shapes depending on mode.
  // Try structured content first, then fall back to content string.

  // 1. Structured content (pages array)
  const structured = result.structured_content;
  if (structured && typeof structured === "object") {
    const sc = structured as Record<string, unknown>;
    const pages = sc.pages;
    if (Array.isArray(pages)) {
      const parts: string[] = [];
      for (const page of pages) {
        if (!page || typeof page !== "object") continue;
        const p = page as Record<string, unknown>;
        const pageNum = typeof p.page_num === "number" ? p.page_num : "";
        const elements = Array.isArray(p.elements) ? p.elements : [];
        const texts: string[] = [];
        for (const el of elements) {
          if (!el || typeof el !== "object") continue;
          const e = el as Record<string, unknown>;
          const content = typeof e.content === "string" ? e.content : "";
          if (content) texts.push(content);
        }
        if (texts.length) {
          parts.push(`[페이지 ${pageNum}]\n${texts.join("\n")}`);
        }
      }
      if (parts.length) return parts.join("\n\n");
    }
  }

  // 2. Plain content string
  if (typeof result.content === "string" && result.content.trim()) {
    return result.content;
  }

  // 3. text field
  if (typeof result.text === "string" && result.text.trim()) {
    return result.text;
  }

  // 4. markdown field
  if (typeof result.markdown === "string" && result.markdown.trim()) {
    return result.markdown;
  }

  return "";
}

export async function POST(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = BodySchema.parse(await req.json());

    if (!body.sessionId.startsWith("report_")) {
      return NextResponse.json({ ok: false, error: "BAD_SESSION" }, { status: 400 });
    }

    const ext = getExt(body.originalName);
    const isExcel = EXCEL_EXTS.has(ext);
    const isText = TEXT_EXTS.has(ext);

    let extractedText = "";
    let warnings: string[] = [];

    if (isText) {
      // Plain text files: read directly from S3
      try {
        extractedText = await readTextFromS3(body.s3Key, body.s3Bucket);
        if (!extractedText.trim()) {
          warnings.push("파일이 비어 있습니다.");
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "TEXT_READ_FAILED";
        console.error("[CHAT_UPLOAD] text read failed:", msg);

        await addFileContext({
          teamId: ws.teamId,
          sessionId: body.sessionId,
          fileId: body.fileId,
          originalName: body.originalName,
          extractedText: "",
          memberName: ws.memberName,
          warnings: [`텍스트 읽기 실패: ${msg}`],
        });

        return NextResponse.json({ ok: false, error: "PARSE_FAILED", detail: msg }, { status: 502 });
      }
    } else if (isExcel) {
      // Excel: parse directly with xlsx library (Lambda doesn't support Excel)
      try {
        extractedText = await parseExcelFromS3(body.s3Key, body.s3Bucket);
        if (!extractedText) {
          warnings.push("엑셀에서 텍스트를 추출하지 못했습니다.");
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "EXCEL_PARSE_FAILED";
        console.error("[CHAT_UPLOAD] excel parse failed:", msg);

        await addFileContext({
          teamId: ws.teamId,
          sessionId: body.sessionId,
          fileId: body.fileId,
          originalName: body.originalName,
          extractedText: "",
          memberName: ws.memberName,
          warnings: [`엑셀 파싱 실패: ${msg}`],
        });

        return NextResponse.json({ ok: false, error: "PARSE_FAILED", detail: msg }, { status: 502 });
      }
    } else {
      // PDF, DOCX, images: parse via Lambda
      try {
        const parserResult = await runParserS3(body.s3Key, body.s3Bucket);
        extractedText = extractTextFromParserResult(parserResult);
        if (!extractedText) {
          warnings.push("문서에서 텍스트를 추출하지 못했습니다.");
        }

        if (Array.isArray(parserResult.warnings)) {
          for (const w of parserResult.warnings) {
            if (typeof w === "string") warnings.push(w);
          }
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "PARSE_FAILED";
        console.error("[CHAT_UPLOAD] parse failed:", msg);

        await addFileContext({
          teamId: ws.teamId,
          sessionId: body.sessionId,
          fileId: body.fileId,
          originalName: body.originalName,
          extractedText: "",
          memberName: ws.memberName,
          warnings: [`파싱 실패: ${msg}`],
        });

        return NextResponse.json({
          ok: false,
          error: "PARSE_FAILED",
          detail: msg,
        }, { status: 502 });
      }
    }

    await addFileContext({
      teamId: ws.teamId,
      sessionId: body.sessionId,
      fileId: body.fileId,
      originalName: body.originalName,
      extractedText,
      memberName: ws.memberName,
      warnings,
    });

    return NextResponse.json({
      ok: true,
      fileId: body.fileId,
      charCount: extractedText.length,
      truncated: extractedText.length > 80_000,
      warnings: warnings.length ? warnings : undefined,
    });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}
