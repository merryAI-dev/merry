import { PutCommand, QueryCommand } from "@aws-sdk/lib-dynamodb";

export type PresenceMember = {
  memberKey: string;
  memberName: string;
  memberImage?: string;
  lastSeenAt: string;
};

function pkPresence(teamId: string, sessionId: string) {
  return `TEAM#${teamId}#PRESENCE#REPORT#${sessionId}`;
}

function skMember(memberKey: string) {
  return `MEMBER#${memberKey}`;
}

function asString(v: unknown): string {
  return typeof v === "string" ? v : "";
}

export async function upsertReportPresence(args: {
  teamId: string;
  sessionId: string;
  memberKey: string;
  memberName: string;
  memberImage?: string;
}) {
  const { getDdbDocClient } = await import("@/lib/aws/ddb");
  const { getDdbTableName } = await import("@/lib/aws/env");

  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();

  const now = new Date().toISOString();
  const item = {
    pk: pkPresence(args.teamId, args.sessionId),
    sk: skMember(args.memberKey),
    entity: "presence",
    scope: "report",
    scope_id: args.sessionId,
    memberKey: args.memberKey,
    memberName: args.memberName,
    memberImage: args.memberImage ?? "",
    lastSeenAt: now,
    updated_at: now,
  };

  await ddb.send(new PutCommand({ TableName, Item: item }));
}

export async function listReportPresence(args: {
  teamId: string;
  sessionId: string;
  withinSeconds?: number;
  limit?: number;
}): Promise<PresenceMember[]> {
  const { getDdbDocClient } = await import("@/lib/aws/ddb");
  const { getDdbTableName } = await import("@/lib/aws/env");

  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();

  const pk = pkPresence(args.teamId, args.sessionId);
  const res = await ddb.send(
    new QueryCommand({
      TableName,
      KeyConditionExpression: "pk = :pk",
      ExpressionAttributeValues: { ":pk": pk },
      Limit: Math.max(1, Math.min(args.limit ?? 80, 200)),
      ScanIndexForward: true,
    }),
  );

  const withinMs = Math.max(5, args.withinSeconds ?? 60) * 1000;
  const cutoff = Date.now() - withinMs;

  const out: PresenceMember[] = [];
  for (const row of res.Items ?? []) {
    const r = (row ?? {}) as Record<string, unknown>;
    const lastSeenAt = asString(r.lastSeenAt);
    const t = lastSeenAt ? Date.parse(lastSeenAt) : NaN;
    if (!Number.isFinite(t) || t < cutoff) continue;

    const memberKey = asString(r.memberKey) || asString(r.sk).replace(/^MEMBER#/, "");
    const memberName = asString(r.memberName);
    const memberImage = asString(r.memberImage) || undefined;
    if (!memberKey || !memberName) continue;

    out.push({ memberKey, memberName, memberImage, lastSeenAt });
  }

  out.sort((a, b) => (b.lastSeenAt || "").localeCompare(a.lastSeenAt || ""));
  return out;
}

