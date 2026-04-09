import { redirect } from "next/navigation";

import { getWorkspaceFromCookies } from "@/lib/workspaceServer";

/** Skip auth only in local dev (MERRY_AUTH_SKIP=true). Defaults to enforced. */
const AUTH_SKIP = process.env.MERRY_AUTH_SKIP === "true";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const ws = await getWorkspaceFromCookies();
  if (!ws && !AUTH_SKIP) redirect("/");

  return (
    <div className="min-h-screen" style={{ background: "var(--bg)" }}>{children}</div>
  );
}
