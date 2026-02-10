import { addMessage, ensureSession, getMessages, getSessionsByPrefix } from "@/lib/chatStore";

export type DraftSummary = {
  draftId: string;
  title: string;
  sessionId: string;
  createdAt?: string;
};

export type DraftVersion = {
  versionId: string;
  title: string;
  content: string;
  createdBy: string;
  createdAt: string;
};

export type DraftVersionSource = {
  kind: string;
  jobId?: string;
  artifactId?: string;
};

export type DraftCommentKind = "수정" | "좋음" | "대안";
export type DraftCommentStatus = "open" | "accepted" | "rejected";

export type DraftAnchor = {
  start: number;
  end: number;
  quote: string;
  context?: string;
};

export type DraftComment = {
  commentId: string;
  versionId: string;
  kind: DraftCommentKind;
  status: DraftCommentStatus;
  text: string;
  anchor: DraftAnchor;
  threadId: string;
  parentId?: string;
  createdBy: string;
  createdAt: string;
  updatedAt?: string;
};

function draftSessionId(draftId: string) {
  return `draft_${draftId}`;
}

export async function listDrafts(teamId: string): Promise<DraftSummary[]> {
  const sessions = await getSessionsByPrefix(teamId, "draft_", 80);
  const out: DraftSummary[] = [];
  for (const s of sessions) {
    const info = (s.user_info ?? {}) as Record<string, unknown>;
    const inferredDraftId =
      typeof s.session_id === "string" ? s.session_id.replace(/^draft_/, "") : "";
    const draftId = typeof info["draftId"] === "string" ? info["draftId"] : inferredDraftId;
    out.push({
      draftId,
      title: typeof info["title"] === "string" ? info["title"] : "Untitled",
      sessionId: s.session_id,
      createdAt: s.created_at,
    });
  }
  return out;
}

export async function createDraft(args: {
  teamId: string;
  createdBy: string;
  title: string;
  content: string;
}) {
  const now = new Date().toISOString();
  const draftId = crypto.randomUUID().replaceAll("-", "").slice(0, 12);
  const sessionId = draftSessionId(draftId);
  const versionId = crypto.randomUUID().replaceAll("-", "").slice(0, 12);

  await ensureSession(args.teamId, sessionId, {
    type: "draft",
    draftId,
    title: args.title.trim(),
  });

  await addMessage({
    teamId: args.teamId,
    sessionId,
    role: "draft_version",
    content: args.content,
    metadata: {
      draft_id: draftId,
      version_id: versionId,
      title: args.title.trim(),
      created_by: args.createdBy,
      created_at: now,
    },
  });

  return { draftId, versionId };
}

export async function addDraftVersion(args: {
  teamId: string;
  draftId: string;
  createdBy: string;
  title: string;
  content: string;
  source?: DraftVersionSource;
}) {
  const now = new Date().toISOString();
  const sessionId = draftSessionId(args.draftId);
  const versionId = crypto.randomUUID().replaceAll("-", "").slice(0, 12);
  await ensureSession(args.teamId, sessionId, { type: "draft", draftId: args.draftId, title: args.title.trim() });

  const source = args.source ?? null;
  const metadata: Record<string, unknown> = {
    draft_id: args.draftId,
    version_id: versionId,
    title: args.title.trim(),
    created_by: args.createdBy,
    created_at: now,
  };
  if (source?.kind) metadata["source_kind"] = source.kind;
  if (source?.jobId) metadata["source_job_id"] = source.jobId;
  if (source?.artifactId) metadata["source_artifact_id"] = source.artifactId;

  await addMessage({
    teamId: args.teamId,
    sessionId,
    role: "draft_version",
    content: args.content,
    metadata,
  });
  return { versionId };
}

