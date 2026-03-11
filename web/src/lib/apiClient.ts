/**
 * Shared client-side API fetch wrapper.
 *
 * - Auto-generates a correlation ID for each request.
 * - Propagates x-correlation-id header to the backend.
 * - Captures x-request-id from response for debugging.
 * - Logs errors with context (URL, correlation ID, request ID).
 */

let _counter = 0;

/** Generate a short correlation ID: timestamp(base36) + counter. */
function generateCorrelationId(): string {
  _counter = (_counter + 1) % 10000;
  return `${Date.now().toString(36)}-${_counter.toString(36)}`;
}

export class ApiError extends Error {
  readonly status: number;
  readonly correlationId: string;
  readonly requestId: string;

  constructor(
    message: string,
    status: number,
    correlationId: string,
    requestId: string,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.correlationId = correlationId;
    this.requestId = requestId;
  }
}

/**
 * Typed fetch wrapper with automatic correlation ID propagation.
 *
 * @example
 * const data = await apiFetch<{ ok: true; jobs: Job[] }>("/api/jobs?limit=10");
 * const data = await apiFetch<{ ok: true }>("/api/jobs/abc/retry", { method: "POST", body: ... });
 */
export async function apiFetch<T = unknown>(
  url: string,
  init?: RequestInit,
): Promise<T> {
  const correlationId = generateCorrelationId();

  const headers = new Headers(init?.headers);
  headers.set("x-correlation-id", correlationId);
  if (!headers.has("content-type") && init?.body && typeof init.body === "string") {
    headers.set("content-type", "application/json");
  }

  const res = await fetch(url, { cache: "no-store", ...init, headers });

  const requestId = res.headers.get("x-request-id") ?? "";

  const json = await res.json().catch(() => ({} as Record<string, unknown>));

  if (!res.ok) {
    const errMsg = (json as Record<string, unknown>)?.error as string || `HTTP ${res.status}`;
    console.error(
      `[API Error] ${init?.method ?? "GET"} ${url} → ${res.status} | cid=${correlationId} rid=${requestId} | ${errMsg}`,
    );
    throw new ApiError(errMsg, res.status, correlationId, requestId);
  }

  return json as T;
}
