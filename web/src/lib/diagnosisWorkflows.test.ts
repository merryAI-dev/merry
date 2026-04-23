import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  getUploadFileMock,
  createDiagnosisSessionMock,
  recordDiagnosisUploadMock,
  saveDiagnosisConversationStartMock,
  markDiagnosisSessionStatusMock,
  materializeDiagnosisSourceFileMock,
  runDiagnosisAgentTurnMock,
} = vi.hoisted(() => ({
  getUploadFileMock: vi.fn(),
  createDiagnosisSessionMock: vi.fn(),
  recordDiagnosisUploadMock: vi.fn(),
  saveDiagnosisConversationStartMock: vi.fn(),
  markDiagnosisSessionStatusMock: vi.fn(),
  materializeDiagnosisSourceFileMock: vi.fn(),
  runDiagnosisAgentTurnMock: vi.fn(),
}));

vi.mock("@/lib/jobStore", () => ({
  getUploadFile: getUploadFileMock,
}));

vi.mock("@/lib/diagnosisSessionStore", () => ({
  createDiagnosisSession: createDiagnosisSessionMock,
  recordDiagnosisUpload: recordDiagnosisUploadMock,
  saveDiagnosisConversationStart: saveDiagnosisConversationStartMock,
  markDiagnosisSessionStatus: markDiagnosisSessionStatusMock,
}));

vi.mock("@/lib/diagnosisAgentBridge", () => ({
  materializeDiagnosisSourceFile: materializeDiagnosisSourceFileMock,
  runDiagnosisAgentTurn: runDiagnosisAgentTurnMock,
  buildDiagnosisStartPrompt: (path: string) => `start:${path}`,
  buildDiagnosisReplyPrompt: (path: string, content: string) => `reply:${path}:${content}`,
  buildDiagnosisGeneratePrompt: (path: string) => `generate:${path}`,
}));

import { startDiagnosisFromUploadedFile } from "./diagnosisWorkflows";

describe("diagnosis workflow adapter", () => {
  beforeEach(() => {
    getUploadFileMock.mockReset();
    createDiagnosisSessionMock.mockReset();
    recordDiagnosisUploadMock.mockReset();
    saveDiagnosisConversationStartMock.mockReset();
    markDiagnosisSessionStatusMock.mockReset();
    materializeDiagnosisSourceFileMock.mockReset();
    runDiagnosisAgentTurnMock.mockReset();

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
    materializeDiagnosisSourceFileMock.mockResolvedValue({
      localPath: "/Users/boram/merry/temp/diagnosis_team-1_diag_1/bbb.xlsx",
      fileId: "file-1",
      originalName: "bbb.xlsx",
      contentType: "application/vnd.ms-excel",
    });
    runDiagnosisAgentTurnMock.mockResolvedValue({
      assistantText: "초기 진단 요약입니다. 가장 먼저 고객 획득 채널을 확인하고 싶습니다.",
      analysisSummary: {
        companyName: "비비비당",
        gapCount: 3,
        sheets: ["기업정보", "현황진단", "(컨설턴트용) 분석보고서"],
        scoreCards: [{ category: "문제", score: 14.5, yesRatePct: 72.5 }],
        sampleGaps: [{ module: "사업화", question: "핵심 KPI가 정리돼 있나요?" }],
      },
    });
    saveDiagnosisConversationStartMock.mockResolvedValue({
      messageId: "diag_msg_1",
      sessionId: "diag_1",
      role: "assistant",
      content: "초기 진단 요약입니다. 가장 먼저 고객 획득 채널을 확인하고 싶습니다.",
      createdAt: "2026-04-09T00:00:12.000Z",
    });
  });

  it("creates diagnosis metadata and stores the first assistant question instead of enqueuing a legacy job", async () => {
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
    expect(materializeDiagnosisSourceFileMock).toHaveBeenCalledWith(
      expect.objectContaining({
        teamId: "team-1",
        sessionId: "diag_1",
        file: expect.objectContaining({
          fileId: "file-1",
        }),
      }),
    );
    expect(runDiagnosisAgentTurnMock).toHaveBeenCalledWith(
      expect.objectContaining({
        teamId: "team-1",
        sessionId: "diag_1",
        memberName: "kim",
        mode: "start",
      }),
    );
    expect(saveDiagnosisConversationStartMock).toHaveBeenCalledWith(
      expect.objectContaining({
        teamId: "team-1",
        sessionId: "diag_1",
        actor: "kim",
        assistantText: "초기 진단 요약입니다. 가장 먼저 고객 획득 채널을 확인하고 싶습니다.",
      }),
    );
    expect(markDiagnosisSessionStatusMock).toHaveBeenCalledWith(
      expect.objectContaining({
        teamId: "team-1",
        sessionId: "diag_1",
        status: "ready",
      }),
    );
    expect(result.session.sessionId).toBe("diag_1");
    expect(result.assistantMessage.content).toContain("고객 획득 채널");
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
