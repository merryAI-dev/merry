/** @vitest-environment jsdom */
import * as React from "react";

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { useParamsMock } = vi.hoisted(() => ({
  useParamsMock: vi.fn(),
}));

vi.mock("next/navigation", async () => {
  const actual = await vi.importActual<typeof import("next/navigation")>("next/navigation");
  return {
    ...actual,
    useParams: useParamsMock,
  };
});

import ReportSessionPage from "./page";

describe("ReportSessionPage", () => {
  beforeEach(() => {
    useParamsMock.mockReset();
    useParamsMock.mockReturnValue({ slug: "missing" });
    Element.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
        if (url === "/api/review/report_missing/meta" || url === "/api/review/report_missing/messages") {
          return new Response(JSON.stringify({ error: "NOT_FOUND" }), {
            status: 404,
            headers: { "content-type": "application/json" },
          });
        }
        throw new Error(`unexpected fetch: ${url}`);
      }),
    );
  });

  it("blocks the interactive review surface when the session does not exist", async () => {
    render(React.createElement(ReportSessionPage));

    await waitFor(() => {
      expect(screen.getByText("세션을 찾을 수 없습니다")).not.toBeNull();
    });

    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.getByRole("link", { name: "세션 목록으로" }).getAttribute("href")).toBe("/review");
  });
});
