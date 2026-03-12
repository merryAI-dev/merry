import { redirect } from "next/navigation";

import { MobileNav } from "@/components/MobileNav";
import { Sidebar } from "@/components/Sidebar";
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
  const _ws = ws ?? { teamId: "dev", memberName: "dev" };

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg)" }}>
      {/* Desktop sidebar — hidden on mobile */}
      <div className="hidden md:flex md:flex-col md:shrink-0">
        <Sidebar workspace={_ws} />
      </div>

      {/* Right side: mobile topbar + scrollable content */}
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        {/* Mobile: top header + slide-out drawer */}
        <MobileNav workspace={_ws} />

        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
