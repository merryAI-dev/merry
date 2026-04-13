import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  getUploadFileMock,
  createJobMock,
  getSqsClientMock,
  createDiagnosisSessionMock,
  recordDiagnosisUploadMock,
  createDiagnosisRunMock,
} = vi.hoisted(() => ({
  getUploadFileMock: vi.fn(),
  createJobMock: vi.fn(),
  getSqsClientMock: vi.fn(),
  createDiagnosisSessionMock: vi.fn(),
  recordDiagnosisUploadMock: vi.fn(),
  createDiagnosisRunMock: vi.fn(),
}));

vi.mock("@/lib/jobStore", () => ({
  getUploadFile: getUploadFileMock,
  createJob: createJobMock,
}));

const sqsSendMock = vi.fn();

vi.mock("@/lib/aws/sqs", () => ({
  getSqsClient: () => ({ send: sqsSendMock }),
}));

vi.mock("@/lib/aws/env", async () => {
  const actual = await vi.importActual<typeof import("@/lib/aws/env")>("@/lib/aws/env");
  return {
    ...actual,
    getSqsQueueUrl: () => "https://example.com/queue",
  };
});

vi.mock("@/lib/diagnosisSessionStore", () => ({
  createDiagnosisSession: createDiagnosisSessionMock,
  recordDiagnosisUpload: recordDiagnosisUploadMock,
  createDiagnosisRun: createDiagnosisRunMock,
}));

import { startDiagnosisFromUploadedFile } from "./diagnosisWorkflows";

describe("diagnosis workflow adapter", () => {
  beforeEach(() => {
    getUploadFileMock.mockReset();
    createJobMock.mockReset();
    createDiagnosisSessionMock.mockReset();
    recordDiagnosisUploadMock.mockReset();
    createDiagnosisRunMock.mockReset();
    sqsSendMock.mockReset();

    getUploadFileMock.mockResolvedValue({
      fileId: "file-1",
      teamId: "team-1",
      status: "uploaded",
      originalName: "bbb.xlsx",
      contentType: "application/vnd.ms-excel",
      sizeBytes: 1234,
      s3Bucket: "bucket",
      s3Key: "uploads/team-1/file-1.xlsx",
      createdBy: "kim",
      createdAt: "2026-04-09T00:00:00.000Z",
      uploadedAt: "2026-04-09T00:00:10.000Z",
    });
    createDiagnosisSessionMock.mockResolvedValue({
      sessionId: "diag_1",
      title: "bbb.xlsx",
      status: "uploaded",
      createdAt: "2026-04-09T00:00:00.000Z",
      updatedAt: "2026-04-09T00:00:00.000Z",
      createdBy: "kim",
      originalFileName: "bbb.xlsx",
      latestRunId: null,
      legacyJobId: null,
      latestArtifactCount: 0,
    });
    recordDiagnosisUploadMock.mockResolvedValue({
      uploadId: "upload-1",
      sessionId: "diag_1",
      fileId: "file-1",
      originalName: "bbb.xlsx",
      contentType: "application/vnd.ms-excel",
      createdAt: "2026-04-09T00:00:00.000Z",
      uploadedAt: "2026-04-09T00:00:10.000Z",
      s3Bucket: "bucket",
      s3Key: "uploads/team-1/file-1.xlsx",
      sizeBytes: 1234,
    });
    createDiagnosisRunMock.mockResolvedValue({
      runId: "run-1",
      sessionId: "diag_1",
      legacyJobId: "job-1",
      status: "queued",
      createdAt: "2026-04-09T00:00:11.000Z",
      updatedAt: "2026-04-09T00:00:11.000Z",
    });
  });

  it("creates diagnosis metadata and enqueues the legacy diagnosis job", async () => {
    const result = await startDiagnosisFromUploadedFile({
      teamId: "team-1",
      memberName: "kim",
      fileId: "file-1",
    });

    expect(createDiagnosisSessionMock).toHaveBeenCalledWith(
      expect.objectContaining({
        teamId: "team-1",
        createdBy: "kim",
        originalFileName: "bbb.xlsx",
      }),
    );
    expect(createJobMock).toHaveBeenCalledWith(
      expect.objectContaining({
        teamId: "team-1",
        type: "diagnosis_analysis",
        inputFileIds: ["file-1"],
        params: expect.objectContaining({ diagnosisSessionId: "diag_1" }),
      }),
    );
    expect(sqsSendMock).toHaveBeenCalledTimes(1);
    expect(createDiagnosisRunMock).toHaveBeenCalledWith(
      expect.objectContaining({
        teamId: "team-1",
        sessionId: "diag_1",
        status: "queued",
      }),
    );
    expect(result.session.sessionId).toBe("diag_1");
    expect(result.run.runId).toBe("run-1");
  });

  it("rejects files that are not fully uploaded", async () => {
    getUploadFileMock.mockResolvedValueOnce({
      fileId: "file-2",
      teamId: "team-1",
      status: "presigned",
    });

    await expect(
      startDiagnosisFromUploadedFile({
        teamId: "team-1",
        memberName: "kim",
        fileId: "file-2",
      }),
    ).rejects.toThrow("FILE_NOT_UPLOADED");
  });
});
