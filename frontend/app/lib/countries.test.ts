import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { countryName, flagUrl } from "./countries";

describe("flagUrl", () => {
  it("finds a flag by its IOC code, not its ISO one", () => {
    expect(flagUrl("GER")).toMatch(/\/de\.svg/);
    expect(flagUrl("SUI")).toMatch(/\/ch\.svg/);
    expect(flagUrl("KOS")).toMatch(/\/xk\.svg/);
    expect(flagUrl("TTO")).toMatch(/\/tt\.svg/);
    expect(flagUrl("URU")).toMatch(/\/uy\.svg/);
    expect(countryName("CAY")).toBe("Cayman Islands");
  });

  it("has no flag for neutral athletes, Chinese Taipei or an unknown code", () => {
    expect(flagUrl("AIN1")).toBeUndefined();
    expect(flagUrl("TPE")).toBeUndefined();
    expect(flagUrl("XYZ")).toBeUndefined();
    expect(countryName("TPE")).toBe("Chinese Taipei");
  });
});

// Every country in the imported results data, so that one new to the data fails here, not on the page
describe("countries in the results data", () => {
  const codes = nocCodesInData();

  it("finds the data", () => {
    expect(codes.length).toBeGreaterThan(0);
  });

  it("names every country", () => {
    expect(codes.filter((noc) => countryName(noc) === noc)).toEqual([]);
  });

  it("has a flag for every country but neutral athletes and Chinese Taipei", () => {
    const flagless = codes.filter((noc) => !flagUrl(noc) && noc !== "TPE" && !/^(AIN|WG)\d*$/.test(noc));
    expect(flagless).toEqual([]);
  });
});

/** The NOC codes in every PARTICIPANTS.csv under data/, next to frontend/ where the tests run. */
function nocCodesInData(): string[] {
  const dataDir = join(process.cwd(), "..", "data");
  const files = readdirSync(dataDir, { recursive: true, encoding: "utf8" }).filter((file) =>
    file.endsWith("-PARTICIPANTS.csv"),
  );
  const codes = new Set<string>();
  for (const file of files) {
    const [header, ...rows] = readFileSync(join(dataDir, file), "utf8").split(/\r?\n/).filter(Boolean);
    const column = csvFields(header).indexOf("NOC Code");
    for (const row of rows) {
      const noc = csvFields(row)[column]?.trim();
      if (noc) {
        codes.add(noc);
      }
    }
  }
  return [...codes].sort();
}

/** A CSV line's fields, allowing for quoted fields with commas in them. */
function csvFields(line: string): string[] {
  return [...line.matchAll(/(?:^|,)("(?:[^"]|"")*"|[^,]*)/g)].map(([, field]) =>
    field.startsWith('"') ? field.slice(1, -1).replaceAll('""', '"') : field,
  );
}
