import { addMessage, ensureSession, getMessages } from "@/lib/chatStore";

export type TeamComment = {
  text: string;
  created_by: string;
  created_at: string;
};

function commentsSessionId(teamId: string) {
  return `comments_${teamId}`;
}

export async function listTeamComments(teamId: string, limit = 20): Promise<TeamComment[]> {
  const messages = await getMessages(teamId, commentsSessionId(teamId));
  const comments: TeamComment[] = [];
  for (const msg of messages) {
    if (msg.role !== "team_comment") continue;
    const meta = (msg.metadata ?? {}) as Record<string, unknown>;
    const created_by =
      (typeof meta["created_by"] === "string" ? meta["created_by"] : undefined) ||
      (typeof meta["createdBy"] === "string" ? meta["createdBy"] : undefined) ||
      "";
    const created_at =
      (typeof meta["created_at"] === "string" ? meta["created_at"] : undefined) ||
      msg.created_at ||
      "";
    comments.push({
      text: msg.content || "",
      created_by,
      created_at,
    });
  }
  return comments.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || "")).slice(0, limit);
}

export async function addTeamComment(args: {
  teamId: string;
  createdBy: string;
  text: string;
}): Promise<TeamComment> {
  const now = new Date().toISOString();
  const comment: TeamComment = {
    text: args.text.trim(),
    created_by: args.createdBy,
    created_at: now,
  };

  const sessionId = commentsSessionId(args.teamId);
  await ensureSession(args.teamId, sessionId, { type: "team_comments" });
  await addMessage({
    teamId: args.teamId,
    sessionId,
    role: "team_comment",
    content: comment.text,
    metadata: comment,
  });

  return comment;
}
