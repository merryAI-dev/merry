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
    <div className="mx-auto flex max-w-7xl gap-6 px-4 py-4">
      <Sidebar workspace={ws} />
      <main className="min-w-0 flex-1 pb-10">{children}</main>
    </div>
  );
}

