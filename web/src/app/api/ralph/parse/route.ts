import { NextResponse } from "next/server";

import { handleParseFormData, handleParseFromS3, runParser } from "./handler";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";
export const maxDuration = 60;

export async function POST(req: Request) {
  const contentType = req.headers.get("content-type") ?? "";

  // JSON body path: parse from S3 key (bypasses Vercel 4.5MB body limit)
  if (contentType.includes("application/json")) {
    try {
      const body = await req.json();
      const result = await handleParseFromS3(body, {
        requireWorkspace: requireWorkspaceFromCookies,
        runParser,
      });
      if (result.status >= 500 && result.body.error !== "UNAUTHORIZED") {
        console.error("[RALPH] parse route (s3) failed", { error: result.body.error });
      }
      return NextResponse.json(result.body, { status: result.status });
    } catch {
      return NextResponse.json({ ok: false, error: "REQUEST_BODY_INVALID" }, { status: 400 });
    }
  }

  // Legacy FormData path (kept for backward compatibility)
  let formData: FormData;
  try {
    formData = await req.formData();
  } catch {
    return NextResponse.json(
      { ok: false, error: "REQUEST_BODY_INVALID" },
      { status: 400 },
    );
  }

  const result = await handleParseFormData(formData, {
    requireWorkspace: requireWorkspaceFromCookies,
    runParser,
  });
  if (result.status >= 500 && result.body.error !== "UNAUTHORIZED") {
    console.error("[RALPH] parse route failed", {
      error: result.body.error,
    });
  }
  return NextResponse.json(result.body, { status: result.status });
}
