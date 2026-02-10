import { redirect } from "next/navigation";

import { Sidebar } from "@/components/Sidebar";
import { getWorkspaceFromCookies } from "@/lib/workspaceServer";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const ws = await getWorkspaceFromCookies();
  if (!ws) redirect("/");

  return (
    <div className="flex gap-4 px-3 py-3">
      <Sidebar workspace={ws} />
      <main className="min-w-0 flex-1 pb-8">{children}</main>
    </div>
  );
}
