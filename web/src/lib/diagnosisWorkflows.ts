import { SendMessageCommand } from "@aws-sdk/client-sqs";

import { getSqsQueueUrl } from "@/lib/aws/env";
import { getSqsClient } from "@/lib/aws/sqs";
import { normalizeDiagnosisDocumentFromUpload } from "@/lib/diagnosisIngestion";
import {
  createDiagnosisRun,
  createDiagnosisSession,
  recordDiagnosisContextDocument,
  recordDiagnosisUpload,
} from "@/lib/diagnosisSessionStore";
import { createJob, getUploadFile } from "@/lib/jobStore";

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

  const jobId = crypto.randomUUID().replaceAll("-", "").slice(0, 16);
  const correlationId = `${jobId}-${Date.now().toString(36)}`;
  const createdAt = new Date().toISOString();

  await createJob({
    jobId,
    teamId: args.teamId,
    type: "diagnosis_analysis",
    status: "queued",
    title: (args.title ?? "현황진단 실행").trim(),
    createdBy: args.memberName,
    createdAt,
    inputFileIds: [args.fileId],
    params: {
      diagnosisSessionId: session.sessionId,
    },
  });

  const sqs = getSqsClient();
  await sqs.send(
    new SendMessageCommand({
      QueueUrl: getSqsQueueUrl(),
      MessageBody: JSON.stringify({
        teamId: args.teamId,
        jobId,
        correlationId,
      }),
    }),
  );

  const run = await createDiagnosisRun({
    teamId: args.teamId,
    sessionId: session.sessionId,
    legacyJobId: jobId,
    status: "queued",
    actor: args.memberName,
  });

  return {
    session,
    run,
    legacyJobId: jobId,
  };
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
