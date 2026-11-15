import { describe, expect, it } from "vitest";
import { countryName } from "./countries";
import { formatDateRange, formatScore, formatSessionDate, formatValue } from "./format";
import { sessionLabel } from "./labels";

describe("formatScore", () => {
  it("prints three decimals", () => {
    expect(formatScore(14.566)).toBe("14.566");
    expect(formatScore(14)).toBe("14.000");
    expect(formatScore(null)).toBe("");
  });
});

describe("formatValue", () => {
  it("prints as few decimals as needed", () => {
    expect(formatValue(6.3)).toBe("6.3");
    expect(formatValue(6)).toBe("6.0");
    expect(formatValue(0.05)).toBe("0.05");
    expect(formatValue(null)).toBe("");
  });
});

describe("dates", () => {
  it("formats a range and a day without shifting time zones", () => {
    // Intl sets the dash between thin spaces
    expect(formatDateRange("2026-10-17", "2026-10-25")).toBe("17\u2009–\u200925 Oct 2026");
    expect(formatSessionDate("2026-10-17")).toBe("Sat 17 Oct");
  });
});

describe("sessionLabel", () => {
  it("names sessions as a results book heads them", () => {
    expect(sessionLabel({ round: "QUAL", apparatus: null, part: null })).toBe("Qualification");
    expect(sessionLabel({ round: "QUAL", apparatus: "VT", part: null })).toBe("Vault Qualification");
    expect(sessionLabel({ round: "EVENT", apparatus: "BB", part: null })).toBe("Balance Beam Final");
    expect(sessionLabel({ round: "AA", apparatus: null, part: 2 })).toBe("All-Around Final, Part 2");
  });
});

describe("countryName", () => {
  it("names IOC codes, neutral codes, and falls back to the code", () => {
    expect(countryName("GER")).toBe("Germany");
    expect(countryName("AIN2")).toBe("Neutral Athletes");
    expect(countryName("WG1")).toBe("Neutral Athletes");
    expect(countryName("XYZ")).toBe("XYZ");
  });
});
