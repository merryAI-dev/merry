import { cookies } from "next/headers";

import { WORKSPACE_COOKIE_NAME, verifyWorkspaceSession } from "@/lib/workspace";
import { auth, authAllowedDomain, authTeamId, googleAuthEnabled } from "@/auth";

function memberNameFromSession(session: any): string {
  const raw = (session && session.memberName) || session?.user?.name || "";
  const name = typeof raw === "string" ? raw.trim() : "";
  if (name) return name;
  const email = typeof session?.user?.email === "string" ? session.user.email : "";
  if (email) return email.split("@")[0] || "member";
  return "member";
}

export async function getWorkspaceFromCookies() {
  // Prefer Google OAuth when configured (and ignore the legacy passcode cookie).
  if (googleAuthEnabled()) {
    const session = await auth();
    const email = typeof (session as any)?.user?.email === "string" ? (session as any).user.email : "";
    const allowed = authAllowedDomain();
    if (!email || !allowed || !email.toLowerCase().endsWith("@" + allowed.toLowerCase())) {
      return null;
    }
    return { teamId: authTeamId(), memberName: memberNameFromSession(session as any) };
  }

  const cookieStore = await cookies();
  const token = cookieStore.get(WORKSPACE_COOKIE_NAME)?.value;
  if (!token) return null;
  return await verifyWorkspaceSession(token);
}

export async function requireWorkspaceFromCookies() {
  const session = await getWorkspaceFromCookies();
  if (!session) {
    throw new Error("UNAUTHORIZED");
  }
  return session;
}
