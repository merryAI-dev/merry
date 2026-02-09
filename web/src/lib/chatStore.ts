import { z } from "zod";

import { PutCommand, QueryCommand } from "@aws-sdk/lib-dynamodb";

export type ChatSessionRow = {
  session_id: string;
  user_id: string;
  user_info: unknown;
  analyzed_files?: unknown;
  generated_files?: unknown;
  created_at?: string;
};

export type ChatMessageRow = {
  id?: string | number;
  session_id: string;
  user_id: string;
  role: string;
  content: string;
  metadata: unknown;
  created_at?: string;
};

import { getDdbDocClient } from "@/lib/aws/ddb";
import { getDdbTableName } from "@/lib/aws/env";

function asString(value: unknown): string {
  if (typeof value === "string") return value;
  if (value == null) return "";
  return String(value);
}

function asOptionalString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function safeJsonParse(value: unknown): unknown {
  if (value == null) return null;
  if (typeof value === "object") return value;
  if (typeof value !== "string") return value;
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function coerceChatMessageRow(row: unknown): ChatMessageRow {
  const r = (row ?? {}) as Record<string, unknown>;
  const idVal = r.id;
  const id = typeof idVal === "string" || typeof idVal === "number" ? idVal : undefined;

  return {
    id,
    session_id: asString(r.session_id),
    user_id: asString(r.user_id),
    role: asString(r.role),
    content: asString(r.content),
    metadata: safeJsonParse(r.metadata),
    created_at: asOptionalString(r.created_at),
  };
}

function coerceChatSessionRow(row: unknown): ChatSessionRow {
  const r = (row ?? {}) as Record<string, unknown>;
  return {
    session_id: asString(r.session_id),
    user_id: asString(r.user_id),
    user_info: safeJsonParse(r.user_info),
    analyzed_files: safeJsonParse(r.analyzed_files),
    generated_files: safeJsonParse(r.generated_files),
    created_at: asOptionalString(r.created_at),
  };
}

function pkTeam(teamId: string) {
  return `TEAM#${teamId}`;
}

function pkTeamSessions(teamId: string) {
  return `TEAM#${teamId}#SESSIONS`;
}

function pkTeamSessionsByPrefix(teamId: string, prefix: string) {
  return `TEAM#${teamId}#SESSIONS#PREFIX#${prefix}`;
}

function pkTeamSessionMessages(teamId: string, sessionId: string) {
  return `TEAM#${teamId}#SESSION#${sessionId}`;
}

function pkTeamActivity(teamId: string) {
  return `TEAM#${teamId}#ACTIVITY`;
}

function inferSessionPrefix(sessionId: string): string {
  const idx = sessionId.indexOf("_");
  if (idx === -1) return "";
  return sessionId.slice(0, idx + 1);
}

function skSessionMeta(sessionId: string) {
  return `SESSION#${sessionId}`;
}

function skSessionIndex(createdAt: string, sessionId: string) {
  return `CREATED#${createdAt}#SESSION#${sessionId}`;
}

function skMessage(createdAt: string, messageId: string) {
  return `MSG#${createdAt}#${messageId}`;
}

function skActivity(createdAt: string, sessionId: string, messageId: string) {
  return `CREATED#${createdAt}#SESSION#${sessionId}#MSG#${messageId}`;
}

export async function ensureSession(teamId: string, sessionId: string, userInfo: object) {
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();
  const now = new Date().toISOString();

  const prefix = inferSessionPrefix(sessionId);
  const sessionItem = {
    pk: pkTeam(teamId),
    sk: skSessionMeta(sessionId),
    entity: "session",
    session_id: sessionId,
    user_id: teamId,
    user_info: userInfo ?? {},
    analyzed_files: [],
    generated_files: [],
    created_at: now,
    updated_at: now,
    session_prefix: prefix,
  };

  try {
    await ddb.send(
      new PutCommand({
        TableName,
        Item: sessionItem,
        ConditionExpression: "attribute_not_exists(pk)",
      }),
    );
  } catch (err) {
    // Session already exists (idempotent).
    const name = (err as { name?: unknown }).name;
    if (name === "ConditionalCheckFailedException") return;
    throw err;
  }

  // Create session listing index items (recent + prefix).
  const idx = {
    pk: pkTeamSessions(teamId),
    sk: skSessionIndex(now, sessionId),
    entity: "session_index",
    session_id: sessionId,
    user_id: teamId,
    user_info: userInfo ?? {},
    created_at: now,
    session_prefix: prefix,
  };
  await ddb.send(new PutCommand({ TableName, Item: idx }));
  if (prefix) {
    const idx2 = { ...idx, pk: pkTeamSessionsByPrefix(teamId, prefix) };
    await ddb.send(new PutCommand({ TableName, Item: idx2 }));
  }
}

export async function addMessage(args: {
  teamId: string;
  sessionId: string;
  role: string;
  content: string;
  metadata?: object;
}) {
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();
  const now = new Date().toISOString();
  const messageId = crypto.randomUUID().replaceAll("-", "").slice(0, 12);

  const msg = {
    pk: pkTeamSessionMessages(args.teamId, args.sessionId),
    sk: skMessage(now, messageId),
    entity: "message",
    id: messageId,
    session_id: args.sessionId,
    user_id: args.teamId,
    role: args.role,
    content: args.content,
    metadata: args.metadata ?? {},
    created_at: now,
  };

  const activity = {
    pk: pkTeamActivity(args.teamId),
    sk: skActivity(now, args.sessionId, messageId),
    entity: "activity",
    id: messageId,
    session_id: args.sessionId,
    user_id: args.teamId,
    role: args.role,
    content: args.content,
    metadata: args.metadata ?? {},
    created_at: now,
  };

  await ddb.send(new PutCommand({ TableName, Item: msg }));
  await ddb.send(new PutCommand({ TableName, Item: activity }));
}

export async function getMessages(teamId: string, sessionId: string): Promise<ChatMessageRow[]> {
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();

  const pk = pkTeamSessionMessages(teamId, sessionId);
  let lastKey: Record<string, unknown> | undefined;
  const out: ChatMessageRow[] = [];

  while (true) {
    const res = await ddb.send(
      new QueryCommand({
        TableName,
        KeyConditionExpression: "pk = :pk",
        ExpressionAttributeValues: { ":pk": pk },
        ExclusiveStartKey: lastKey,
        ScanIndexForward: true,
        Limit: 200,
      }),
    );
    for (const item of res.Items ?? []) out.push(coerceChatMessageRow(item));
    if (!res.LastEvaluatedKey) break;
    lastKey = res.LastEvaluatedKey as Record<string, unknown>;
  }

  // Ensure only the actual message items are returned.
  return out
    .filter((m) => typeof m.role === "string" && m.session_id === sessionId && m.user_id === teamId)
    .sort((a, b) => (a.created_at ?? "").localeCompare(b.created_at ?? ""));
}

export async function getRecentSessions(teamId: string, limit = 30): Promise<ChatSessionRow[]> {
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();
  const res = await ddb.send(
    new QueryCommand({
      TableName,
      KeyConditionExpression: "pk = :pk",
      ExpressionAttributeValues: { ":pk": pkTeamSessions(teamId) },
      Limit: limit,
      ScanIndexForward: false,
    }),
  );
  return (res.Items ?? []).map(coerceChatSessionRow);
}

export async function getSessionsByPrefix(teamId: string, prefix: string, limit = 50): Promise<ChatSessionRow[]> {
  const ddb = getDdbDocClient();
  const TableName = getDdbTableName();
  const res = await ddb.send(
    new QueryCommand({
      TableName,
      KeyConditionExpression: "pk = :pk",
      ExpressionAttributeValues: { ":pk": pkTeamSessionsByPrefix(teamId, prefix) },
      Limit: limit,
      ScanIndexForward: false,
    }),
  );
  return (res.Items ?? []).map(coerceChatSessionRow);
}

export const TaskInputSchema = z.object({
  title: z.string().min(1),
  owner: z.string().optional().default(""),
  due_date: z.string().optional().default(""),
  notes: z.string().optional().default(""),
});
