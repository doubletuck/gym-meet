import { render as renderInPage, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import type { AllAroundRow, ApparatusStandingRow, Routine, ScoreRow, CompetitionResults, TeamRow } from "~/api/types";
import {
  AllAroundTable,
  firstVaults,
  ScoreTable,
  StandingsTable,
  standingsApparatus,
  TeamTable,
  VaultTable,
  vaultFinalQualifying,
} from "./tables";

// Gymnast names link to their athlete pages, so the tables render inside a router
const render = (ui: ReactElement) => renderInPage(<MemoryRouter>{ui}</MemoryRouter>);

function routine(overrides: Partial<Routine>): Routine {
  return {
    status: "COMPLETED",
    difficulty: null,
    difficultyInquiry: false,
    execution: null,
    bonus: null,
    bonusDetail: null,
    penalty: null,
    sjPenalty: null,
    score: null,
    ...overrides,
  };
}

// Yeo's 2026 Worlds qualification vault: first on the single-vault list, second for the vault final
const yeo: ScoreRow = {
  rank: 1,
  bib: "525",
  athlete: { id: 1, surname: "Yeo", givenName: "Seojeong" },
  noc: "KOR",
  club: null,
  routine: routine({ difficulty: 5.4, execution: 9.166, score: 14.566 }),
  secondRoutine: routine({ difficulty: 5.0, execution: 9.0, score: 14.0 }),
  combinedBonus: 0.2,
  total: 14.483,
  qualificationRank: 2,
  qualification: "Q",
  teamRole: "COUNTING",
};

describe("ScoreTable", () => {
  it("shows a championship qualification's first vault only, with no qualification column", () => {
    render(<ScoreTable apparatus="VT" scores={firstVaults([yeo])} qualification={false} />);

    const row = screen.getByText("Seojeong Yeo").closest("tr")!;
    expect(within(row).getByRole("cell", { name: "14.566" })).toBeInTheDocument();
    expect(screen.queryByText("14.483")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show details" })).not.toBeInTheDocument();
  });

  it("fades a score dropped from the team total and marks a D score under inquiry", async () => {
    const dropped: ScoreRow = {
      ...yeo,
      secondRoutine: null,
      routine: routine({ difficulty: 5.5, difficultyInquiry: true, execution: 7.766, score: 13.266 }),
      total: 13.266,
      teamRole: "DROPPED",
    };
    render(<ScoreTable apparatus="BB" scores={[dropped]} qualification />);

    expect(screen.getByTitle("Dropped from the team total")).toHaveTextContent("13.266");
    await userEvent.click(screen.getByRole("button", { name: "Show details" }));
    expect(screen.getByText("Difficulty").nextSibling).toHaveTextContent("!5.5");
  });

  it("fades an individual's score and says it wasn't the team's, apart from a counting one", () => {
    const individual: ScoreRow = {
      ...yeo,
      athlete: { id: 2, surname: "Malik", givenName: "Ritam" },
      secondRoutine: null,
      routine: routine({ difficulty: 4.3, execution: 8.7, score: 13.0 }),
      total: 13.0,
      teamRole: "INDIVIDUAL",
    };
    const counting: ScoreRow = {
      ...individual,
      athlete: { id: 3, surname: "Thorpe", givenName: "Heath" },
      total: 12.9,
      teamRole: "COUNTING",
    };
    render(<ScoreTable apparatus="FX" scores={[individual, counting]} qualification={false} />);

    expect(screen.getByTitle("Competed as an individual, not for the team")).toHaveTextContent("13.000");
    expect(screen.getAllByTitle(/team/)).toHaveLength(1);
  });

  it("shows a bonus column only when someone earned a bonus", () => {
    const zou: ScoreRow = {
      ...yeo,
      athlete: { id: 2, surname: "Zou", givenName: "Jingyuan" },
      secondRoutine: null,
      routine: routine({ difficulty: 6.6, execution: 8.733, bonus: 0.1, score: 15.433 }),
      total: 15.433,
    };
    const plain: ScoreRow = {
      ...zou,
      athlete: { id: 3, surname: "Lin", givenName: "Chaopan" },
      routine: routine({ difficulty: 6, execution: 8, score: 14 }),
      total: 14,
    };

    const { unmount } = render(<ScoreTable apparatus="PB" scores={[zou, plain]} qualification={false} />);
    expect(screen.getByRole("columnheader", { name: "Bon" })).toBeInTheDocument();
    expect(
      within(screen.getByText("Jingyuan Zou").closest("tr")!).getByRole("cell", { name: "0.1" }),
    ).toBeInTheDocument();
    unmount();

    render(<ScoreTable apparatus="PB" scores={[plain]} qualification={false} />);
    expect(screen.queryByRole("columnheader", { name: "Bon" })).not.toBeInTheDocument();
  });

  it("lists D, E, bonus and penalty under the gymnast for a phone, leaving out blanks", () => {
    const zou: ScoreRow = {
      ...yeo,
      qualificationRank: 1,
      athlete: { id: 2, surname: "Zou", givenName: "Jingyuan" },
      secondRoutine: null,
      routine: routine({ difficulty: 5.8, execution: 9.566, bonus: 0.1, penalty: -0.3, score: 15.166 }),
    };
    const lin: ScoreRow = {
      ...zou,
      athlete: { id: 3, surname: "Lin", givenName: "Chaopan" },
      routine: routine({ difficulty: 6, execution: 8, score: 14 }),
    };
    render(<ScoreTable apparatus="PB" scores={[zou, lin]} qualification={false} />);

    const zouCell = screen.getByText("Jingyuan Zou").closest("td")!;
    expect(within(zouCell).getByTitle("Difficulty").parentElement).toHaveTextContent("D 5.8");
    expect(within(zouCell).getByTitle("Execution").parentElement).toHaveTextContent("E 9.566");
    expect(within(zouCell).getByTitle("Bonus").parentElement).toHaveTextContent("B 0.1");
    expect(within(zouCell).getByTitle("Penalty").parentElement).toHaveTextContent("P -0.3");

    const linCell = screen.getByText("Chaopan Lin").closest("td")!;
    expect(within(linCell).getByTitle("Execution")).toBeInTheDocument();
    expect(within(linCell).queryByTitle("Bonus")).not.toBeInTheDocument();
    expect(within(linCell).queryByTitle("Penalty")).not.toBeInTheDocument();
  });

  it("highlights the athlete a link came from and opens their details", () => {
    const plain: ScoreRow = {
      ...yeo,
      secondRoutine: null,
      routine: routine({ difficulty: 6, execution: 8, score: 14 }),
      total: 14,
    };
    const penalised: ScoreRow = {
      ...plain,
      athlete: { id: 2, surname: "Penalised", givenName: "A" },
      routine: routine({ difficulty: 6, execution: 8, sjPenalty: -1, score: 13 }),
    };
    render(<ScoreTable apparatus="UB" scores={[plain, penalised]} qualification={false} athleteId={2} />);

    const row = screen.getByText("A Penalised").closest("tr")!;
    expect(row).toHaveAttribute("data-highlighted", "true");
    expect(screen.getByText("Seojeong Yeo").closest("tr")).not.toHaveAttribute("data-highlighted");
    expect(within(row).getByRole("button", { name: "Hide details" })).toHaveAttribute("aria-expanded", "true");
  });

  it("expands only rows with more to show than the columns", () => {
    const plain: ScoreRow = {
      ...yeo,
      qualificationRank: 1,
      secondRoutine: null,
      routine: routine({ difficulty: 6, execution: 8, score: 14 }),
      total: 14,
    };
    const sj: ScoreRow = {
      ...plain,
      athlete: { id: 2, surname: "Penalised", givenName: "A" },
      routine: routine({ difficulty: 6, execution: 8, sjPenalty: -1, score: 13 }),
    };

    const { unmount } = render(<ScoreTable apparatus="UB" scores={[plain]} qualification={false} />);
    expect(screen.queryByRole("button", { name: "Show details" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Details" })).not.toBeInTheDocument();
    unmount();

    render(<ScoreTable apparatus="UB" scores={[plain, sj]} qualification={false} />);
    expect(screen.getAllByRole("button", { name: "Show details" })).toHaveLength(1);
    expect(within(screen.getByText("A Penalised").closest("tr")!).getByRole("button")).toBeInTheDocument();
  });

  it("sorts by D highest first and by penalty largest deduction first", async () => {
    const row = (surname: string, difficulty: number, penalty: number | null): ScoreRow => ({
      ...yeo,
      athlete: { id: difficulty, surname, givenName: "A" },
      secondRoutine: null,
      routine: routine({ difficulty, execution: 8, penalty, score: 8 + difficulty + (penalty ?? 0) }),
    });
    render(
      <ScoreTable
        apparatus="FX"
        scores={[row("Low", 5, null), row("High", 6, -0.1), row("Mid", 5.5, -0.3)]}
        qualification={false}
      />,
    );
    const order = () => screen.getAllByText(/^A /).map((name) => name.textContent);

    await userEvent.click(screen.getByRole("button", { name: "D" }));
    expect(order()).toEqual(["A High", "A Mid", "A Low"]);

    await userEvent.click(screen.getByRole("button", { name: "Pen" }));
    expect(order()).toEqual(["A Mid", "A High", "A Low"]);
  });

  it("shows an invalid vault's zero beside its status", async () => {
    const invalid: ScoreRow = {
      ...yeo,
      rank: 109,
      secondRoutine: null,
      routine: routine({ status: "INVALID_VAULT", difficulty: 0, execution: 0, score: 0 }),
      total: 0,
      qualificationRank: 109,
    };
    render(<ScoreTable apparatus="VT" scores={firstVaults([invalid])} qualification={false} />);

    const total = within(screen.getByText("Seojeong Yeo").closest("tr")!).getAllByRole("cell").at(-1)!;
    expect(total).toHaveTextContent("Invalid vault0.000");
  });

  it("shows did not start in place of a total", () => {
    const dns: ScoreRow = { ...yeo, rank: null, secondRoutine: null, routine: routine({ status: "DNS" }), total: null };
    render(<ScoreTable apparatus="PH" scores={[dns]} qualification />);

    expect(screen.getByText("Did not start")).toBeInTheDocument();
    expect(screen.getByText("–")).toBeInTheDocument();
  });
});

describe("VaultTable", () => {
  // Andrade's 2026 Worlds vault final: (14.400 + 14.133) / 2 plus a 0.2 combined bonus
  const andrade: ScoreRow = {
    ...yeo,
    rank: 1,
    athlete: { id: 3, surname: "Andrade", givenName: "Rebeca" },
    noc: "BRA",
    routine: routine({ difficulty: 5.0, execution: 9.4, score: 14.4 }),
    secondRoutine: routine({ difficulty: 4.8, execution: 9.333, score: 14.133 }),
    combinedBonus: 0.2,
    total: 14.466,
    qualificationRank: null,
    qualification: null,
  };
  // Pease's second vault is the harder one by penalty, her first by D
  const pease: ScoreRow = {
    ...andrade,
    rank: 2,
    athlete: { id: 4, surname: "Pease", givenName: "Claire" },
    noc: "USA",
    routine: routine({ difficulty: 5.6, execution: 8.766, score: 14.366 }),
    secondRoutine: routine({ difficulty: 5.0, execution: 9.0, penalty: -0.3, score: 13.7 }),
    total: 14.233,
  };
  const order = () => screen.getAllByText(/^(Rebeca|Claire) /).map((name) => name.textContent);

  it("shows both vaults on their own lines beside one total and its combined bonus", () => {
    render(<VaultTable scores={[andrade]} qualification={false} />);

    const row = screen.getByText("Rebeca Andrade").closest("tr")!;
    const [, , vault, d, , , score, total] = within(row).getAllByRole("cell");
    expect(vault).toHaveTextContent("12");
    expect(d).toHaveTextContent("5.04.8");
    expect(score).toHaveTextContent("14.40014.133");
    expect(total).toHaveTextContent("14.466+0.2");
    expect(screen.queryByRole("button", { name: "Show details" })).not.toBeInTheDocument();
  });

  it("lists each vault under the gymnast for a phone", () => {
    render(<VaultTable scores={[pease]} qualification={false} />);

    const cell = screen.getByText("Claire Pease").closest("td")!;
    const [first, second] = within(cell)
      .getAllByTitle("Score")
      .map((score) => score.closest("span.flex"));
    expect(first).toHaveTextContent("1D 5.6E 8.766= 14.366");
    expect(second).toHaveTextContent("2D 5.0E 9.000P -0.3= 13.700");
    expect(within(cell).getByTitle("Combined bonus").parentElement).toHaveTextContent("Bonus +0.2");
  });

  it("ranks a qualification's two-vault gymnasts for the final, unranked ones last", () => {
    const oneVault: ScoreRow = { ...andrade, athlete: { id: 5, surname: "Once", givenName: "A" }, secondRoutine: null };
    const unranked: ScoreRow = { ...pease, rank: 3, qualificationRank: null };
    const ranked = vaultFinalQualifying([
      { ...pease, rank: 1, qualificationRank: 2 },
      oneVault,
      unranked,
      { ...andrade, rank: 2, qualificationRank: 1 },
    ]);

    expect(ranked.map((row) => [row.athlete.surname, row.rank])).toEqual([
      ["Andrade", 1],
      ["Pease", 2],
      ["Pease", null],
    ]);
  });

  it("shows an invalid second vault's zero beside its status", () => {
    const zapata: ScoreRow = {
      ...andrade,
      secondRoutine: routine({ status: "INVALID_VAULT", difficulty: 0, execution: 0, score: 0 }),
      combinedBonus: null,
      total: 7.2,
    };
    render(<VaultTable scores={[zapata]} qualification={false} />);

    const score = within(screen.getByText("Rebeca Andrade").closest("tr")!).getAllByRole("cell")[6];
    expect(score).toHaveTextContent("14.400Invalid vault0.000");
  });

  it("sorts D on the better vault and the penalty on the bigger deduction", async () => {
    render(<VaultTable scores={[andrade, pease]} qualification={false} />);

    await userEvent.click(screen.getByRole("button", { name: "D" }));
    expect(order()).toEqual(["Claire Pease", "Rebeca Andrade"]);

    await userEvent.click(screen.getByRole("button", { name: "Pen" }));
    expect(order()).toEqual(["Claire Pease", "Rebeca Andrade"]);

    await userEvent.click(screen.getByRole("button", { name: "Score" }));
    expect(order()).toEqual(["Rebeca Andrade", "Claire Pease"]);
  });
});

describe("AllAroundTable", () => {
  function allAround(rank: number | null, surname: string, VT: number, total: number | null): AllAroundRow {
    return {
      rank,
      rankStatus: rank == null ? "INCOMPLETE" : "RANKED",
      bib: surname,
      athlete: { id: rank ?? 0, surname, givenName: "A" },
      noc: "USA",
      club: null,
      total,
      sjPenalty: null,
      qualification: null,
      apparatusScores: { VT },
      parts: [],
    };
  }
  const rows = [
    allAround(1, "First", 13.5, 55.1),
    allAround(2, "Second", 14.2, 54.9),
    allAround(null, "Unranked", 12.0, null),
  ];
  const order = () => screen.getAllByText(/^A /).map((name) => name.textContent);

  it("lists apparatus scores under the gymnast for a phone, and doesn't expand", () => {
    render(<AllAroundTable rows={rows} apparatus={["VT"]} qualification={false} />);

    const cell = screen.getByText("A First").closest("td")!;
    expect(within(cell).getByTitle("Vault").parentElement).toHaveTextContent(/ 13\.500$/);
    expect(screen.queryByRole("button", { name: "Show details" })).not.toBeInTheDocument();
  });

  it("says why an unranked gymnast has no rank", () => {
    render(<AllAroundTable rows={rows} apparatus={["VT"]} qualification={false} />);

    const unranked = screen.getByText("A Unranked").closest("tr")!;
    expect(within(unranked).getByTitle(/^Incomplete/)).toHaveTextContent("INC");
  });

  it("is ranked as published until a header is tapped", () => {
    render(<AllAroundTable rows={rows} apparatus={["VT"]} qualification={false} />);

    expect(order()).toEqual(["A First", "A Second", "A Unranked"]);
    expect(screen.getByRole("columnheader", { name: "#" })).toHaveAttribute("aria-sort", "ascending");
  });

  it("sorts an apparatus highest first, then lowest first", async () => {
    render(<AllAroundTable rows={rows} apparatus={["VT"]} qualification={false} />);
    const vault = screen.getByRole("button", { name: "Vault" });

    await userEvent.click(vault);
    expect(order()).toEqual(["A Second", "A First", "A Unranked"]);
    expect(screen.getByRole("columnheader", { name: "Vault" })).toHaveAttribute("aria-sort", "descending");

    await userEvent.click(vault);
    expect(order()).toEqual(["A Unranked", "A First", "A Second"]);
  });

  it("keeps rows without a value last in either direction", async () => {
    render(<AllAroundTable rows={rows} apparatus={["VT"]} qualification={false} />);
    const total = screen.getByRole("button", { name: "Total" });

    await userEvent.click(total);
    expect(order()).toEqual(["A First", "A Second", "A Unranked"]);
    await userEvent.click(total);
    expect(order()).toEqual(["A Second", "A First", "A Unranked"]);

    await userEvent.click(screen.getByRole("button", { name: "#" }));
    expect(order()).toEqual(["A First", "A Second", "A Unranked"]);
  });

  it("lists each part's scores under the combined ones for a competition held in parts", () => {
    const combined: AllAroundRow = {
      ...allAround(5, "Moldauer", 26.7, 163.896),
      parts: [
        { part: 1, total: 81.773, apparatusScores: { VT: 13.7 } },
        { part: 2, total: 82.123, apparatusScores: { VT: 13.0 } },
      ],
    };
    render(<AllAroundTable rows={[combined]} apparatus={["VT"]} qualification={false} />);

    const [, , vault, total] = screen.getAllByRole("cell");
    expect(vault).toHaveTextContent("26.700P1 13.700P2 13.000");
    expect(total).toHaveTextContent("163.896P1 81.773P2 82.123");
    expect(within(total).getByTitle("Part 1")).toHaveTextContent("P1");
  });
});

describe("StandingsTable", () => {
  it("lists each part's score under the combined total", () => {
    const row: ApparatusStandingRow = {
      rank: 1,
      bib: "12",
      athlete: { id: 1, surname: "Hoopes", givenName: "Patrick" },
      noc: "USA",
      club: null,
      total: 30.816,
      parts: [
        { part: 1, score: 15.641 },
        { part: 2, score: 15.175 },
      ],
    };
    render(<StandingsTable apparatus="PH" rows={[row]} />);

    expect(screen.getAllByRole("cell").at(-1)).toHaveTextContent("30.816P1 15.641P2 15.175");
  });
});

describe("TeamTable", () => {
  it("lists apparatus totals under the team for a phone, leaving out blanks", () => {
    const team: TeamRow = {
      rank: 1,
      rankStatus: "RANKED",
      noc: "JPN",
      total: 252.0,
      sjPenalty: null,
      qualification: null,
      apparatusTotals: { FX: 42.1 },
    };
    render(<TeamTable rows={[team]} apparatus={["FX", "PH"]} qualification={false} />);

    const cell = screen.getByText("Japan").closest("td")!;
    expect(within(cell).getByTitle("Floor Exercise").parentElement).toHaveTextContent(/ 42\.100$/);
    expect(within(cell).queryByTitle("Pommel Horse")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show details" })).not.toBeInTheDocument();
  });

  it("shows a penalty column only when a team has a penalty", () => {
    const team = (noc: string, total: number, sjPenalty: number | null): TeamRow => ({
      rank: null,
      rankStatus: "UNPLACED",
      noc,
      total,
      sjPenalty,
      qualification: null,
      apparatusTotals: {},
    });
    const { unmount } = render(
      <TeamTable rows={[team("CAN", 243.026, null)]} apparatus={["FX"]} qualification={false} />,
    );
    expect(screen.queryByRole("columnheader", { name: /Pen/ })).not.toBeInTheDocument();
    unmount();

    render(
      <TeamTable
        rows={[team("CAN", 243.026, null), team("CUB", 190.728, -1)]}
        apparatus={["FX"]}
        qualification={false}
      />,
    );
    expect(screen.getByRole("columnheader", { name: /Pen/ })).toBeInTheDocument();
    const cells = screen.getAllByRole("row").map((row) => row.textContent);
    expect(cells.filter((text) => text?.includes("-1.000"))).toHaveLength(1);
    expect(cells.find((text) => text?.includes("-1.000"))).toContain("190.728");
  });
});

describe("standingsApparatus", () => {
  const results = (overrides: Partial<CompetitionResults>): CompetitionResults => ({
    event: { slug: "2026-asian-championships-wag-sr", title: "13th Senior Asian Championships" },
    competition: {
      id: 1,
      slug: "qualification",
      name: "Team and All-Around Final · Apparatus Qualification",
      shortName: "Qualification",
      discipline: "WAG",
      ageCategory: "SR",
      type: "C1",
      apparatus: null,
      round: null,
      part: null,
      purposes: { team: "FINAL", allAround: "FINAL", apparatus: "QUALIFYING" },
      date: "2026-06-25",
      endDate: null,
    },
    apparatus: [],
    allAround: [],
    teams: [],
    apparatusStandings: [],
    ...overrides,
  });

  it("takes the score tables' apparatus", () => {
    expect(standingsApparatus(results({ apparatus: [{ apparatus: "BB", scores: [] }] }))).toEqual(["BB"]);
  });

  it("without score tables, takes the apparatus the standings have scores on, in Olympic order", () => {
    const row: AllAroundRow = {
      rank: 1,
      rankStatus: "RANKED",
      bib: "502",
      athlete: { id: 1, surname: "Ke", givenName: "Qinqin" },
      noc: "CHN",
      club: null,
      total: 56.299,
      sjPenalty: null,
      qualification: null,
      apparatusScores: { FX: 13.233, BB: 14.933, UB: 14.4, VT: 13.733 },
      parts: [],
    };
    expect(standingsApparatus(results({ allAround: [row] }))).toEqual(["VT", "UB", "BB", "FX"]);
  });
});
