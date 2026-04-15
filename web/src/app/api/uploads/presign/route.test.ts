import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  requireWorkspaceFromCookiesMock,
  getSignedUrlMock,
  putUploadFileMock,
} = vi.hoisted(() => ({
  requireWorkspaceFromCookiesMock: vi.fn(),
  getSignedUrlMock: vi.fn(),
  putUploadFileMock: vi.fn(),
}));

vi.mock("@/lib/workspaceServer", () => ({
  requireWorkspaceFromCookies: requireWorkspaceFromCookiesMock,
}));

vi.mock("@aws-sdk/s3-request-presigner", () => ({
  getSignedUrl: getSignedUrlMock,
}));

vi.mock("@/lib/jobStore", () => ({
  putUploadFile: putUploadFileMock,
}));

vi.mock("@/lib/aws/s3", () => ({
  getS3Client: () => ({}),
}));

vi.mock("@/lib/aws/env", async () => {
  const actual = await vi.importActual<typeof import("@/lib/aws/env")>("@/lib/aws/env");
  return {
    ...actual,
    getS3BucketName: () => "bucket",
    getDdbTableName: () => "merry-main",
  };
});

import { POST } from "./route";

describe("uploads presign route", () => {
  beforeEach(() => {
    requireWorkspaceFromCookiesMock.mockReset();
    getSignedUrlMock.mockReset();
    putUploadFileMock.mockReset();

    requireWorkspaceFromCookiesMock.mockResolvedValue({ teamId: "team-1", memberName: "kim" });
    getSignedUrlMock.mockResolvedValue("https://example.com/upload");
    putUploadFileMock.mockResolvedValue(undefined);
  });

  it("accepts pptx uploads for diagnosis support documents", async () => {
    const response = await POST(new Request("http://localhost/api/uploads/presign", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        filename: "briefing.pptx",
        contentType: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        sizeBytes: 1024,
      }),
    }));
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.ok).toBe(true);
    expect(putUploadFileMock).toHaveBeenCalled();
  });
});
