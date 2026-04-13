import { SendMessageCommand } from "@aws-sdk/client-sqs";

import { getSqsQueueUrl } from "@/lib/aws/env";
import { getSqsClient } from "@/lib/aws/sqs";
import {
  createDiagnosisRun,
  createDiagnosisSession,
  recordDiagnosisUpload,
} from "@/lib/diagnosisSessionStore";
import { createJob, getUploadFile } from "@/lib/jobStore";

export async function startDiagnosisFromUploadedFile(args: {
  teamId: string;
  memberName: string;
  fileId: string;
  title?: string;
}) {
  const file = await getUploadFile(args.teamId, args.fileId);
  if (!file) throw new Error("FILE_NOT_FOUND");
  if (file.status !== "uploaded") throw new Error("FILE_NOT_UPLOADED");

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
