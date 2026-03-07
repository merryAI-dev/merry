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
    <>
      {/* Mobile: top header + slide-out drawer */}
      <MobileNav workspace={_ws} />

      <div className="flex gap-4 px-3 py-3 max-md:px-0 max-md:py-0">
        {/* Desktop sidebar — hidden on mobile */}
        <div className="hidden md:block">
          <Sidebar workspace={_ws} />
        </div>
        <main className="min-w-0 flex-1 pb-8 max-md:px-4 max-md:pt-4">{children}</main>
      </div>
    </>
  );
}
