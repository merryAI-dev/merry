import { ReviewMobileNav } from "@/components/review/ReviewMobileNav";
import { ReviewSidebar } from "@/components/review/ReviewSidebar";
import { getWorkspaceFromCookies } from "@/lib/workspaceServer";

export default async function ReviewLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const ws = await getWorkspaceFromCookies();
  const workspace = ws ?? { teamId: "dev", memberName: "dev" };

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg)" }}>
      <div className="hidden shrink-0 md:flex md:flex-col">
        <ReviewSidebar workspace={workspace} />
      </div>
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <ReviewMobileNav workspace={workspace} />
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
