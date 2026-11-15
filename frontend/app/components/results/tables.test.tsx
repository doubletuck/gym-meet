import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { AllAroundRow, Routine, ScoreRow, TeamRow } from "~/api/types";
import { AllAroundTable, ScoreTable, TeamTable } from "./tables";

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
  routine: routine({ difficulty: 5.4, execution: 9.166, score: 14.566 }),
  secondRoutine: routine({ difficulty: 5.0, execution: 9.0, score: 14.0 }),
  combinedBonus: 0.2,
  total: 14.483,
  qualificationRank: 2,
  qualification: "Q",
  countsTowardTeam: true,
};

describe("ScoreTable", () => {
  it("shows the first vault in qualification, the two-vault total once expanded", async () => {
    render(<ScoreTable apparatus="VT" scores={[yeo]} qualification teamScoring={false} rankedOnFirstVault />);

    const row = screen.getByText("Seojeong Yeo").closest("tr")!;
    expect(within(row).getByText("14.566")).toBeInTheDocument();
    expect(screen.queryByText("Two-vault total")).not.toBeInTheDocument();

    await userEvent.click(within(row).getByRole("button", { name: "Show details" }));

    expect(screen.getByText("Vault 2")).toBeInTheDocument();
    expect(screen.getByText("Two-vault total").nextSibling).toHaveTextContent("14.483");
    expect(screen.getByText("Qualification rank").nextSibling).toHaveTextContent("2");
    expect(within(row).getByRole("button", { name: "Hide details" })).toHaveAttribute("aria-expanded", "true");
  });

  it("shows the two-vault total in a vault final", () => {
    render(
      <ScoreTable apparatus="VT" scores={[yeo]} qualification={false} teamScoring={false} rankedOnFirstVault={false} />,
    );

    expect(screen.getByText("14.483")).toBeInTheDocument();
  });

  it("fades a score dropped from the team total and marks a D score under inquiry", async () => {
    const dropped: ScoreRow = {
      ...yeo,
      secondRoutine: null,
      routine: routine({ difficulty: 5.5, difficultyInquiry: true, execution: 7.766, score: 13.266 }),
      total: 13.266,
      countsTowardTeam: false,
    };
    render(<ScoreTable apparatus="BB" scores={[dropped]} qualification teamScoring rankedOnFirstVault />);

    expect(screen.getByTitle("Dropped from the team total")).toHaveTextContent("13.266");
    await userEvent.click(screen.getByRole("button", { name: "Show details" }));
    expect(screen.getByText("Difficulty").nextSibling).toHaveTextContent("!5.5");
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

    const { unmount } = render(
      <ScoreTable apparatus="PB" scores={[zou, plain]} qualification={false} teamScoring={false} rankedOnFirstVault />,
    );
    expect(screen.getByRole("columnheader", { name: "Bon" })).toBeInTheDocument();
    expect(
      within(screen.getByText("Jingyuan Zou").closest("tr")!).getByRole("cell", { name: "0.1" }),
    ).toBeInTheDocument();
    unmount();

    render(<ScoreTable apparatus="PB" scores={[plain]} qualification={false} teamScoring={false} rankedOnFirstVault />);
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
    render(
      <ScoreTable apparatus="PB" scores={[zou, lin]} qualification={false} teamScoring={false} rankedOnFirstVault />,
    );

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

    const { unmount } = render(
      <ScoreTable apparatus="UB" scores={[plain]} qualification={false} teamScoring={false} rankedOnFirstVault />,
    );
    expect(screen.queryByRole("button", { name: "Show details" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Details" })).not.toBeInTheDocument();
    unmount();

    render(
      <ScoreTable apparatus="UB" scores={[plain, sj]} qualification={false} teamScoring={false} rankedOnFirstVault />,
    );
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
        teamScoring={false}
        rankedOnFirstVault={false}
      />,
    );
    const order = () => screen.getAllByText(/^A /).map((name) => name.textContent);

    await userEvent.click(screen.getByRole("button", { name: "D" }));
    expect(order()).toEqual(["A High", "A Mid", "A Low"]);

    await userEvent.click(screen.getByRole("button", { name: "Pen" }));
    expect(order()).toEqual(["A Mid", "A High", "A Low"]);
  });

  it("shows did not start in place of a total", () => {
    const dns: ScoreRow = { ...yeo, rank: null, secondRoutine: null, routine: routine({ status: "DNS" }), total: null };
    render(<ScoreTable apparatus="PH" scores={[dns]} qualification teamScoring={false} rankedOnFirstVault />);

    expect(screen.getByText("Did not start")).toBeInTheDocument();
    expect(screen.getByText("–")).toBeInTheDocument();
  });
});

describe("AllAroundTable", () => {
  function allAround(rank: number | null, surname: string, VT: number, total: number | null): AllAroundRow {
    return {
      rank,
      bib: surname,
      athlete: { id: rank ?? 0, surname, givenName: "A" },
      noc: "USA",
      total,
      qualification: null,
      apparatusScores: { VT },
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
    expect(within(cell).getByTitle("Vault").parentElement).toHaveTextContent("VT 13.500");
    expect(screen.queryByRole("button", { name: "Show details" })).not.toBeInTheDocument();
  });

  it("is ranked as published until a header is tapped", () => {
    render(<AllAroundTable rows={rows} apparatus={["VT"]} qualification={false} />);

    expect(order()).toEqual(["A First", "A Second", "A Unranked"]);
    expect(screen.getByRole("columnheader", { name: "#" })).toHaveAttribute("aria-sort", "ascending");
  });

  it("sorts an apparatus highest first, then lowest first", async () => {
    render(<AllAroundTable rows={rows} apparatus={["VT"]} qualification={false} />);
    const vault = screen.getByRole("button", { name: "VT" });

    await userEvent.click(vault);
    expect(order()).toEqual(["A Second", "A First", "A Unranked"]);
    expect(screen.getByRole("columnheader", { name: "VT" })).toHaveAttribute("aria-sort", "descending");

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
});

describe("TeamTable", () => {
  it("lists apparatus totals under the team for a phone, leaving out blanks", () => {
    const team: TeamRow = { rank: 1, noc: "JPN", total: 252.0, qualification: null, apparatusTotals: { FX: 42.1 } };
    render(<TeamTable rows={[team]} apparatus={["FX", "PH"]} qualification={false} />);

    const cell = screen.getByText("Japan").closest("td")!;
    expect(within(cell).getByTitle("Floor Exercise").parentElement).toHaveTextContent("FX 42.100");
    expect(within(cell).queryByTitle("Pommel Horse")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show details" })).not.toBeInTheDocument();
  });
});
