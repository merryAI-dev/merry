import { describe, expect, it, vi } from "vitest";
import * as React from "react";

import { DEFAULT_AFTER_LOGIN_PATH } from "@/lib/products";

const { redirectMock, getWorkspaceFromCookiesMock, LoginPanelMock } = vi.hoisted(() => ({
  redirectMock: vi.fn(),
  getWorkspaceFromCookiesMock: vi.fn(),
  LoginPanelMock: vi.fn(() => null),
}));

vi.mock("next/navigation", () => ({
  redirect: redirectMock,
}));

vi.mock("@/components/LoginPanel", () => ({
  LoginPanel: LoginPanelMock,
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

  it("passes login props to the LoginPanel on the unauthenticated path", async () => {
    redirectMock.mockReset();
    getWorkspaceFromCookiesMock.mockReset();
    getWorkspaceFromCookiesMock.mockResolvedValue(null);

    const prevGoogleClientId = process.env.GOOGLE_CLIENT_ID;
    const prevGoogleClientSecret = process.env.GOOGLE_CLIENT_SECRET;
    process.env.GOOGLE_CLIENT_ID = "client-id";
    process.env.GOOGLE_CLIENT_SECRET = "client-secret";

    let tree: React.ReactNode = null;
    try {
      tree = await Home({ searchParams: Promise.resolve({ error: "OAuthCallback" }) });
    } finally {
      process.env.GOOGLE_CLIENT_ID = prevGoogleClientId;
      process.env.GOOGLE_CLIENT_SECRET = prevGoogleClientSecret;
    }

    expect(redirectMock).not.toHaveBeenCalled();
    const loginPanel = findElementByType(tree, LoginPanelMock);
    expect(loginPanel?.props).toMatchObject({ googleEnabled: true, errorCode: "OAuthCallback" });
  });
});

function findElementByType(node: React.ReactNode, type: unknown): React.ReactElement | null {
  if (node == null || typeof node === "boolean") return null;
  if (Array.isArray(node)) {
    for (const child of node) {
      const found = findElementByType(child, type);
      if (found) return found;
    }
    return null;
  }
  if (!React.isValidElement(node)) return null;
  if (node.type === type) return node;
  return findElementByType(node.props.children, type);
}
