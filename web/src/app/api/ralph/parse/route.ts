import { NextResponse } from "next/server";

import { handleParseFormData, runParser } from "./handler";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";
export const maxDuration = 60;

export async function POST(req: Request) {
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
