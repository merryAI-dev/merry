import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { sendMock } = vi.hoisted(() => ({
  sendMock: vi.fn(),
}));

vi.mock("@/lib/aws/ddb", () => ({
  getDdbDocClient: () => ({ send: sendMock }),
}));

import {
  createDiagnosisSession,
  getDiagnosisContextDocumentContent,
  getDiagnosisSessionDetail,
  listDiagnosisHistory,
  listDiagnosisSessions,
  recordDiagnosisContextDocument,
} from "./diagnosisSessionStore";

const ENV_KEYS = ["MERRY_DDB_TABLE", "MERRY_DIAGNOSIS_DDB_TABLE"] as const;

let originalEnv: Partial<Record<(typeof ENV_KEYS)[number], string | undefined>> = {};

beforeEach(() => {
  originalEnv = {};
  for (const key of ENV_KEYS) {
    originalEnv[key] = process.env[key];
  }

  process.env.MERRY_DDB_TABLE = "merry-main";
  process.env.MERRY_DIAGNOSIS_DDB_TABLE = "merry-diagnosis";
  sendMock.mockReset();
  sendMock.mockResolvedValue({});
});

afterEach(() => {
  for (const key of ENV_KEYS) {
    const value = originalEnv[key];
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
});

describe("diagnosisSessionStore diagnosis table routing", () => {
  it("uses MERRY_DIAGNOSIS_DDB_TABLE for session writes and reads", async () => {
    sendMock
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({
        Items: [
          {
            session_id: "diag_1",
            title: "비비비당 진단",
            status: "processing",
            created_by: "kim",
            created_at: "2026-04-09T00:00:00.000Z",
            updated_at: "2026-04-09T00:00:10.000Z",
            original_file_name: "bbb.xlsx",
            legacy_job_id: "job-1",
            latest_run_id: "run-1",
          },
        ],
      });

    await createDiagnosisSession({
      teamId: "team-1",
      title: "비비비당 진단",
      createdBy: "kim",
      originalFileName: "bbb.xlsx",
    });
    await listDiagnosisSessions("team-1", 20);

    expect(sendMock).toHaveBeenCalled();
    for (const call of sendMock.mock.calls) {
      expect(call[0].input.TableName).toBe("merry-diagnosis");
      expect(call[0].input.TableName).not.toBe("merry-main");
    }
  });

  it("assembles detail and history records from the diagnosis table", async () => {
    sendMock
      .mockResolvedValueOnce({
        Item: {
          session_id: "diag_1",
          title: "비비비당 진단",
          status: "ready",
          created_by: "kim",
          created_at: "2026-04-09T00:00:00.000Z",
          updated_at: "2026-04-09T00:10:00.000Z",
          original_file_name: "bbb.xlsx",
          latest_run_id: "run-1",
          legacy_job_id: "job-1",
          latest_artifact_count: 1,
        },
      })
      .mockResolvedValueOnce({
        Items: [
          {
            entity: "diagnosis_upload",
            upload_id: "upload-1",
            file_id: "file-1",
            original_name: "bbb.xlsx",
            content_type: "application/vnd.ms-excel",
            created_at: "2026-04-09T00:00:00.000Z",
          },
          {
            entity: "diagnosis_run",
            run_id: "run-1",
            legacy_job_id: "job-1",
            status: "succeeded",
            created_at: "2026-04-09T00:00:01.000Z",
            updated_at: "2026-04-09T00:10:00.000Z",
          },
          {
            entity: "diagnosis_event",
            event_id: "event-1",
            type: "run_succeeded",
            actor: "kim",
            created_at: "2026-04-09T00:10:00.000Z",
            description: "진단 실행이 완료되었습니다.",
          },
        ],
      })
      .mockResolvedValueOnce({
        Items: [
          {
            event_id: "event-1",
            session_id: "diag_1",
            session_title: "비비비당 진단",
            type: "run_succeeded",
            actor: "kim",
            created_at: "2026-04-09T00:10:00.000Z",
            description: "진단 실행이 완료되었습니다.",
          },
        ],
      });

    const detail = await getDiagnosisSessionDetail("team-1", "diag_1");
    const history = await listDiagnosisHistory("team-1", 10);

    expect(detail?.sessionId).toBe("diag_1");
    expect(detail?.uploads).toHaveLength(1);
    expect(detail?.runs[0]?.legacyJobId).toBe("job-1");
    expect(detail?.events[0]?.type).toBe("run_succeeded");
    expect(history[0]?.sessionTitle).toBe("비비비당 진단");
  });

  it("stores context documents in chunk items and reassembles the content", async () => {
    const table = new Map<string, Record<string, unknown>>();
    sendMock.mockImplementation(async (command: { constructor: { name: string }; input: Record<string, unknown> }) => {
      const { input } = command;

      if (command.constructor.name === "PutCommand") {
        const item = input.Item as Record<string, unknown>;
        table.set(`${item.pk}::${item.sk}`, structuredClone(item));
        return {};
      }

      if (command.constructor.name === "GetCommand") {
        const key = input.Key as Record<string, unknown>;
        return { Item: table.get(`${key.pk}::${key.sk}`) ?? null };
      }

      if (command.constructor.name === "QueryCommand") {
        const pk = (input.ExpressionAttributeValues as Record<string, unknown>)?.[":pk"];
        const descending = input.ScanIndexForward === false;
        const items = [...table.values()]
          .filter((item) => item.pk === pk)
          .sort((a, b) => String(a.sk).localeCompare(String(b.sk)));
        if (descending) items.reverse();
        return { Items: items };
      }

      return {};
    });

    const session = await createDiagnosisSession({
      teamId: "team-1",
      title: "비비비당 진단",
      createdBy: "kim",
      originalFileName: "bbb.xlsx",
    });

    const markdown = `# 보조 문서\n\n${"시장 개요 ".repeat(30_000)}`;
    const plainText = `시장 개요 ${"확장 ".repeat(30_000)}`;

    const stored = await recordDiagnosisContextDocument({
      teamId: "team-1",
      sessionId: session.sessionId,
      actor: "kim",
      file: {
        fileId: "file-ctx-1",
        originalName: "deck.pdf",
        contentType: "application/pdf",
        s3Bucket: "bucket",
        s3Key: "uploads/team/deck.pdf",
        createdAt: "2026-04-09T00:00:00.000Z",
      },
      normalized: {
        role: "context",
        sourceFormat: "pdf",
        markdown,
        plainText,
        warnings: [],
        metadata: { pageCount: 12 },
      },
    });

    const detail = await getDiagnosisSessionDetail("team-1", session.sessionId);
    const content = await getDiagnosisContextDocumentContent("team-1", session.sessionId, stored.documentId);

    expect(stored.markdownChunkCount).toBeGreaterThan(1);
    expect(detail?.contextDocuments).toHaveLength(1);
    expect(detail?.contextDocuments[0]).toMatchObject({
      documentId: stored.documentId,
      sourceFormat: "pdf",
      role: "context",
      originalName: "deck.pdf",
    });
    expect(content?.markdown).toBe(markdown);
    expect(content?.plainText).toBe(plainText);
  });
});
