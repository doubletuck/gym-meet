import { describe, expect, it } from "vitest";
import { countryName } from "./countries";
import { formatDate, formatDateRange, formatScore, formatCompetitionDate, formatValue } from "./format";

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
    expect(formatDate("2006-12-30")).toBe("30 Dec 2006");
    expect(formatCompetitionDate("2026-10-17")).toBe("Sat 17 Oct");
    expect(formatCompetitionDate("2026-08-06", "2026-08-08")).toBe("Thu 6 Aug\u2009–\u2009Sat 8 Aug");
  });
});

describe("countryName", () => {
  it("names IOC codes, neutral codes, and falls back to the code", () => {
    expect(countryName("GER")).toBe("Germany");
    expect(countryName("WG1")).toBe("World Gymnastics 1");
    expect(countryName("WG2")).toBe("World Gymnastics 2");
    expect(countryName("AIN2")).toBe("Individual Neutral Athletes (AIN2)");
    expect(countryName("XYZ")).toBe("XYZ");
  });
});
