import { redirect } from "next/navigation";

import { getWorkspaceFromCookies } from "@/lib/workspaceServer";

import { ReportNewWizard } from "./wizard";

/** Skip auth only in local dev (MERRY_AUTH_SKIP=true). Defaults to enforced. */
const AUTH_SKIP = process.env.MERRY_AUTH_SKIP === "true";

export default async function ReportNewPage() {
  const ws = await getWorkspaceFromCookies();
  if (!ws && !AUTH_SKIP) redirect("/");
  const _ws = ws ?? { teamId: "dev", memberName: "dev" };

  return <ReportNewWizard initialAuthor={_ws.memberName} />;
}

