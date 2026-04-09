import { describe, expect, it, vi } from "vitest";

import { requestLogout } from "./logoutClient";

describe("requestLogout", () => {
  it("returns success only when the logout response is ok", async () => {
    const result = await requestLogout(
      vi.fn().mockResolvedValue({ ok: true }) as unknown as typeof fetch,
    );

    expect(result).toEqual({ ok: true });
  });

  it("returns a minimal failure message when the logout response fails", async () => {
    const result = await requestLogout(
      vi.fn().mockResolvedValue({ ok: false }) as unknown as typeof fetch,
    );

    expect(result).toEqual({ ok: false, error: "로그아웃에 실패했습니다." });
  });

  it("returns a minimal failure message when the logout request throws", async () => {
    const result = await requestLogout(
      vi.fn().mockRejectedValue(new Error("network")) as unknown as typeof fetch,
    );

    expect(result).toEqual({ ok: false, error: "로그아웃에 실패했습니다." });
  });
});
