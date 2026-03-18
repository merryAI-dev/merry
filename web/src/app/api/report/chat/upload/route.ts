import { NextResponse } from "next/server";
import { z } from "zod";

import { runParserS3 } from "@/app/api/ralph/parse/handler";
import { addFileContext } from "@/lib/reportChat";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";
export const maxDuration = 120;

const BodySchema = z.object({
  sessionId: z.string().min(1).max(128),
  fileId: z.string().min(1).max(64),
  s3Key: z.string().min(1).max(512),
  s3Bucket: z.string().min(1).max(256),
  originalName: z.string().min(1).max(500),
});

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

    // Parse file via Lambda (reuse existing pipeline)
    let parserResult: Record<string, unknown>;
    let warnings: string[] = [];
    try {
      parserResult = await runParserS3(body.s3Key, body.s3Bucket);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "PARSE_FAILED";
      console.error("[CHAT_UPLOAD] parse failed:", msg);

      // Store an empty file context with warning so user knows it failed
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

    const extractedText = extractTextFromParserResult(parserResult);
    if (!extractedText) {
      warnings.push("문서에서 텍스트를 추출하지 못했습니다.");
    }

    // Check parser warnings
    if (Array.isArray(parserResult.warnings)) {
      for (const w of parserResult.warnings) {
        if (typeof w === "string") warnings.push(w);
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
