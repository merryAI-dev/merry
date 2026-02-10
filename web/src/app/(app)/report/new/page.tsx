import { redirect } from "next/navigation";

import { getWorkspaceFromCookies } from "@/lib/workspaceServer";

import { ReportNewWizard } from "./wizard";

export default async function ReportNewPage() {
  const ws = await getWorkspaceFromCookies();
  if (!ws) redirect("/");

  return <ReportNewWizard initialAuthor={ws.memberName} />;
}

