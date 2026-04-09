/** @vitest-environment jsdom */
import * as React from "react";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ReportError from "./error";

describe("ReportError", () => {
  it("keeps the list recovery link inside the staged review shell", () => {
    render(
      React.createElement(ReportError, {
        error: new Error("boom"),
        reset: () => undefined,
      }),
    );

    const link = screen.getByRole("link", { name: "목록으로" });
    expect(link.getAttribute("href")).toBe("/review");
    expect(screen.getByText("리포트를 불러올 수 없습니다")).not.toBeNull();
  });
});
