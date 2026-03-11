import { NextResponse } from "next/server";

/**
 * Add Cache-Control headers to a NextResponse.
 *
 * @param res - The NextResponse to augment.
 * @param maxAge - max-age in seconds (browser + CDN).
 * @param staleWhileRevalidate - stale-while-revalidate window in seconds.
 * @param isPrivate - Whether the response is private (user-specific). Default true.
 */
export function withCache(
  res: NextResponse,
  maxAge: number,
  staleWhileRevalidate = 0,
  isPrivate = true,
): NextResponse {
  const parts: string[] = [];
  if (isPrivate) parts.push("private");
  parts.push(`max-age=${maxAge}`);
  if (staleWhileRevalidate > 0) {
    parts.push(`stale-while-revalidate=${staleWhileRevalidate}`);
  }
  res.headers.set("Cache-Control", parts.join(", "));
  return res;
}

/** Shorthand for no-cache responses. */
export function withNoCache(res: NextResponse): NextResponse {
  res.headers.set("Cache-Control", "private, no-cache, no-store, must-revalidate");
  return res;
}
