import { describe, expect, it } from "vitest";
import { formatCurrency } from "./currency";

describe("formatCurrency", () => {
  it("keeps whole amounts compact", () => {
    expect(formatCurrency(1000, "GBP")).toBe("£1,000");
  });

  it("shows fractional amounts instead of rounding them to zero", () => {
    expect(formatCurrency(0.3, "GBP")).toBe("£0.30");
    expect(formatCurrency(1000.5, "GBP")).toBe("£1,000.50");
  });
});