export async function findDraftVersionBySource(args: {
  teamId: string;
  draftId: string;
  source: DraftVersionSource;
}): Promise<{ versionId: string } | null> {
  const sessionId = draftSessionId(args.draftId);
  const messages = await getMessages(args.teamId, sessionId);

  const wantKind = (args.source.kind ?? "").trim();
  const wantJobId = (args.source.jobId ?? "").trim();
  const wantArtifactId = (args.source.artifactId ?? "").trim();
  if (!wantKind) return null;

  for (const msg of messages) {
    if (msg.role !== "draft_version") continue;
    const meta = (msg.metadata ?? {}) as Record<string, unknown>;

    const kind = typeof meta["source_kind"] === "string" ? meta["source_kind"] : "";
    const jobId = typeof meta["source_job_id"] === "string" ? meta["source_job_id"] : "";
    const artifactId = typeof meta["source_artifact_id"] === "string" ? meta["source_artifact_id"] : "";
    if (!kind || kind !== wantKind) continue;
    if (wantJobId && jobId !== wantJobId) continue;
    if (wantArtifactId && artifactId !== wantArtifactId) continue;

    const versionId = typeof meta["version_id"] === "string" ? meta["version_id"] : "";
    if (!versionId) continue;
    return { versionId };
  }

  return null;
}

export async function addDraftComment(args: {
  teamId: string;
  draftId: string;
  versionId: string;
  createdBy: string;
  kind: DraftCommentKind;
  text: string;
  anchor: DraftAnchor;
  threadId?: string;
  parentId?: string;
}) {
  const now = new Date().toISOString();
  const sessionId = draftSessionId(args.draftId);
  const commentId = crypto.randomUUID().replaceAll("-", "").slice(0, 12);
  const threadId = args.threadId || commentId;

  await addMessage({
    teamId: args.teamId,
    sessionId,
    role: "draft_comment",
    content: args.text.trim(),
    metadata: {
      comment_id: commentId,
      thread_id: threadId,
      parent_id: args.parentId ?? "",
      version_id: args.versionId,
      kind: args.kind,
      status: "open",
      anchor: args.anchor,
      created_by: args.createdBy,
      created_at: now,
    },
  });

  return { commentId, threadId };
}

export async function setDraftCommentStatus(args: {
  teamId: string;
  draftId: string;
  commentId: string;
  status: DraftCommentStatus;
  updatedBy: string;
}) {
  const now = new Date().toISOString();
  const sessionId = draftSessionId(args.draftId);
  await addMessage({
    teamId: args.teamId,
    sessionId,
    role: "draft_comment_update",
    content: `status:${args.commentId}`,
    metadata: {
      comment_id: args.commentId,
      status: args.status,
      updated_by: args.updatedBy,
      updated_at: now,
    },
  });
}

