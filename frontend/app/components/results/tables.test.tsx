import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { Routine, ScoreRow } from "~/api/types";
import { ScoreTable } from "./tables";

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

  it("shows did not start in place of a total", () => {
    const dns: ScoreRow = { ...yeo, rank: null, secondRoutine: null, routine: routine({ status: "DNS" }), total: null };
    render(<ScoreTable apparatus="PH" scores={[dns]} qualification teamScoring={false} rankedOnFirstVault />);

    expect(screen.getByText("Did not start")).toBeInTheDocument();
    expect(screen.getByText("–")).toBeInTheDocument();
  });
});
