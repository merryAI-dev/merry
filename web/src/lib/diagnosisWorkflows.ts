import { PutObjectCommand } from "@aws-sdk/client-s3";
import { basename } from "path";
import { readFile } from "fs/promises";

import { getS3BucketName } from "@/lib/aws/env";
import { getS3Client } from "@/lib/aws/s3";
import {
  appendDiagnosisAssistantMessage,
  appendDiagnosisConversationTurn,
  createDiagnosisSession,
  getDiagnosisSessionDetail,
  getDiagnosisSessionRuntimeState,
  markDiagnosisSessionStatus,
  recordDiagnosisArtifact,
  recordDiagnosisContextDocument,
  recordDiagnosisUpload,
  saveDiagnosisConversationStart,
  setDiagnosisConversationState,
} from "@/lib/diagnosisSessionStore";
import {
  buildDiagnosisGeneratePrompt,
  buildDiagnosisReplyPrompt,
  buildDiagnosisStartPrompt,
  materializeDiagnosisSourceFile,
  runDiagnosisAgentTurn,
} from "@/lib/diagnosisAgentBridge";
import { normalizeDiagnosisDocumentFromUpload } from "@/lib/diagnosisIngestion";
import { getUploadFile } from "@/lib/jobStore";

function diagnosisModel() {
  return process.env.MERRY_DIAGNOSIS_CHAT_MODEL ?? "claude-opus-4-6";
}

function getExt(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot >= 0 ? filename.slice(dot).toLowerCase() : "";
}

function assertPrimaryDiagnosisFile(filename: string) {
  const ext = getExt(filename);
  if (ext !== ".xlsx" && ext !== ".xls") {
    throw new Error("UNSUPPORTED_PRIMARY_FILE");
  }
}

function assertContextDiagnosisFile(filename: string) {
  const ext = getExt(filename);
  if (ext !== ".pdf" && ext !== ".docx" && ext !== ".pptx") {
    throw new Error("UNSUPPORTED_CONTEXT_FILE");
  }
}

export async function startDiagnosisFromUploadedFile(args: {
  teamId: string;
  memberName: string;
  fileId: string;
  title?: string;
}) {
  const file = await getUploadFile(args.teamId, args.fileId);
  if (!file) throw new Error("FILE_NOT_FOUND");
  if (file.status !== "uploaded") throw new Error("FILE_NOT_UPLOADED");
  assertPrimaryDiagnosisFile(file.originalName);

  const session = await createDiagnosisSession({
    teamId: args.teamId,
    title: args.title,
    createdBy: args.memberName,
    originalFileName: file.originalName,
  });

  await recordDiagnosisUpload({
    teamId: args.teamId,
    sessionId: session.sessionId,
    file,
    actor: args.memberName,
  });

  let materializedPath: string | undefined;
  try {
    await markDiagnosisSessionStatus({
      teamId: args.teamId,
      sessionId: session.sessionId,
      status: "processing",
    });

    const materialized = await materializeDiagnosisSourceFile({
      teamId: args.teamId,
      sessionId: session.sessionId,
      file,
    });
    materializedPath = materialized.localPath;

    const agentTurn = await runDiagnosisAgentTurn({
      mode: "start",
      sessionId: session.sessionId,
      teamId: args.teamId,
      memberName: args.memberName,
      history: [],
      prompt: buildDiagnosisStartPrompt(materialized.localPath),
      model: diagnosisModel(),
      sourceFilePath: materialized.localPath,
    });

    const assistantMessage = await saveDiagnosisConversationStart({
      teamId: args.teamId,
      sessionId: session.sessionId,
      actor: args.memberName,
      assistantText: agentTurn.assistantText,
      sourceFile: {
        fileId: materialized.fileId,
        originalName: materialized.originalName,
      },
      sourceFileLocalPath: materialized.localPath,
      analysisSummary: agentTurn.analysisSummary,
    });

    await markDiagnosisSessionStatus({
      teamId: args.teamId,
      sessionId: session.sessionId,
      status: "ready",
    });

    return {
      session: {
        ...session,
        status: "ready" as const,
      },
      assistantMessage,
    };
  } catch (err) {
    await markDiagnosisSessionStatus({
      teamId: args.teamId,
      sessionId: session.sessionId,
      status: "failed",
    }).catch(() => {});
    if (materializedPath) {
      await setDiagnosisConversationState({
        teamId: args.teamId,
        sessionId: session.sessionId,
        status: "failed",
        canGenerateReport: false,
        sourceFile: {
          fileId: file.fileId,
          originalName: file.originalName,
        },
        sourceFileLocalPath: materializedPath,
      }).catch(() => {});
    }
    throw err;
  }
}

export async function attachDiagnosisContextDocumentFromUploadedFile(args: {
  teamId: string;
  memberName: string;
  sessionId: string;
  fileId: string;
}) {
  const file = await getUploadFile(args.teamId, args.fileId);
  if (!file) throw new Error("FILE_NOT_FOUND");
  if (file.status !== "uploaded") throw new Error("FILE_NOT_UPLOADED");
  assertContextDiagnosisFile(file.originalName);

  const normalized = await normalizeDiagnosisDocumentFromUpload({
    file,
    role: "context",
  });

  const document = await recordDiagnosisContextDocument({
    teamId: args.teamId,
    sessionId: args.sessionId,
    actor: args.memberName,
    file,
    normalized,
  });

  return { document };
}

