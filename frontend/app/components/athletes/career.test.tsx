import { render as renderInPage, screen, within } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import type { AthleteDetail, AthleteEntry, Routine } from "~/api/types";
import { EntryResults, PersonalBests } from "./career";

const render = (ui: ReactElement) => renderInPage(<MemoryRouter>{ui}</MemoryRouter>);

const worlds = { slug: "2026-world-championships", title: "Worlds", startDate: "2026-10-17", endDate: "2026-10-25" };

function session(slug: string, round: "QUAL" | "AA" | "EVENT", apparatus: "UB" | "VT" | null = null) {
  return {
    id: slug.length,
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
  it("lists the best on each apparatus and the all-around, linking to where each was scored", () => {
    const athlete: AthleteDetail = {
      id: 1,
      surname: "Nemour",
      givenName: "Kaylia",
      discipline: "WAG",
      birthYear: 2006,
      otherNames: [],
      personalBests: [
        {
          apparatus: "UB",
          score: 15.333,
          difficulty: 7.0,
          execution: 8.333,
          event: worlds,
          session: session("uneven-bars-final", "EVENT", "UB"),
        },
      ],
      allAroundBest: { total: 55.999, event: worlds, session: session("qualification", "QUAL") },
      entries: [],
    };
    render(<PersonalBests athlete={athlete} />);

    const bars = screen.getByRole("row", { name: /Uneven Bars/ });
    expect(bars).toHaveTextContent("7.08.33315.333");
    expect(within(bars).getAllByRole("link")[0]).toHaveAttribute(
      "href",
      "/events/2026-world-championships/wag/sr/uneven-bars-final",
    );
    const allAround = screen.getByRole("row", { name: /All-around/ });
    expect(allAround).toHaveTextContent("55.999");
    expect(within(allAround).getAllByRole("link")[0]).toHaveTextContent("Worlds, Qualification");
  });
});

describe("EntryResults", () => {
  it("shows each session's all-around result and scores, a vault entry's two vaults and their result", () => {
    const entry: AthleteEntry = {
      event: worlds,
      noc: "KOR",
      club: null,
      entryStatus: "COMPETITOR",
      sessions: [
        {
          session: session("qualification", "QUAL"),
          allAround: { rank: 3, total: 55.1, qualification: "Q" },
          scores: [
            {
              apparatus: "VT",
              rank: 1,
              routine: routine(5.4, 9.166, 14.566),
              secondRoutine: routine(5.0, 9.0, 14.0),
              combinedBonus: 0.2,
              total: 14.483,
              qualificationRank: 2,
              qualification: "Q",
            },
          ],
          apparatusStandings: [],
        },
      ],
    };
    render(<EntryResults entry={entry} />);

    expect(screen.getByRole("link", { name: "Qualification" })).toHaveAttribute(
      "href",
      "/events/2026-world-championships/wag/sr/qualification",
    );
    expect(screen.getByText(/All-around/)).toHaveTextContent("All-around 55.100 · #3");
    expect(screen.getByRole("row", { name: /Vault 1/ })).toHaveTextContent("5.49.16614.566#1");
    expect(screen.getByRole("row", { name: /Vault 2/ })).toHaveTextContent("5.09.00014.000");
    expect(screen.getByRole("row", { name: /Vault result/ })).toHaveTextContent("14.483");
  });

  it("shows a split round's combined apparatus standings", () => {
    const entry: AthleteEntry = {
      event: { ...worlds, slug: "2026-us-championships", title: "US Championships" },
      noc: "USA",
      club: "U of Oklahoma",
      entryStatus: "COMPETITOR",
      sessions: [
        {
          session: { ...session("all-around-final", "AA"), discipline: "MAG" },
          allAround: { rank: 5, total: 163.896, qualification: null },
          scores: [],
          apparatusStandings: [{ apparatus: "VT", rank: 12, total: 26.35 }],
        },
      ],
    };
    render(<EntryResults entry={entry} />);

    expect(screen.getByText(/U of Oklahoma/)).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /Vault/ })).toHaveTextContent("26.350#12");
  });
});
