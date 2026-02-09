import { SendMessageCommand } from "@aws-sdk/client-sqs";
import { NextResponse } from "next/server";
import { z } from "zod";

import { getSqsClient } from "@/lib/aws/sqs";
import { getSqsQueueUrl } from "@/lib/aws/env";
import { createJob, getUploadFile, listRecentJobs, type JobType } from "@/lib/jobStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const CreateSchema = z.object({
  jobType: z.enum(["exit_projection", "diagnosis_analysis", "pdf_evidence", "pdf_parse", "contract_review"]),
  title: z.string().optional(),
  fileIds: z.array(z.string().min(6)).min(1).max(8),
  params: z.record(z.string(), z.unknown()).optional(),
});

export async function GET() {
  try {
    const ws = await requireWorkspaceFromCookies();
    const jobs = await listRecentJobs(ws.teamId, 30);
    return NextResponse.json({ ok: true, jobs });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    return NextResponse.json({ ok: false, error: "FAILED" }, { status });
  }
}

export async function POST(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = CreateSchema.parse(await req.json());

    // Enforce job-type specific arity to keep worker behavior predictable.
    if (body.jobType === "contract_review") {
      if (body.fileIds.length > 2) {
        return NextResponse.json({ ok: false, error: "TOO_MANY_FILES" }, { status: 400 });
      }
    } else {
      if (body.fileIds.length !== 1) {
        return NextResponse.json({ ok: false, error: "INVALID_FILE_COUNT" }, { status: 400 });
      }
    }

    // Validate input file existence and upload completion.
    for (const fileId of body.fileIds) {
      const file = await getUploadFile(ws.teamId, fileId);
      if (!file) return NextResponse.json({ ok: false, error: "FILE_NOT_FOUND" }, { status: 404 });
      if (file.status !== "uploaded") {
        return NextResponse.json({ ok: false, error: "FILE_NOT_UPLOADED" }, { status: 400 });
      }
    }

    const jobId = crypto.randomUUID().replaceAll("-", "").slice(0, 16);
    const createdAt = new Date().toISOString();
    const type = body.jobType as JobType;
    const title = (body.title ?? "").trim() || ({
      exit_projection: "Exit 프로젝션",
      diagnosis_analysis: "기업진단 분석",
      pdf_evidence: "PDF 근거 추출",
      pdf_parse: "PDF 파싱",
      contract_review: "계약서 검토",
    }[type]);

    await createJob({
      jobId,
      teamId: ws.teamId,
      type,
      status: "queued",
      title,
      createdBy: ws.memberName,
      createdAt,
      inputFileIds: body.fileIds,
      params: body.params ?? {},
    });

    const sqs = getSqsClient();
    await sqs.send(
      new SendMessageCommand({
        QueueUrl: getSqsQueueUrl(),
        MessageBody: JSON.stringify({ teamId: ws.teamId, jobId }),
      }),
    );

    return NextResponse.json({ ok: true, jobId });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    const code =
      err instanceof Error && err.message.startsWith("Missing env ")
        ? "MISSING_AWS_CONFIG"
        : "BAD_REQUEST";
    return NextResponse.json({ ok: false, error: code }, { status });
  }
}