export async function replyInDiagnosisSession(args: {
  teamId: string;
  memberName: string;
  sessionId: string;
  content: string;
}) {
  const detail = await getDiagnosisSessionDetail(args.teamId, args.sessionId);
  if (!detail) throw new Error("NOT_FOUND");

  const runtimeState = await getDiagnosisSessionRuntimeState(args.teamId, args.sessionId);
  const sourceFileLocalPath = runtimeState?.sourceFileLocalPath;
  const sourceFile = runtimeState?.conversationState?.sourceFile;
  if (!sourceFileLocalPath || !sourceFile) throw new Error("SOURCE_FILE_MISSING");

  await markDiagnosisSessionStatus({
    teamId: args.teamId,
    sessionId: args.sessionId,
    status: "processing",
  });
  await setDiagnosisConversationState({
    teamId: args.teamId,
    sessionId: args.sessionId,
    status: "thinking",
    canGenerateReport: true,
    sourceFile,
    sourceFileLocalPath,
    analysisSummary: runtimeState?.conversationState?.analysisSummary ?? null,
  });

  try {
    const history = detail.messages.map((message) => ({
      role: message.role,
      content: message.content,
    }));
    const agentTurn = await runDiagnosisAgentTurn({
      mode: "reply",
      sessionId: args.sessionId,
      teamId: args.teamId,
      memberName: args.memberName,
      history,
      prompt: buildDiagnosisReplyPrompt(sourceFileLocalPath, args.content),
      model: diagnosisModel(),
      sourceFilePath: sourceFileLocalPath,
    });

    const assistantMessage = await appendDiagnosisConversationTurn({
      teamId: args.teamId,
      sessionId: args.sessionId,
      userContent: args.content,
      assistantText: agentTurn.assistantText,
      analysisSummary: agentTurn.analysisSummary,
    });

    await markDiagnosisSessionStatus({
      teamId: args.teamId,
      sessionId: args.sessionId,
      status: "ready",
    });

    return { assistantMessage };
  } catch (err) {
    await markDiagnosisSessionStatus({
      teamId: args.teamId,
      sessionId: args.sessionId,
      status: "failed",
    }).catch(() => {});
    await setDiagnosisConversationState({
      teamId: args.teamId,
      sessionId: args.sessionId,
      status: "failed",
      canGenerateReport: true,
      sourceFile,
      sourceFileLocalPath,
      analysisSummary: runtimeState?.conversationState?.analysisSummary ?? null,
    }).catch(() => {});
    throw err;
  }
}

export async function generateDiagnosisReport(args: {
  teamId: string;
  memberName: string;
  sessionId: string;
}) {
  const detail = await getDiagnosisSessionDetail(args.teamId, args.sessionId);
  if (!detail) throw new Error("NOT_FOUND");

  const runtimeState = await getDiagnosisSessionRuntimeState(args.teamId, args.sessionId);
  const sourceFileLocalPath = runtimeState?.sourceFileLocalPath;
  const sourceFile = runtimeState?.conversationState?.sourceFile;
  if (!sourceFileLocalPath || !sourceFile) throw new Error("SOURCE_FILE_MISSING");

  await markDiagnosisSessionStatus({
    teamId: args.teamId,
    sessionId: args.sessionId,
    status: "processing",
  });
  await setDiagnosisConversationState({
    teamId: args.teamId,
    sessionId: args.sessionId,
    status: "generating_report",
    canGenerateReport: true,
    sourceFile,
    sourceFileLocalPath,
    analysisSummary: runtimeState?.conversationState?.analysisSummary ?? null,
  });

  try {
    const agentTurn = await runDiagnosisAgentTurn({
      mode: "generate",
      sessionId: args.sessionId,
      teamId: args.teamId,
      memberName: args.memberName,
      history: detail.messages.map((message) => ({
        role: message.role,
        content: message.content,
      })),
      prompt: buildDiagnosisGeneratePrompt(sourceFileLocalPath),
      model: diagnosisModel(),
      sourceFilePath: sourceFileLocalPath,
    });

    const generatedFile = agentTurn.latestGeneratedFile;
    if (!generatedFile) throw new Error("REPORT_NOT_GENERATED");

    const fileBytes = await readFile(generatedFile);
    const bucket = getS3BucketName();
    const label = basename(generatedFile);
    const artifactKey = `diagnosis-artifacts/${args.teamId}/${args.sessionId}/${crypto
      .randomUUID()
      .replaceAll("-", "")
      .slice(0, 16)}_${label}`;

    const s3 = getS3Client();
    await s3.send(
      new PutObjectCommand({
        Bucket: bucket,
        Key: artifactKey,
        Body: fileBytes,
        ContentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      }),
    );

    const artifact = await recordDiagnosisArtifact({
      teamId: args.teamId,
      sessionId: args.sessionId,
      actor: args.memberName,
      label,
      contentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      s3Bucket: bucket,
      s3Key: artifactKey,
      sizeBytes: fileBytes.byteLength,
    });

    const assistantMessage = await appendDiagnosisAssistantMessage({
      teamId: args.teamId,
      sessionId: args.sessionId,
      assistantText:
        agentTurn.assistantText || `${label} 결과물을 생성했습니다. 다운로드해서 확인해 주세요.`,
      analysisSummary: agentTurn.analysisSummary,
    });

    await markDiagnosisSessionStatus({
      teamId: args.teamId,
      sessionId: args.sessionId,
      status: "ready",
    });

    return { assistantMessage, artifact };
  } catch (err) {
    await markDiagnosisSessionStatus({
      teamId: args.teamId,
      sessionId: args.sessionId,
      status: "failed",
    }).catch(() => {});
    await setDiagnosisConversationState({
      teamId: args.teamId,
      sessionId: args.sessionId,
      status: "failed",
      canGenerateReport: true,
      sourceFile,
      sourceFileLocalPath,
      analysisSummary: runtimeState?.conversationState?.analysisSummary ?? null,
    }).catch(() => {});
    throw err;
  }
}
