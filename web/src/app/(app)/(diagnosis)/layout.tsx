import { DiagnosisMobileNav } from "@/components/diagnosis/DiagnosisMobileNav";
import { DiagnosisSidebar } from "@/components/diagnosis/DiagnosisSidebar";
import { isDiagnosisEnabledForWorkspace } from "@/lib/products";
import { getWorkspaceFromCookies } from "@/lib/workspaceServer";
import { redirect } from "next/navigation";

export default async function DiagnosisLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const ws = await getWorkspaceFromCookies();
  if (!isDiagnosisEnabledForWorkspace(ws)) {
    redirect("/products");
  }
  const workspace = ws ?? { teamId: "dev", memberName: "dev" };

  return (
    <div className="flex h-screen overflow-hidden bg-[#F5F1E8]">
      <div className="hidden shrink-0 md:flex md:flex-col">
        <DiagnosisSidebar workspace={workspace} />
      </div>
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <DiagnosisMobileNav workspace={workspace} />
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
