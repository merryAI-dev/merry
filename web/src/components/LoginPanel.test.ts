import { describe, expect, it } from "vitest";

import { LOGIN_AFTER_LOGIN_PATH } from "./LoginPanel";

describe("LoginPanel", () => {
  it("routes fresh logins to the shared product chooser", () => {
    expect(LOGIN_AFTER_LOGIN_PATH).toBe("/products");
  });
});
