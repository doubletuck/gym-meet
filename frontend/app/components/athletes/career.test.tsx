import { render as renderInPage, screen, within } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import type {
  Apparatus,
  ApparatusScore,
  AthleteDetail,
  AthleteEntry,
  CompetitionSummary,
  CompetitionType,
  EntryCompetition,
  Routine,
} from "~/api/types";
import { APPARATUS_LABELS } from "~/lib/labels";
import { CareerResults, PersonalBests } from "./career";

const render = (ui: ReactElement) => renderInPage(<MemoryRouter>{ui}</MemoryRouter>);

const worlds = {
  slug: "2026-world-championships",
  title: "54th Artistic Gymnastics World Championships",
  shortName: "Worlds 2026",
  startDate: "2026-10-17",
  endDate: "2026-10-25",
};

const NAMES: Record<CompetitionType, [name: string, shortName: string]> = {
  C1: ["Qualification", "Qualification"],
  C2: ["All-Around Final", "AA Final"],
  C3: ["Final", "Final"],
  C4: ["Team Final", "Team Final"],
};

// What each kind of competition's rankings are for at a championship like Worlds
const PURPOSES: Record<CompetitionType, CompetitionSummary["purposes"]> = {
  C1: { team: "QUALIFYING", allAround: "QUALIFYING", apparatus: "QUALIFYING" },
  C2: { team: null, allAround: "FINAL", apparatus: "INFORMATIONAL" },
  C3: { team: null, allAround: null, apparatus: "FINAL" },
  C4: { team: "FINAL", allAround: null, apparatus: "INFORMATIONAL" },
};

function competition(
  slug: string,
  type: CompetitionType,
  apparatus: Apparatus | null = null,
  overrides: Partial<CompetitionSummary> = {},
): CompetitionSummary {
  const [name, shortName] =
    type === "C3" && apparatus ? [`${APPARATUS_LABELS[apparatus]} Final`, "Final"] : NAMES[type];
  return {
    id: slug.length * 10 + (apparatus?.length ?? 0) + Number(type[1]),
    slug,
    name,
    shortName,
    discipline: "WAG",
    ageCategory: "SR",
    type,
    apparatus,
    round: null,
    part: null,
    purposes: PURPOSES[type],
    date: "2026-10-18",
    endDate: null,
    ...overrides,
  };
}

function routine(difficulty: number, execution: number, score: number): Routine {
  return {
    status: "COMPLETED",
    difficulty,
    difficultyInquiry: false,
    execution,
    bonus: null,
    bonusDetail: null,
    penalty: null,
    sjPenalty: null,
    score,
  };
}

describe("PersonalBests", () => {
  function athlete(overrides: Partial<AthleteDetail>): AthleteDetail {
    return {
      id: 7,
      surname: "Nemour",
      givenName: "Kaylia",
      discipline: "WAG",
      birthYear: 2006,
      birthDate: null,
      otherNames: [],
      personalBests: [],
      allAroundBest: null,
      entries: [],
      ...overrides,
    };
  }

  it("shows a tile for each apparatus and the all-around, linking to the athlete's row in the results", () => {
    render(
      <PersonalBests
        athlete={athlete({
          personalBests: [
            {
              apparatus: "UB",
              score: 15.333,
              routine: routine(7.0, 8.333, 15.333),
              vault: null,
              event: worlds,
              competition: competition("uneven-bars-final", "C3", "UB"),
            },
          ],
          allAroundBest: { total: 55.999, event: worlds, competition: competition("qualification", "C1") },
        })}
      />,
    );

    const [bars, allAround] = screen.getAllByRole("link");
    expect(bars).toHaveTextContent(/Uneven Bars/);
    expect(bars).toHaveTextContent("15.333");
    expect(bars).toHaveTextContent("D 7.0E 8.333");
    expect(bars).toHaveTextContent("Worlds 2026Final");
    expect(bars).toHaveAttribute("href", "/events/2026-world-championships/wag/sr/uneven-bars-final?view=UB&athlete=7");
    expect(allAround).toHaveTextContent("55.999");
    expect(allAround).toHaveTextContent("Worlds 2026Qualification");
    expect(allAround).toHaveAttribute(
      "href",
      "/events/2026-world-championships/wag/sr/qualification?view=all-around&athlete=7",
    );
  });

  it("shows bonus and penalties only where there are any, so the breakdown adds up", () => {
    render(
      <PersonalBests
        athlete={athlete({
          personalBests: [
            {
              apparatus: "FX",
              score: 12.9,
              routine: { ...routine(5.3, 7.9, 12.9), bonus: 0, penalty: -0.3 },
              vault: null,
              event: worlds,
              competition: competition("qualification", "C1"),
            },
          ],
        })}
      />,
    );

    const floor = screen.getByRole("link");
    expect(floor).toHaveTextContent("D 5.3E 7.900P -0.3");
    expect(floor).not.toHaveTextContent(/\bB\b|SJ/);
  });

  it("names the vault, and opens a championship qualification's second vault in the vault final ranking", () => {
    render(
      <PersonalBests
        athlete={athlete({
          personalBests: [
            {
              apparatus: "VT",
              score: 14.4,
              routine: routine(5.2, 9.2, 14.4),
              vault: 2,
              event: worlds,
              competition: competition("qualification", "C1"),
            },
          ],
        })}
      />,
    );

    const vault = screen.getByRole("link");
    expect(vault).toHaveTextContent(/Vault 2/);
    expect(vault).toHaveAttribute(
      "href",
      "/events/2026-world-championships/wag/sr/qualification?view=VT-final&athlete=7",
    );
  });
});

