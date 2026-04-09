import { describe, expect, it } from "vitest";

import {
  DEFAULT_AFTER_LOGIN_PATH,
  PRODUCTS,
  getProductBySlug,
  productNavLabel,
} from "./products";

describe("products", () => {
  it("defines only review and diagnosis as top-level products", () => {
    expect(PRODUCTS.map((product) => product.slug)).toEqual(["review", "diagnosis"]);
    expect(PRODUCTS.map((product) => product.href)).toEqual(["/review", "/diagnosis"]);
  });

  it("routes authenticated users to the product chooser", () => {
    expect(DEFAULT_AFTER_LOGIN_PATH).toBe("/products");
  });

  it("returns Korean labels for the chooser cards", () => {
    expect(productNavLabel("review")).toBe("투자심사");
    expect(productNavLabel("diagnosis")).toBe("현황진단");
  });

  it("throws on unknown product slugs", () => {
    expect(() => getProductBySlug("analysis")).toThrow(/Unknown product/);
  });
});
