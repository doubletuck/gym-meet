import { render as renderInPage, screen, within } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import type { Apparatus, ApparatusScore, AthleteDetail, AthleteEntry, EntrySession, Routine } from "~/api/types";
import { CareerResults, PersonalBests } from "./career";

const render = (ui: ReactElement) => renderInPage(<MemoryRouter>{ui}</MemoryRouter>);

const worlds = {
  slug: "2026-world-championships",
  title: "54th Artistic Gymnastics World Championships",
  shortName: "Worlds 2026",
  startDate: "2026-10-17",
  endDate: "2026-10-25",
};

function session(slug: string, round: "QUAL" | "AA" | "EVENT", apparatus: Apparatus | null = null) {
  return {
    id: slug.length * 10 + (apparatus?.length ?? 0) + round.length,
    slug,
    discipline: "WAG" as const,
    ageCategory: "SR" as const,
    round,
    apparatus,
    part: null,
    date: "2026-10-18",
    endDate: null,
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
              session: session("uneven-bars-final", "EVENT", "UB"),
            },
          ],
          allAroundBest: { total: 55.999, event: worlds, session: session("qualification", "QUAL") },
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
              session: session("qualification", "QUAL"),
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
              session: session("qualification", "QUAL"),
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

  function entry(sessions: EntrySession[], overrides: Partial<AthleteEntry> = {}): AthleteEntry {
    return { event: worlds, noc: "KOR", club: null, entryStatus: "COMPETITOR", sessions, ...overrides };
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
              session: session("qualification", "QUAL"),
              allAround: { rank: 3, total: 55.1, qualification: "Q" },
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
                session: session("vault-qualification", "QUAL", "VT"),
                allAround: null,
                scores: [score("VT", { rank: 2 })],
                apparatusStandings: [],
              },
              {
                session: session("uneven-bars-qualification", "QUAL", "UB"),
                allAround: null,
                scores: [score("UB", { rank: 3, qualification: "Q" })],
                apparatusStandings: [],
              },
              {
                session: session("vault-final", "EVENT", "VT"),
                allAround: null,
                scores: [score("VT", { rank: 4 })],
                apparatusStandings: [],
              },
              {
                session: session("uneven-bars-final", "EVENT", "UB"),
                allAround: null,
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

  it("shows bonus and penalty columns when any result has them, the Superior Jury's penalty counted in", () => {
    render(
      <CareerResults
        athlete={athlete([
          entry([
            {
              session: session("qualification", "QUAL"),
              allAround: null,
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
              session: session("qualification", "QUAL"),
              allAround: null,
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
      session: session("qualification", "QUAL"),
      allAround: null,
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

  it("shows a split round's combined apparatus standings", () => {
    render(
      <CareerResults
        athlete={athlete([
          entry(
            [
              {
                session: { ...session("all-around-final", "AA"), discipline: "MAG" },
                allAround: { rank: 5, total: 163.896, qualification: null },
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
      "/events/2026-us-championships/mag/sr/all-around-final?view=combined-VT&athlete=7",
    );
  });
});