describe("CareerResults", () => {
  function athlete(entries: AthleteEntry[]): AthleteDetail {
    return {
      id: 7,
      surname: "Yeo",
      givenName: "Seojeong",
      discipline: "WAG",
      birthYear: 2002,
      birthDate: null,
      otherNames: [],
      personalBests: [],
      allAroundBest: null,
      entries,
    };
  }

  function score(apparatus: Apparatus, overrides: Partial<ApparatusScore> = {}): ApparatusScore {
    return {
      apparatus,
      rank: null,
      routine: routine(5.4, 8.5, 13.9),
      secondRoutine: null,
      combinedBonus: null,
      total: 13.9,
      qualificationRank: null,
      qualification: null,
      ...overrides,
    };
  }

  function entry(competitions: EntryCompetition[], overrides: Partial<AthleteEntry> = {}): AthleteEntry {
    return {
      event: worlds,
      noc: "KOR",
      club: null,
      entryStatus: "COMPETITOR",
      competitions,
      mixedTeam: null,
      ...overrides,
    };
  }

  const row = (name: RegExp) => screen.getByRole("row", { name });
  const roundHeaders = () =>
    screen.getAllByRole("columnheader").filter((header) => header.getAttribute("scope") === "colgroup");
  const columnHeaders = () =>
    within(screen.getAllByRole("rowgroup")[0])
      .getAllByRole("columnheader")
      .map((header) => header.textContent);

  it("shows a vault result over its two vaults, and the all-around as the last row", () => {
    render(
      <CareerResults
        athlete={athlete([
          entry([
            {
              competition: competition("qualification", "C1"),
              allAround: { rank: 3, rankStatus: "RANKED", total: 55.1, qualification: "Q", purpose: "QUALIFYING" },
              team: null,
              scores: [
                score("VT", {
                  rank: 1,
                  routine: routine(5.4, 9.166, 14.566),
                  secondRoutine: routine(5.0, 9.0, 14.0),
                  total: 14.283,
                  qualificationRank: 2,
                  qualification: "Q",
                }),
              ],
              apparatusStandings: [],
            },
          ]),
        ])}
      />,
    );

    expect(screen.getByRole("link", { name: "Qualification" })).toHaveAttribute(
      "href",
      "/events/2026-world-championships/wag/sr/qualification",
    );
    const rows = screen.getAllByRole("row").map((tableRow) => tableRow.textContent);
    // The header, the round, then the vault result, each vault, and the all-around
    expect(rows.slice(2)).toEqual([
      "VTVault result14.2832Q",
      "VT1Vault 15.49.16614.5661",
      "VT2Vault 25.09.00014.000",
      "AAAll-Around55.1003Q",
    ]);
    expect(within(row(/Vault result/)).getByRole("link")).toHaveAttribute(
      "href",
      "/events/2026-world-championships/wag/sr/qualification?view=VT-final&athlete=7",
    );
    expect(screen.queryByText(/#/)).not.toBeInTheDocument();
  });

  it("puts a World Cup's qualifications in one round and its finals in another, with medals in the finals", () => {
    const cup = { ...worlds, slug: "2026-cottbus", title: "World Cup Cottbus" };
    render(
      <CareerResults
        athlete={athlete([
          entry(
            [
              {
                competition: competition("vault-qualification", "C1", "VT"),
                allAround: null,
                team: null,
                scores: [score("VT", { rank: 2 })],
                apparatusStandings: [],
              },
              {
                competition: competition("uneven-bars-qualification", "C1", "UB"),
                allAround: null,
                team: null,
                scores: [score("UB", { rank: 3, qualification: "Q" })],
                apparatusStandings: [],
              },
              {
                competition: competition("vault-final", "C3", "VT"),
                allAround: null,
                team: null,
                scores: [score("VT", { rank: 4 })],
                apparatusStandings: [],
              },
              {
                competition: competition("uneven-bars-final", "C3", "UB"),
                allAround: null,
                team: null,
                scores: [score("UB", { rank: 1 })],
                apparatusStandings: [],
              },
            ],
            { event: cup },
          ),
        ])}
      />,
    );

    expect(roundHeaders().map((header) => header.textContent)).toEqual(["Qualification", "Apparatus Finals"]);
    const [qualifyingBars, finalBars] = screen.getAllByRole("row", { name: /Uneven Bars/ });
    expect(within(qualifyingBars).queryByTitle(/medal/)).not.toBeInTheDocument();
    expect(within(finalBars).getByTitle("Gold medal")).toHaveTextContent("1, gold medal");
    expect(within(screen.getAllByRole("row", { name: /^Vault/ })[1]).queryByTitle(/medal/)).not.toBeInTheDocument();
  });

  it("gives medals for what a final awards them for: the all-around in an all-around final, the team in a team final", () => {
    const sixth = (apparatus: Apparatus, rank: number) => score(apparatus, { rank });
    render(
      <CareerResults
        athlete={athlete([
          entry([
            {
              competition: competition("qualification", "C1"),
              allAround: { rank: 2, rankStatus: "RANKED", total: 84.632, qualification: "Q", purpose: "QUALIFYING" },
              team: {
                noc: "JPN",
                rank: 1,
                rankStatus: "RANKED",
                total: 254.529,
                qualification: "Q",
                purpose: "QUALIFYING",
              },
              scores: [sixth("UB", 1)],
              apparatusStandings: [],
            },
            {
              competition: competition("team-final", "C4"),
              allAround: null,
              team: {
                noc: "JPN",
                rank: 1,
                rankStatus: "RANKED",
                total: 251.928,
                qualification: null,
                purpose: "FINAL",
              },
              scores: [score("UB")],
              apparatusStandings: [],
            },
            {
              competition: competition("all-around-final", "C2"),
              allAround: { rank: 1, rankStatus: "RANKED", total: 85.998, qualification: null, purpose: "FINAL" },
              team: null,
              scores: [sixth("UB", 1), sixth("BB", 3)],
              apparatusStandings: [],
            },
          ]),
        ])}
      />,
    );

    const medals = screen.getAllByTitle(/medal/);
    expect(medals).toHaveLength(2);
    const [qualifyingTeam, finalTeam] = screen.getAllByRole("row", { name: /Team JPN/ });
    expect(qualifyingTeam).toHaveTextContent("254.5291Q");
    expect(within(qualifyingTeam).queryByTitle(/medal/)).not.toBeInTheDocument();
    expect(within(finalTeam).getByTitle("Gold medal")).toBeInTheDocument();
    expect(within(finalTeam).getByRole("link")).toHaveAttribute(
      "href",
      "/events/2026-world-championships/wag/sr/team-final?view=teams&athlete=7",
    );
    const allAroundFinal = screen.getAllByRole("row", { name: /All-Around/ }).at(-1)!;
    expect(within(allAroundFinal).getByTitle("Gold medal")).toBeInTheDocument();
    // Placing on an apparatus within the all-around final wins no medal
    for (const bars of screen.getAllByRole("row", { name: /Uneven Bars/ })) {
      expect(within(bars).queryByTitle(/medal/)).not.toBeInTheDocument();
    }
  });

  it("shows bonus and penalty columns when any result has them, the Superior Jury's penalty counted in", () => {
    render(
      <CareerResults
        athlete={athlete([
          entry([
            {
              competition: competition("qualification", "C1"),
              allAround: null,
              team: null,
              scores: [
                score("BB", { routine: { ...routine(5.8, 7.9, 13.3), penalty: -0.1, sjPenalty: -0.3 } }),
                score("FX", { routine: { ...routine(5.3, 7.9, 13.3), bonus: 0.1 } }),
              ],
              apparatusStandings: [],
            },
          ]),
        ])}
      />,
    );

    expect(columnHeaders()).toEqual([
      "Apparatus",
      "DDifficulty",
      "EExecution",
      "BBonus",
      "PenPenalty",
      "Score",
      "Rank",
    ]);
    expect(row(/Balance Beam/)).toHaveTextContent("5.87.900-0.413.300");
    expect(within(row(/Balance Beam/)).getByTitle("Penalty -0.1, Superior Jury -0.3")).toBeInTheDocument();
    expect(row(/Floor/)).toHaveTextContent("5.37.9000.113.300");
  });

  it("leaves out bonus, penalty and qualification columns no result needs", () => {
    render(
      <CareerResults
        athlete={athlete([
          entry([
            {
              competition: competition("qualification", "C1"),
              allAround: null,
              team: null,
              scores: [score("UB")],
              apparatusStandings: [],
            },
          ]),
        ])}
      />,
    );

    expect(columnHeaders()).toEqual(["Apparatus", "DDifficulty", "EExecution", "Score", "Rank"]);
  });

  it("names who they competed for only where it differs from their current country", () => {
    const qualification = {
      competition: competition("qualification", "C1"),
      allAround: null,
      team: null,
      scores: [score("UB")],
      apparatusStandings: [],
    };
    render(
      <CareerResults
        athlete={athlete([
          entry([qualification]),
          entry([qualification], { event: { ...worlds, slug: "2025-worlds", title: "Worlds 2025" }, noc: "AIN" }),
        ])}
      />,
    );

    const [latest, earlier] = screen.getAllByRole("heading", { level: 3 });
    expect(latest).not.toHaveTextContent(/Korea/);
    expect(earlier).toHaveTextContent(/AIN|Individual Neutral/);
  });

  it("shows a split competition's combined apparatus standings", () => {
    render(
      <CareerResults
        athlete={athlete([
          entry(
            [
              {
                competition: competition("all-around-and-apparatus-final", "C1", null, {
                  name: "All-Around and Apparatus Final",
                  shortName: "Final",
                  discipline: "MAG",
                  purposes: { team: null, allAround: "FINAL", apparatus: "FINAL" },
                }),
                allAround: { rank: 5, rankStatus: "RANKED", total: 163.896, qualification: null, purpose: "FINAL" },
                team: null,
                scores: [],
                apparatusStandings: [{ apparatus: "VT", rank: 12, total: 26.35 }],
              },
            ],
            {
              event: { ...worlds, slug: "2026-us-championships", title: "US Championships" },
              noc: "USA",
              club: "U of Oklahoma",
            },
          ),
        ])}
      />,
    );

    expect(screen.getByText(/U of Oklahoma/)).toBeInTheDocument();
    expect(row(/^Vault/)).toHaveTextContent("26.35012");
    expect(within(row(/^Vault/)).getByRole("link")).toHaveAttribute(
      "href",
      "/events/2026-us-championships/mag/sr/all-around-and-apparatus-final?view=combined-VT&athlete=7",
    );
  });

  it("gives medals for titles Competition I decided, and says why a result has no rank", () => {
    render(
      <CareerResults
        athlete={athlete([
          entry([
            {
              competition: competition("qualification", "C1", null, {
                name: "Team and All-Around Final · Apparatus Qualification",
                purposes: { team: "FINAL", allAround: "FINAL", apparatus: "QUALIFYING" },
              }),
              allAround: { rank: null, rankStatus: "NOC_LIMIT", total: 52.1, qualification: null, purpose: "FINAL" },
              team: { noc: "ALG", rank: 2, rankStatus: "RANKED", total: 150.2, qualification: null, purpose: "FINAL" },
              scores: [score("UB", { rank: 1, qualification: "Q" })],
              apparatusStandings: [],
            },
          ]),
        ])}
      />,
    );

    expect(roundHeaders().map((header) => header.textContent)).toEqual([
      "Team and All-Around Final · Apparatus QualificationSun 18 Oct",
    ]);
    expect(within(row(/Team ALG/)).getByTitle("Silver medal")).toBeInTheDocument();
    // First on bars qualifies for the final, which awards the medal
    expect(within(row(/Uneven Bars/)).queryByTitle(/medal/)).not.toBeInTheDocument();
    expect(within(row(/^All-Around/)).getByTitle(/over the limit per country/)).toHaveTextContent("NR");
  });

  it("shows the mixed team a member counted for, with its medal, though they competed in no final round", () => {
    const yog = { ...worlds, slug: "2026-youth-olympic-games", title: "Youth Olympic Games" };
    const result = (slug: string, name: string, rank: number, purpose: "QUALIFYING" | "FINAL") => ({
      slug,
      name,
      discipline: "MIX" as const,
      ageCategory: "JR" as const,
      rank,
      rankStatus: "RANKED" as const,
      total: 81.898,
      qualification: purpose === "QUALIFYING" ? ("Q" as const) : null,
      purpose,
    });
    render(
      <CareerResults
        athlete={athlete([
          entry([], {
            event: yog,
            noc: "CHN",
            mixedTeam: {
              noc: "CHN",
              results: [
                result("qualification", "Qualification", 1, "QUALIFYING"),
                result("team-final-round-3", "Team Final, Round 3", 1, "FINAL"),
              ],
            },
          }),
        ])}
      />,
    );

    expect(roundHeaders().map((header) => header.textContent)).toEqual(["Mixed Team CHN"]);
    expect(within(row(/^Qualification/)).queryByTitle(/medal/)).not.toBeInTheDocument();
    expect(within(row(/^Team Final, Round 3/)).getByTitle("Gold medal")).toBeInTheDocument();
    expect(within(row(/^Team Final, Round 3/)).getByRole("link")).toHaveAttribute(
      "href",
      "/events/2026-youth-olympic-games/mix/jr/team-final-round-3?view=teams&athlete=7",
    );
  });
});
