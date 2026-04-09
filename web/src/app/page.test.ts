import { describe, expect, it, vi } from "vitest";
import * as React from "react";

import { DEFAULT_AFTER_LOGIN_PATH } from "@/lib/products";

const { redirectMock, getWorkspaceFromCookiesMock } = vi.hoisted(() => ({
  redirectMock: vi.fn(),
  getWorkspaceFromCookiesMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  redirect: redirectMock,
}));

vi.mock("@/lib/workspaceServer", () => ({
  getWorkspaceFromCookies: getWorkspaceFromCookiesMock,
}));

const { default: Home } = await import("./page.tsx");

describe("Home", () => {
  it("redirects authenticated users to the shared product chooser", async () => {
    redirectMock.mockReset();
    getWorkspaceFromCookiesMock.mockReset();
    getWorkspaceFromCookiesMock.mockResolvedValue({ teamId: "team_1", memberName: "lee" });

    await Home({});

    expect(redirectMock).toHaveBeenCalledTimes(1);
    expect(redirectMock).toHaveBeenCalledWith(DEFAULT_AFTER_LOGIN_PATH);
  });
});
