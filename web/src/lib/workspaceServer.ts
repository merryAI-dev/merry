import { cache } from "react";
import { cookies } from "next/headers";

import { WORKSPACE_COOKIE_NAME, verifyWorkspaceSession } from "@/lib/workspace";
import { auth, authAllowedDomain, authTeamId, googleAuthEnabled } from "@/auth";

/** Shape of session returned by next-auth with our custom fields. */
interface AuthSession {
  teamId?: string;
  memberName?: string;
  user?: { name?: string | null; email?: string | null; image?: string | null };
}

function memberNameFromSession(session: AuthSession | null): string {
  const raw = (session && session.memberName) || session?.user?.name || "";
  const name = typeof raw === "string" ? raw.trim() : "";
  if (name) return name;
  const email = typeof session?.user?.email === "string" ? session.user.email : "";
  if (email) return email.split("@")[0] || "member";
  return "member";
}

// React.cache() deduplicates calls within a single server-render pass.
// Without this, layout + page both calling getWorkspaceFromCookies() would
// trigger auth() twice per navigation.
/** Auth failure reason for diagnostic logging. */
export type AuthFailReason = "NO_SESSION" | "DOMAIN_MISMATCH" | "NO_TOKEN" | "INVALID_TOKEN";

// React.cache() deduplicates calls within a single server-render pass.
export const getWorkspaceFromCookies = cache(async function _getWorkspace() {
  // Prefer Google OAuth when configured (and ignore the legacy passcode cookie).
  if (googleAuthEnabled()) {
    const session = (await auth()) as AuthSession | null;
    const email = typeof session?.user?.email === "string" ? session.user.email : "";
    const allowed = authAllowedDomain();
    if (!email || !allowed || !email.toLowerCase().endsWith("@" + allowed.toLowerCase())) {
      return null;
    }
    return { teamId: authTeamId(), memberName: memberNameFromSession(session) };
  }

  const cookieStore = await cookies();
  const token = cookieStore.get(WORKSPACE_COOKIE_NAME)?.value;
  if (!token) return null;
  return await verifyWorkspaceSession(token);
});

export async function requireWorkspaceFromCookies() {
  const session = await getWorkspaceFromCookies();
  if (session) return session;

  // Determine specific failure reason for diagnostics.
  let reason: AuthFailReason = "NO_TOKEN";
  if (googleAuthEnabled()) {
    const authSession = (await auth()) as AuthSession | null;
    const email = typeof authSession?.user?.email === "string" ? authSession.user.email : "";
    reason = email ? "DOMAIN_MISMATCH" : "NO_SESSION";
  } else {
    const cookieStore = await cookies();
    const token = cookieStore.get(WORKSPACE_COOKIE_NAME)?.value;
    reason = token ? "INVALID_TOKEN" : "NO_TOKEN";
  }

  const err = new Error("UNAUTHORIZED") as Error & { authFailReason?: AuthFailReason };
  err.authFailReason = reason;
  throw err;
}
