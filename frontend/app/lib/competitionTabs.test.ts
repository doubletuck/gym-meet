import { describe, expect, it } from "vitest";

import type { RankingSummary } from "~/api/types";
import { competition, division } from "~/test/fixtures";
import { competitionTabs, memberFor, tabOf } from "./competitionTabs";

const finals = (["VT", "UB", "BB", "FX"] as const).map((apparatus, index) =>
  competition({
    slug: `${apparatus.toLowerCase()}-final`,
    name: `${apparatus} Final`,
    shortName: "Final",
    type: "C3",
    apparatus,
    date: index < 2 ? "2026-10-24" : "2026-10-25",
  }),
);

describe("competitionTabs", () => {
  it("makes a tab of each competition, and one of the apparatus finals", () => {
    const tabs = competitionTabs(
      division([
        competition({ slug: "qualification", name: "Qualification", date: "2026-10-18", endDate: "2026-10-19" }),
        competition({ slug: "team-final", name: "Team Final", type: "C4", date: "2026-10-21" }),
        competition({
          slug: "all-around-final",
          name: "All-Around Final",
          shortName: "AA Final",
          type: "C2",
          date: "2026-10-23",
        }),
        ...finals,
      ]),
    );

    expect(tabs.map((tab) => tab.label)).toEqual([
      "Qualification",
      "Team Final",
      "All-Around Final",
      "Apparatus Finals",
    ]);
    expect(tabs[0]).toMatchObject({ key: "qualification", date: "2026-10-18", endDate: "2026-10-19" });
    expect(tabs[3]).toMatchObject({ key: "C3-apparatus", date: "2026-10-24", endDate: "2026-10-25" });
    expect(tabs[3].members.map((member) => member.apparatus)).toEqual(["VT", "UB", "BB", "FX"]);
  });

  it("calls a Competition I named for its titles qualification", () => {
    const [tab] = competitionTabs(
      division([
        competition({
          slug: "qualification",
          name: "All-Around Final · Team and Apparatus Qualification",
          shortName: "Qualification",
        }),
      ]),
    );

    expect(tab.label).toBe("Qualification");
  });

  it("makes one tab of an apparatus-format meet's qualifications", () => {
    const tabs = competitionTabs(
      division([
        competition({
          slug: "vault-qualification",
          name: "Vault Qualification",
          shortName: "Qualification",
          apparatus: "VT",
        }),
        competition({
          slug: "beam-qualification",
          name: "Balance Beam Qualification",
          shortName: "Qualification",
          apparatus: "BB",
        }),
        ...finals,
      ]),
    );

    expect(tabs.map((tab) => [tab.label, tab.members.length])).toEqual([
      ["Qualification", 2],
      ["Apparatus Finals", 4],
    ]);
  });

  it("puts a mixed team's qualification first and its final's rounds in one tab", () => {
    const ranking: RankingSummary = {
      id: 1,
      slug: "qualification",
      name: "Qualification",
      discipline: "MIX",
      ageCategory: "JR",
      type: "TEAM",
      purpose: "QUALIFYING",
      date: "2026-11-07",
      endDate: "2026-11-08",
    };
    const rounds = [1, 2, 3].map((round) =>
      competition({
        slug: `team-final-round-${round}`,
        name: `Team Final, Round ${round}`,
        type: "C4",
        round,
        date: "2026-11-11",
      }),
    );

    const tabs = competitionTabs(division(rounds, [ranking], { discipline: "MIX", ageCategory: "JR" }));

    expect(tabs.map((tab) => tab.label)).toEqual(["Qualification", "Team Final"]);
    expect(tabs[1].members.map((member) => member.label)).toEqual(["Round 1", "Round 2", "Round 3"]);
    expect(tabs[1].endDate).toBeNull();
  });

  it("puts a split competition's combined row beside its parts", () => {
    const name = "All-Around and Apparatus Final";
    const [tab] = competitionTabs(
      division([
        competition({ slug: "all-around-and-apparatus-final", name, shortName: "Final", endDate: "2026-08-09" }),
        competition({
          slug: "all-around-and-apparatus-final-part-1",
          name: `${name}, Part 1`,
          part: 1,
          date: "2026-08-07",
        }),
        competition({
          slug: "all-around-and-apparatus-final-part-2",
          name: `${name}, Part 2`,
          part: 2,
          date: "2026-08-09",
        }),
      ]),
    );

    expect(tab.label).toBe(name);
    expect(tab.members.map((member) => member.label)).toEqual(["Combined", "Part 1", "Part 2"]);
  });
});

describe("tabOf and memberFor", () => {
  const tabs = competitionTabs(division([competition({ slug: "qualification", name: "Qualification" }), ...finals]));

  it("finds the tab holding a competition", () => {
    expect(tabOf(tabs, "bb-final")?.label).toBe("Apparatus Finals");
    expect(tabOf(tabs, "nothing")).toBeUndefined();
  });

  it("opens a tab on the apparatus being viewed, else its first", () => {
    expect(memberFor(tabs[1], "BB").slug).toBe("bb-final");
    expect(memberFor(tabs[1], "teams").slug).toBe("vt-final");
    expect(memberFor(tabs[0], "BB").slug).toBe("qualification");
  });
});
