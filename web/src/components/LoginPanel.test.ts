/** @vitest-environment jsdom */
import * as React from "react";

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { routerReplace, signInMock } = vi.hoisted(() => ({
  routerReplace: vi.fn(),
  signInMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: routerReplace }),
}));

vi.mock("next-auth/react", () => ({
  signIn: signInMock,
}));

import { LoginPanel } from "./LoginPanel";

describe("LoginPanel", () => {
  beforeEach(() => {
    routerReplace.mockReset();
    signInMock.mockReset();
    vi.stubGlobal("fetch", vi.fn());
  });

  it("calls Google sign-in with the chooser callback url", () => {
    render(React.createElement(LoginPanel, { googleEnabled: true, errorCode: "" }));

    fireEvent.click(screen.getByRole("button", { name: "Google로 로그인" }));

    expect(signInMock).toHaveBeenCalledWith("google", { callbackUrl: "/products" });
  });

  it("redirects successful passcode login to the chooser path", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ ok: true }),
      }),
    );

    render(React.createElement(LoginPanel, { googleEnabled: false, errorCode: "" }));

    fireEvent.change(screen.getByPlaceholderText("이름 또는 닉네임"), { target: { value: "홍길동" } });
    fireEvent.change(screen.getByPlaceholderText("워크스페이스 코드"), { target: { value: "1234" } });
    fireEvent.click(screen.getByRole("button", { name: "워크스페이스 들어가기" }));

    await waitFor(() => {
      expect(routerReplace).toHaveBeenCalledWith("/products");
    });
  });
});
