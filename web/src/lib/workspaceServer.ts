import { cookies } from "next/headers";

import { WORKSPACE_COOKIE_NAME, verifyWorkspaceSession } from "@/lib/workspace";

export async function getWorkspaceFromCookies() {
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
