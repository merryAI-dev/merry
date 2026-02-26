import { redirect } from "next/navigation";

import { getWorkspaceFromCookies } from "@/lib/workspaceServer";

import { ReportNewWizard } from "./wizard";

export default async function ReportNewPage() {
  const ws = await getWorkspaceFromCookies();
  // TODO: re-enable auth before deploy
  // if (!ws) redirect("/");
  const _ws = ws ?? { teamId: "dev", memberName: "dev" };

  return <ReportNewWizard initialAuthor={_ws.memberName} />;
}

