import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

/**
 * Prevents "it works on one Vercel URL but not another" issues.
 *
 * - Auth cookies are host-scoped, so using multiple deployment URLs causes
 *   random logout/redirect behavior for the team.
 * - Enforcing a canonical host (in production) removes that source of flakiness.
 *
 * Enable by setting `CANONICAL_HOST=mysc-merry-inv.vercel.app` (production env).
 */
export function proxy(req: NextRequest) {
  const canonicalHost = process.env.CANONICAL_HOST?.trim();
  if (!canonicalHost) return NextResponse.next();

  const host = req.headers.get("host") ?? "";
  if (!host || host === canonicalHost) return NextResponse.next();

  const url = req.nextUrl.clone();
  url.host = canonicalHost;
  url.protocol = "https:";
  return NextResponse.redirect(url, 308);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};

