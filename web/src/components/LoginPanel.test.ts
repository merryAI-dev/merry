import { describe, expect, it, vi } from "vitest";

import { DEFAULT_AFTER_LOGIN_PATH } from "@/lib/products";

import { applyLoginRedirect, getGoogleSignInOptions, getLoginRedirectPath } from "./LoginPanel";

describe("LoginPanel", () => {
  it("routes fresh logins to the shared product chooser", () => {
    const router = { replace: vi.fn() };

    applyLoginRedirect(router);

    expect(router.replace).toHaveBeenCalledWith(DEFAULT_AFTER_LOGIN_PATH);
  });

  it("passes the chooser path to Google sign-in", () => {
    expect(getGoogleSignInOptions()).toEqual({ callbackUrl: DEFAULT_AFTER_LOGIN_PATH });
  });

  it("keeps the redirect path sourced from the shared constant", () => {
    expect(getLoginRedirectPath()).toBe(DEFAULT_AFTER_LOGIN_PATH);
  });
});