export async function getDraftDetail(teamId: string, draftId: string): Promise<{
  versions: DraftVersion[];
  comments: DraftComment[];
}> {
  const sessionId = draftSessionId(draftId);
  const messages = await getMessages(teamId, sessionId);

  const versions: DraftVersion[] = [];
  const commentsById: Record<string, DraftComment> = {};
  for (const msg of messages) {
    const meta = (msg.metadata ?? {}) as Record<string, unknown>;

    if (msg.role === "draft_version") {
      const versionId = typeof meta["version_id"] === "string" ? meta["version_id"] : "";
      if (!versionId) continue;
      const title = typeof meta["title"] === "string" ? meta["title"] : "Draft";
      const createdBy = typeof meta["created_by"] === "string" ? meta["created_by"] : "";
      const createdAt =
        (typeof meta["created_at"] === "string" ? meta["created_at"] : undefined) ||
        msg.created_at ||
        "";
      versions.push({
        versionId,
        title,
        content: msg.content || "",
        createdBy,
        createdAt,
      });
      continue;
    }

    if (msg.role === "draft_comment") {
      const commentId = typeof meta["comment_id"] === "string" ? meta["comment_id"] : "";
      if (!commentId) continue;
      const current = commentsById[commentId];
      if (!current) {
        const versionId = typeof meta["version_id"] === "string" ? meta["version_id"] : "";
        const kind = meta["kind"];
        const status = meta["status"];
        const parsedKind: DraftCommentKind =
          kind === "수정" || kind === "좋음" || kind === "대안" ? kind : "수정";
        const parsedStatus: DraftCommentStatus =
          status === "open" || status === "accepted" || status === "rejected" ? status : "open";
        const anchorRaw = meta["anchor"];
        const anchorObj = (anchorRaw && typeof anchorRaw === "object" ? (anchorRaw as Record<string, unknown>) : {}) as Record<string, unknown>;
        const anchor: DraftAnchor = {
          start: typeof anchorObj["start"] === "number" ? anchorObj["start"] : 0,
          end: typeof anchorObj["end"] === "number" ? anchorObj["end"] : 0,
          quote: typeof anchorObj["quote"] === "string" ? anchorObj["quote"] : "",
          context: typeof anchorObj["context"] === "string" ? anchorObj["context"] : undefined,
        };
        const threadId = typeof meta["thread_id"] === "string" ? meta["thread_id"] : commentId;
        const parentId = typeof meta["parent_id"] === "string" && meta["parent_id"] ? meta["parent_id"] : undefined;
        const createdBy = typeof meta["created_by"] === "string" ? meta["created_by"] : "";
        const createdAt =
          (typeof meta["created_at"] === "string" ? meta["created_at"] : undefined) ||
          msg.created_at ||
          "";
        const updatedAt = typeof meta["updated_at"] === "string" ? meta["updated_at"] : undefined;

        commentsById[commentId] = {
          commentId,
          versionId,
          kind: parsedKind,
          status: parsedStatus,
          text: msg.content || "",
          anchor,
          threadId,
          parentId,
          createdBy,
          createdAt,
          updatedAt,
        };
      } else {
        // Treat additional draft_comment rows as updates (rare).
        if (meta["status"] === "open" || meta["status"] === "accepted" || meta["status"] === "rejected") {
          current.status = meta["status"];
        }
        if (meta["kind"] === "수정" || meta["kind"] === "좋음" || meta["kind"] === "대안") {
          current.kind = meta["kind"];
        }
        if (meta["anchor"] && typeof meta["anchor"] === "object") {
          const anchorObj = meta["anchor"] as Record<string, unknown>;
          current.anchor = {
            start: typeof anchorObj["start"] === "number" ? anchorObj["start"] : current.anchor.start,
            end: typeof anchorObj["end"] === "number" ? anchorObj["end"] : current.anchor.end,
            quote: typeof anchorObj["quote"] === "string" ? anchorObj["quote"] : current.anchor.quote,
            context: typeof anchorObj["context"] === "string" ? anchorObj["context"] : current.anchor.context,
          };
        }
        current.text = msg.content || current.text;
        const updatedAt =
          (typeof meta["updated_at"] === "string" ? meta["updated_at"] : undefined) ||
          msg.created_at ||
          current.updatedAt;
        current.updatedAt = updatedAt;
      }
      continue;
    }

    if (msg.role === "draft_comment_update") {
      const commentId = typeof meta["comment_id"] === "string" ? meta["comment_id"] : "";
      if (!commentId) continue;
      const current = commentsById[commentId];
      if (!current) continue;
      if (meta["status"] === "open" || meta["status"] === "accepted" || meta["status"] === "rejected") {
        current.status = meta["status"];
      }
      const updatedAt =
        (typeof meta["updated_at"] === "string" ? meta["updated_at"] : undefined) ||
        msg.created_at ||
        current.updatedAt;
      current.updatedAt = updatedAt;
    }
  }

  const comments = Object.values(commentsById).sort((a, b) => (a.createdAt || "").localeCompare(b.createdAt || ""));
  versions.sort((a, b) => (a.createdAt || "").localeCompare(b.createdAt || ""));

  return { versions, comments };
}
