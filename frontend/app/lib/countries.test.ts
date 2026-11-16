import { describe, expect, it } from "vitest";

import { countryName, flagUrl } from "./countries";

describe("flagUrl", () => {
  it("finds a flag by its IOC code, not its ISO one", () => {
    expect(flagUrl("GER")).toMatch(/\/de\.svg/);
    expect(flagUrl("SUI")).toMatch(/\/ch\.svg/);
    expect(flagUrl("KOS")).toMatch(/\/xk\.svg/);
  });

  it("has no flag for neutral athletes, Chinese Taipei or an unknown code", () => {
    expect(flagUrl("AIN1")).toBeUndefined();
    expect(flagUrl("TPE")).toBeUndefined();
    expect(flagUrl("XYZ")).toBeUndefined();
    expect(countryName("TPE")).toBe("Chinese Taipei");
  });
});
