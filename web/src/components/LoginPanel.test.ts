import { describe, expect, it } from "vitest";

import { DEFAULT_AFTER_LOGIN_PATH } from "@/lib/products";

import { getGoogleSignInOptions, getLoginRedirectPath } from "./LoginPanel";

describe("LoginPanel", () => {
  it("routes fresh logins to the shared product chooser", () => {
    expect(getLoginRedirectPath()).toBe(DEFAULT_AFTER_LOGIN_PATH);
  });

  it("passes the chooser path to Google sign-in", () => {
    expect(getGoogleSignInOptions()).toEqual({ callbackUrl: DEFAULT_AFTER_LOGIN_PATH });
  });
});
