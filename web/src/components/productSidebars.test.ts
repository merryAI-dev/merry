/** @vitest-environment jsdom */
import * as React from "react";

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { routerReplace, requestLogoutMock } = vi.hoisted(() => ({
  routerReplace: vi.fn(),
  requestLogoutMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/report",
  useRouter: () => ({ replace: routerReplace }),
}));

vi.mock("@/lib/logoutClient", () => ({
  requestLogout: requestLogoutMock,
}));

import { DiagnosisSidebar } from "./diagnosis/DiagnosisSidebar";
import { ReviewSidebar } from "./review/ReviewSidebar";

function createLocalStorageMock() {
  const store = new Map<string, string>();
  return {
    getItem: vi.fn((key: string) => store.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store.set(key, value);
    }),
    removeItem: vi.fn((key: string) => {
      store.delete(key);
    }),
    clear: vi.fn(() => {
      store.clear();
    }),
  };
}

describe("desktop product sidebars", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", createLocalStorageMock());
    routerReplace.mockReset();
    requestLogoutMock.mockReset();
  });

  it("shows an accessible collapsed logout failure indicator in the review sidebar", async () => {
    localStorage.setItem("merry-review-sidebar-collapsed", "true");
    requestLogoutMock.mockResolvedValue({ ok: false, error: "로그아웃에 실패했습니다." });

    render(
      React.createElement(ReviewSidebar, {
        workspace: { teamId: "review-team", memberName: "lee" },
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: "로그아웃" }));

    const indicator = await screen.findByRole("alert", { name: "로그아웃에 실패했습니다." });
    expect(indicator.getAttribute("title")).toBe("로그아웃에 실패했습니다.");
    expect(routerReplace).not.toHaveBeenCalled();
  });

  it("shows an accessible collapsed logout failure indicator in the diagnosis sidebar", async () => {
    localStorage.setItem("merry-diagnosis-sidebar-collapsed", "true");
    requestLogoutMock.mockResolvedValue({ ok: false, error: "로그아웃에 실패했습니다." });

    render(
      React.createElement(DiagnosisSidebar, {
        workspace: { teamId: "diagnosis-team", memberName: "kim" },
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: "로그아웃" }));

    const indicator = await screen.findByRole("alert", { name: "로그아웃에 실패했습니다." });
    expect(indicator.getAttribute("title")).toBe("로그아웃에 실패했습니다.");
    expect(routerReplace).not.toHaveBeenCalled();
  });
});
