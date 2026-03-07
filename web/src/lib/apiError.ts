import { NextResponse } from "next/server";

/**
 * Standard API error handler for route catch blocks.
 * Logs structured error context and returns a consistent JSON response.
 */
export function handleApiError(err: unknown, operation: string) {
  const msg = err instanceof Error ? err.message : String(err);
  const isUnauthorized = msg === "UNAUTHORIZED" || msg.startsWith("UNAUTHORIZED:");
  const status = isUnauthorized ? 401 : 500;

  if (!isUnauthorized) {
    console.error(`[API] ${operation}`, {
      error: msg,
      name: err instanceof Error ? err.name : undefined,
    });
  }

  const errorCode = isUnauthorized ? msg : "FAILED";
  return NextResponse.json({ ok: false, error: errorCode }, { status });
}
