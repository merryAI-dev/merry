import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/** Allowed origins for API CORS. Defaults to same-origin only. */
const ALLOWED_ORIGINS = new Set(
  (process.env.MERRY_CORS_ORIGINS ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean),
);

function isOriginAllowed(origin: string | null): boolean {
  if (!origin) return true; // same-origin requests
  return ALLOWED_ORIGINS.has(origin) || ALLOWED_ORIGINS.has("*");
}

/* ─── Sliding Window Rate Limiter (in-memory) ─── */

const RATE_LIMIT_WINDOW_MS = Number(process.env.MERRY_RATE_LIMIT_WINDOW_MS ?? 60_000);
const RATE_LIMIT_MAX = Number(process.env.MERRY_RATE_LIMIT_MAX ?? 60);
/** Paths exempt from rate limiting (health checks, auth). */
const RATE_LIMIT_EXEMPT = new Set(["/api/health", "/api/auth/workspace"]);

type RateBucket = { timestamps: number[]; lastCleanup: number };
const rateBuckets = new Map<string, RateBucket>();

/** Periodic cleanup: remove stale entries every 5 minutes to prevent memory growth. */
let lastGlobalCleanup = Date.now();
const GLOBAL_CLEANUP_INTERVAL_MS = 300_000;

function cleanupBuckets(now: number) {
  if (now - lastGlobalCleanup < GLOBAL_CLEANUP_INTERVAL_MS) return;
  lastGlobalCleanup = now;
  const cutoff = now - RATE_LIMIT_WINDOW_MS * 2;
  for (const [key, bucket] of rateBuckets) {
    if (bucket.lastCleanup < cutoff) {
      rateBuckets.delete(key);
    }
  }
}

function checkRateLimit(key: string): { allowed: boolean; remaining: number; resetMs: number } {
  const now = Date.now();
  cleanupBuckets(now);

  let bucket = rateBuckets.get(key);
  if (!bucket) {
    bucket = { timestamps: [], lastCleanup: now };
    rateBuckets.set(key, bucket);
  }

  // Slide window: remove timestamps older than window.
  const windowStart = now - RATE_LIMIT_WINDOW_MS;
  bucket.timestamps = bucket.timestamps.filter((ts) => ts > windowStart);
  bucket.lastCleanup = now;

  if (bucket.timestamps.length >= RATE_LIMIT_MAX) {
    const oldest = bucket.timestamps[0] ?? now;
    const resetMs = oldest + RATE_LIMIT_WINDOW_MS - now;
    return { allowed: false, remaining: 0, resetMs: Math.max(resetMs, 0) };
  }

  bucket.timestamps.push(now);
  return {
    allowed: true,
    remaining: RATE_LIMIT_MAX - bucket.timestamps.length,
    resetMs: RATE_LIMIT_WINDOW_MS,
  };
}

function getRateLimitKey(request: NextRequest): string {
  // Use X-Forwarded-For (behind load balancer) or fallback to generic key.
  const forwarded = request.headers.get("x-forwarded-for");
  const ip = forwarded?.split(",")[0]?.trim() || "unknown";
  return `ip:${ip}`;
}

/* ─── Proxy (Next.js 16+) ─── */

export function proxy(request: NextRequest) {
  // ── Canonical host redirect (production) ──
  const canonicalHost = process.env.CANONICAL_HOST?.trim();
  if (canonicalHost) {
    const host = request.headers.get("host") ?? "";
    if (host && host !== canonicalHost) {
      const url = request.nextUrl.clone();
      url.host = canonicalHost;
      url.protocol = "https:";
      return NextResponse.redirect(url, 308);
    }
  }

  const { pathname } = request.nextUrl;

  // ── API CORS + Request ID + Rate Limiting + Timing ──
  if (pathname.startsWith("/api/")) {
    const origin = request.headers.get("origin");
    const requestId =
      request.headers.get("x-request-id") ?? crypto.randomUUID().replaceAll("-", "").slice(0, 16);
    const correlationId = request.headers.get("x-correlation-id") ?? "";
    const requestStartMs = Date.now();

    // Block cross-origin requests from disallowed origins.
    if (origin && !isOriginAllowed(origin)) {
      const res = NextResponse.json({ ok: false, error: "CORS_DENIED" }, { status: 403 });
      res.headers.set("x-request-id", requestId);
      if (correlationId) res.headers.set("x-correlation-id", correlationId);
      return res;
    }

    // Handle preflight.
    if (request.method === "OPTIONS") {
      const res = new NextResponse(null, { status: 204 });
      if (origin && isOriginAllowed(origin)) {
        res.headers.set("Access-Control-Allow-Origin", origin);
        res.headers.set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
        res.headers.set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-Id, X-Correlation-Id");
        res.headers.set("Access-Control-Max-Age", "86400");
      }
      return res;
    }

    // Mutation requests: ensure no caching by browsers or intermediaries.
    const isMutation = request.method !== "GET" && request.method !== "HEAD" && request.method !== "OPTIONS";

    // Rate limiting (skip exempt paths).
    if (RATE_LIMIT_MAX > 0 && !RATE_LIMIT_EXEMPT.has(pathname)) {
      const key = getRateLimitKey(request);
      const { allowed, remaining, resetMs } = checkRateLimit(key);

      if (!allowed) {
        const res = NextResponse.json(
          { ok: false, error: "RATE_LIMITED" },
          { status: 429 },
        );
        res.headers.set("Retry-After", String(Math.ceil(resetMs / 1000)));
        res.headers.set("X-RateLimit-Limit", String(RATE_LIMIT_MAX));
        res.headers.set("X-RateLimit-Remaining", "0");
        res.headers.set("x-request-id", requestId);
        if (correlationId) res.headers.set("x-correlation-id", correlationId);
        return res;
      }

      // Add CORS + tracing + rate limit headers to response.
      const response = NextResponse.next();
      response.headers.set("x-request-id", requestId);
      response.headers.set("x-request-start", String(requestStartMs));
      if (correlationId) response.headers.set("x-correlation-id", correlationId);
      response.headers.set("X-RateLimit-Limit", String(RATE_LIMIT_MAX));
      response.headers.set("X-RateLimit-Remaining", String(remaining));
      if (isMutation) response.headers.set("Cache-Control", "no-store");
      if (origin && isOriginAllowed(origin)) {
        response.headers.set("Access-Control-Allow-Origin", origin);
        response.headers.set("Access-Control-Expose-Headers", "x-request-id, x-correlation-id, x-request-start, X-RateLimit-Remaining");
      }
      return response;
    }

    // Non-rate-limited paths still get CORS + tracing headers.
    const response = NextResponse.next();
    response.headers.set("x-request-id", requestId);
    response.headers.set("x-request-start", String(requestStartMs));
    if (correlationId) response.headers.set("x-correlation-id", correlationId);
    if (isMutation) response.headers.set("Cache-Control", "no-store");
    if (origin && isOriginAllowed(origin)) {
      response.headers.set("Access-Control-Allow-Origin", origin);
      response.headers.set("Access-Control-Expose-Headers", "x-request-id, x-correlation-id, x-request-start");
    }
    return response;
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
