import { QueryCommand } from "@aws-sdk/lib-dynamodb";

export type TeamActivity = {
  session_id: string;
  role: string;
  content: string;
  created_at: string;
  member: string;
};

function safeJsonParse(value: unknown): Record<string, unknown> {
  if (value == null) return {};
  if (typeof value === "object") return value as Record<string, unknown>;
  if (typeof value !== "string") return {};
  try {
    const parsed = JSON.parse(value) as unknown;
    return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

export async function getRecentActivity(teamId: string, limit = 30): Promise<TeamActivity[]> {
  const { getDdbDocClient } = await import("@/lib/aws/ddb");
  const { getDdbTableName } = await import("@/lib/aws/env");

  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();
  const pk = `TEAM#${teamId}#ACTIVITY`;

  const res = await ddb.send(
    new QueryCommand({
      TableName,
      KeyConditionExpression: "pk = :pk",
      ExpressionAttributeValues: { ":pk": pk },
      Limit: limit,
      ScanIndexForward: false,
    }),
  );

  const out: TeamActivity[] = [];
  for (const row of res.Items ?? []) {
    const r = (row ?? {}) as Record<string, unknown>;
    const meta = safeJsonParse(r.metadata) as Record<string, unknown>;
    const member =
      (typeof meta["member"] === "string" ? meta["member"] : undefined) ||
      (typeof meta["created_by"] === "string" ? meta["created_by"] : undefined) ||
      (typeof meta["createdBy"] === "string" ? meta["createdBy"] : undefined) ||
      "";
    out.push({
      session_id: typeof r.session_id === "string" ? r.session_id : "",
      role: typeof r.role === "string" ? r.role : "",
      content: typeof r.content === "string" ? r.content : "",
      created_at: typeof r.created_at === "string" ? r.created_at : "",
      member,
    });
  }
  return out;
}
