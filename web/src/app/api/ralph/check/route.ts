import { NextResponse } from "next/server";

import { handleCheckFormData, runChecker } from "./handler";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";
export const maxDuration = 60;

export async function POST(req: Request) {
  const result = await handleCheckFormData(await req.formData(), {
    requireWorkspace: requireWorkspaceFromCookies,
    runChecker,
  });
  if (result.status >= 500 && result.body.error !== "UNAUTHORIZED") {
    console.error("[RALPH] check route failed", {
      error: result.body.error,
    });
  }
  return NextResponse.json(result.body, { status: result.status });
}
