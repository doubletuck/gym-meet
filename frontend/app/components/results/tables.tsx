import type { ReactNode } from "react";

import type { AllAroundRow, Apparatus, ApparatusStandingRow, Routine, ScoreRow, TeamRow } from "~/api/types";
import { formatScore, formatValue } from "~/lib/format";
import { APPARATUS_LABELS } from "~/lib/labels";
import { Abbreviation } from "../Abbreviation";
import { ExpandableTable, type Column } from "./ExpandableTable";
import { Country, DetailList, Gymnast, QualificationBadge, Rank, RoutineScore, statusLabel } from "./parts";

/** A D score as published: a leading "!" marks one under inquiry. */
function difficulty(routine: Routine): string {
  const d = formatValue(routine.difficulty);
  return d && routine.difficultyInquiry ? `!${d}` : d;
}

function routineDetails(routine: Routine): [string, string][] {
  return [
    ["Difficulty", difficulty(routine)],
    ["Execution", formatScore(routine.execution)],
    ["Bonus", formatValue(routine.bonus)],
    ...(routine.bonusDetail ?? []).map((item): [string, string] => [
      item.description ?? "Bonus",
      formatValue(item.bonus),
    ]),
    ["Penalty", formatValue(routine.penalty)],
    ["Superior Jury penalty", formatValue(routine.sjPenalty)],
    ["Score", scoreText(routine)],
  ];
}

/**
 * Labelled values on a line under a row's name, for a phone, where their
 * columns are hidden. Blanks are left out, and the line wraps between values.
 */
function PhoneLine({
  items,
  spoken = false,
  lead,
  children,
}: {
  items: (readonly [short: string, label: string, value: string])[];
  /** Reads the labels out in full, for codes like "PH" a screen reader would spell out. */
  spoken?: boolean;
  /** Leads the line in bold, e.g. the vault number. */
  lead?: ReactNode;
  /** Follows the values, e.g. "Did not start". */
  children?: ReactNode;
}) {
  const shown = items.filter(([, , value]) => value !== "");
  if (shown.length === 0 && !children) {
    return null;
  }
  return (
    <span className="mt-0.5 flex flex-wrap gap-x-2.5 text-xs text-gray-500 tabular-nums sm:hidden">
      {lead != null && <span className="font-semibold">{lead}</span>}
      {shown.map(([short, label, value]) => (
        <span key={short} className="whitespace-nowrap">
          <Abbreviation short={short} label={label} spoken={spoken} /> {value}
        </span>
      ))}
      {children}
    </span>
  );
}

function vaults(row: ScoreRow): Routine[] {
  return row.secondRoutine ? [row.routine, row.secondRoutine] : [row.routine];
}

/**
 * Whether an expanded row would show more than the columns and the phone line:
 * an itemized bonus, a Superior Jury penalty, or a qualification rank that
 * differs from the rank.
 */
function hasMoreDetail(row: ScoreRow): boolean {
  return (
    vaults(row).some((routine) => (routine.bonusDetail?.length ?? 0) > 0 || !!routine.sjPenalty) ||
    (row.qualificationRank != null && row.qualificationRank !== row.rank)
  );
}

/** A row's expanded panel: each routine in full, and what else the row carries. */
function ScoreDetail({ row, teamScoring }: { row: ScoreRow; teamScoring: boolean }) {
  return (
    <div className="space-y-3">
      {row.secondRoutine ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <p className="mb-1 font-medium">Vault 1</p>
            <DetailList items={routineDetails(row.routine)} />
          </div>
          <div>
            <p className="mb-1 font-medium">Vault 2</p>
            <DetailList items={routineDetails(row.secondRoutine)} />
          </div>
        </div>
      ) : (
        <DetailList items={routineDetails(row.routine)} />
      )}
      <DetailList
        items={[
          ["Combined bonus", formatValue(row.combinedBonus)],
          ["Two-vault total", row.secondRoutine ? formatScore(row.total) : ""],
          ["Qualification rank", row.qualificationRank != null ? String(row.qualificationRank) : ""],
          ["Team", teamScoring && !row.countsTowardTeam ? "Dropped from the team total" : ""],
        ]}
      />
    </div>
  );
}

/** A routine's score as text: an invalid vault is scored (0.000) and says so; a routine not done says why. */
function scoreText(routine: Routine): string {
  if (routine.status === "COMPLETED") {
    return formatScore(routine.score);
  }
  return routine.score != null ? `${formatScore(routine.score)} (${statusLabel(routine)})` : statusLabel(routine);
}

/**
 * One apparatus's scores as published. In qualification the qualification
 * column shows who made the final; scores dropped from a team's total are
 * shown faded. The bonus column appears only when someone earned a bonus,
 * so that a row's D, E, bonus and penalty add up to its total. On a phone,
 * where those columns are hidden, they're on a line under the gymnast instead.
 * Rows expand only when there's more to show (see hasMoreDetail). Where vault
 * is decided on two vaults, use VaultTable; for a championship qualification's
 * first vaults, pass firstVaults.
 */
export function ScoreTable({
  apparatus,
  scores,
  qualification,
  teamScoring,
}: {
  apparatus: Apparatus;
  scores: ScoreRow[];
  qualification: boolean;
  teamScoring: boolean;
}) {
  const columns: Column<ScoreRow>[] = [
    {
      header: "#",
      label: "Rank",
      sortValue: (row) => row.rank,
      sortFirst: "ascending",
      cell: (row) => <Rank rank={row.rank} />,
    },
    {
      header: "Gymnast",
      cell: (row) => (
        <Gymnast athlete={row.athlete} noc={row.noc} club={row.club}>
          <PhoneLine
            items={[
              ["D", "Difficulty", difficulty(row.routine)],
              ["E", "Execution", formatScore(row.routine.execution)],
              ["B", "Bonus", formatValue(row.routine.bonus)],
              ["P", "Penalty", formatValue(row.routine.penalty)],
            ]}
          />
        </Gymnast>
      ),
    },
    {
      header: "D",
      label: "Difficulty",
      align: "right",
      wide: true,
      sortValue: (row) => row.routine.difficulty,
      cell: (row) => difficulty(row.routine),
    },
    {
      header: "E",
      label: "Execution",
      align: "right",
      wide: true,
      sortValue: (row) => row.routine.execution,
      cell: (row) => formatScore(row.routine.execution),
    },
    ...(scores.some((row) => row.routine.bonus)
      ? [
          {
            header: "Bon",
            label: "Bonus",
            align: "right",
            wide: true,
            sortValue: (row) => row.routine.bonus,
            cell: (row) => formatValue(row.routine.bonus),
          } satisfies Column<ScoreRow>,
        ]
      : []),
    {
      header: "Pen",
      label: "Penalty",
      align: "right",
      wide: true,
      sortValue: (row) => row.routine.penalty,
      // Penalties are negative, so the largest deduction comes first
      sortFirst: "ascending",
      cell: (row) => formatValue(row.routine.penalty),
    },
    {
      header: "Total",
      align: "right",
      sortValue: (row) => row.total,
      cell: (row) =>
        teamScoring && !row.countsTowardTeam ? (
          <span className="text-gray-400" title="Dropped from the team total">
            <RoutineScore routine={row.routine} score={row.total} />
          </span>
        ) : (
          <span className="font-semibold">
            <RoutineScore routine={row.routine} score={row.total} />
          </span>
        ),
    },
  ];
  if (qualification) {
    columns.push({
      header: "Q",
      label: "Qualification",
      cell: (row) => <QualificationBadge result={row.qualification} />,
    });
  }

  return (
    <ExpandableTable
      caption={`${APPARATUS_LABELS[apparatus]} results`}
      columns={columns}
      defaultSort="#"
      rows={scores}
      rowKey={(row) => `${row.bib}-${row.athlete.id}`}
      detail={(row) => hasMoreDetail(row) && <ScoreDetail row={row} teamScoring={teamScoring} />}
    />
  );
}

/** Each vault's value on its own line, so a row's two vaults read across in line. */
function PerVault({ row, value }: { row: ScoreRow; value: (routine: Routine, index: number) => ReactNode }) {
  return vaults(row).map((routine, i) => (
    <span key={i} className="block">
      {value(routine, i) || "\u00a0"}
    </span>
  ));
}

/** The better of a row's vaults by this value, the one a vault is sorted on. */
function best(row: ScoreRow, value: (routine: Routine) => number | null, pick: (...values: number[]) => number) {
  const values = vaults(row)
    .map(value)
    .filter((v) => v != null);
  return values.length ? pick(...values) : null;
}

/**
 * Vault where it's decided on two vaults: a vault final, or the qualification
 * of an apparatus-format meet (World Cup). Each gymnast's vaults sit on two
 * lines, beside one rank and one total: the two vaults' average plus any
 * combined bonus, which is shown under it. D, E, bonus and score sort on the
 * better vault, the penalty on the bigger deduction. On a phone, each vault
 * is a line under the gymnast.
 */
export function VaultTable({
  scores,
  qualification,
  caption = "Vault results",
}: {
  scores: ScoreRow[];
  qualification: boolean;
  caption?: string;
}) {
  const columns: Column<ScoreRow>[] = [
    {
      header: "#",
      label: "Rank",
      sortValue: (row) => row.rank,
      sortFirst: "ascending",
      cell: (row) => <Rank rank={row.rank} />,
    },
    {
      header: "Gymnast",
      cell: (row) => (
        <Gymnast athlete={row.athlete} noc={row.noc} club={row.club}>
          {vaults(row).map((routine, i) => (
            <PhoneLine
              key={i}
              lead={i + 1}
              items={[
                ["D", "Difficulty", difficulty(routine)],
                ["E", "Execution", formatScore(routine.execution)],
                ["B", "Bonus", formatValue(routine.bonus)],
                ["P", "Penalty", formatValue(routine.penalty)],
                ["=", "Score", formatScore(routine.score)],
              ]}
            >
              {routine.status !== "COMPLETED" && <span>{statusLabel(routine)}</span>}
            </PhoneLine>
          ))}
          <PhoneLine items={[["Bonus", "Combined bonus", combinedBonus(row)]]} />
        </Gymnast>
      ),
    },
    {
      header: "V",
      label: "Vault",
      align: "right",
      wide: true,
      cell: (row) => (
        <span className="text-gray-400">
          <PerVault row={row} value={(_, i) => String(i + 1)} />
        </span>
      ),
    },
    {
      header: "D",
      label: "Difficulty",
      align: "right",
      wide: true,
      sortValue: (row) => best(row, (routine) => routine.difficulty, Math.max),
      cell: (row) => <PerVault row={row} value={difficulty} />,
    },
    {
      header: "E",
      label: "Execution",
      align: "right",
      wide: true,
      sortValue: (row) => best(row, (routine) => routine.execution, Math.max),
      cell: (row) => <PerVault row={row} value={(routine) => formatScore(routine.execution)} />,
    },
    ...(scores.some((row) => vaults(row).some((routine) => routine.bonus))
      ? [
          {
            header: "Bon",
            label: "Bonus",
            align: "right",
            wide: true,
            sortValue: (row) => best(row, (routine) => routine.bonus, Math.max),
            cell: (row) => <PerVault row={row} value={(routine) => formatValue(routine.bonus)} />,
          } satisfies Column<ScoreRow>,
        ]
      : []),
    {
      header: "Pen",
      label: "Penalty",
      align: "right",
      wide: true,
      // Penalties are negative, so the largest deduction comes first
      sortValue: (row) => best(row, (routine) => routine.penalty, Math.min),
      sortFirst: "ascending",
      cell: (row) => <PerVault row={row} value={(routine) => formatValue(routine.penalty)} />,
    },
    {
      header: "Score",
      align: "right",
      wide: true,
      sortValue: (row) => best(row, (routine) => routine.score, Math.max),
      cell: (row) => <PerVault row={row} value={(routine) => <RoutineScore routine={routine} />} />,
    },
    {
      header: "Total",
      label: "Average of the two vaults, plus any combined bonus",
      align: "right",
      sortValue: (row) => row.total,
      cell: (row) =>
        row.total == null && row.routine.status !== "COMPLETED" ? (
          <span className="text-gray-500">{statusLabel(row.routine)}</span>
        ) : (
          <>
            <span className="font-semibold">{formatScore(row.total)}</span>
            {row.combinedBonus ? (
              <span className="hidden text-xs leading-5 text-gray-500 sm:block" title="Combined bonus">
                {combinedBonus(row)}
              </span>
            ) : null}
          </>
        ),
    },
  ];
  if (qualification) {
    columns.push({
      header: "Q",
      label: "Qualification",
      cell: (row) => <QualificationBadge result={row.qualification} />,
    });
  }

  return (
    <ExpandableTable
      caption={caption}
      columns={columns}
      defaultSort="#"
      rows={scores}
      rowKey={(row) => `${row.bib}-${row.athlete.id}`}
      detail={(row) => hasMoreDetail(row) && <ScoreDetail row={row} teamScoring={false} />}
    />
  );
}

/**
 * A championship qualification's vault as it counts for team and all-around:
 * each gymnast's first vault, ranked as published. A second vault, and the
 * vault final qualification it goes toward, are in vaultFinalQualifying.
 */
export function firstVaults(scores: ScoreRow[]): ScoreRow[] {
  return scores.map((row) => ({
    ...row,
    secondRoutine: null,
    combinedBonus: null,
    total: row.routine.score,
    qualificationRank: null,
    qualification: null,
  }));
}

/**
 * A championship qualification's ranking for the vault final: the gymnasts who
 * vaulted twice, ranked on their two-vault total by their qualification rank.
 * Those left unranked (a vault not started) come last.
 */
export function vaultFinalQualifying(scores: ScoreRow[]): ScoreRow[] {
  return scores
    .filter((row) => row.secondRoutine != null)
    .map((row) => ({ ...row, rank: row.qualificationRank }))
    .sort((a, b) => (a.rank ?? Infinity) - (b.rank ?? Infinity));
}

function combinedBonus(row: ScoreRow): string {
  return row.combinedBonus ? `+${formatValue(row.combinedBonus)}` : "";
}

/**
 * A score over its part-by-part scores, for a round held in parts and decided
 * on the combined result (e.g. a two-day all-around).
 */
function WithParts({ score, parts }: { score: ReactNode; parts: { part: number; score?: number | null }[] }) {
  const shown = parts.filter((part) => part.score != null);
  return (
    <>
      {score}
      {shown.map(({ part, score }) => (
        <span key={part} className="block text-xs font-normal whitespace-nowrap text-gray-500">
          <abbr title={`Part ${part}`} className="no-underline">
            P{part}
          </abbr>{" "}
          {formatScore(score)}
        </span>
      ))}
    </>
  );
}

function apparatusItems(apparatus: Apparatus[], scores: Partial<Record<string, number>>) {
  return apparatus.map((app) => [app, APPARATUS_LABELS[app], formatScore(scores[app])] as const);
}

/**
 * All-around results; on a phone, each gymnast's apparatus scores are on a line
 * under their name. A round held in parts lists each part's scores under the
 * combined ones.
 */
export function AllAroundTable({
  rows,
  apparatus,
  qualification,
}: {
  rows: AllAroundRow[];
  apparatus: Apparatus[];
  qualification: boolean;
}) {
  const columns: Column<AllAroundRow>[] = [
    {
      header: "#",
      label: "Rank",
      sortValue: (row) => row.rank,
      sortFirst: "ascending",
      cell: (row) => <Rank rank={row.rank} />,
    },
    {
      header: "Gymnast",
      cell: (row) => (
        <Gymnast athlete={row.athlete} noc={row.noc} club={row.club}>
          <PhoneLine spoken items={apparatusItems(apparatus, row.apparatusScores)} />
        </Gymnast>
      ),
    },
    ...apparatus.map((app): Column<AllAroundRow> => ({
      header: app,
      label: APPARATUS_LABELS[app],
      spoken: true,
      align: "right",
      wide: true,
      sortValue: (row) => row.apparatusScores[app],
      cell: (row) => (
        <WithParts
          score={formatScore(row.apparatusScores[app])}
          parts={row.parts.map((part) => ({ part: part.part, score: part.apparatusScores[app] }))}
        />
      ),
    })),
    ...penaltyColumn(rows),
    {
      header: "Total",
      align: "right",
      sortValue: (row) => row.total,
      cell: (row) => (
        <WithParts
          score={<span className="font-semibold">{formatScore(row.total)}</span>}
          parts={row.parts.map((part) => ({ part: part.part, score: part.total }))}
        />
      ),
    },
  ];
  if (qualification) {
    columns.push({
      header: "Q",
      label: "Qualification",
      cell: (row) => <QualificationBadge result={row.qualification} />,
    });
  }

  return (
    <ExpandableTable
      caption="All-around results"
      columns={columns}
      defaultSort="#"
      rows={rows}
      rowKey={(row) => `${row.bib}-${row.athlete.id}`}
    />
  );
}

/**
 * A penalty on a result as a whole (a team penalty), already taken off the
 * total; the column is only shown when some row has one.
 */
function penaltyColumn<T extends { sjPenalty: number | null }>(rows: T[]): Column<T>[] {
  if (!rows.some((row) => row.sjPenalty != null)) {
    return [];
  }
  return [
    {
      header: "Pen.",
      label: "Penalty",
      align: "right",
      wide: true,
      sortValue: (row) => row.sjPenalty,
      cell: (row) => formatScore(row.sjPenalty),
    },
  ];
}

/** Team results; on a phone, each team's apparatus totals are on a line under its name. */
export function TeamTable({
  rows,
  apparatus,
  qualification,
}: {
  rows: TeamRow[];
  apparatus: Apparatus[];
  qualification: boolean;
}) {
  const columns: Column<TeamRow>[] = [
    {
      header: "#",
      label: "Rank",
      sortValue: (row) => row.rank,
      sortFirst: "ascending",
      cell: (row) => <Rank rank={row.rank} />,
    },
    {
      header: "Team",
      cell: (row) => (
        <>
          <span className="font-medium">
            <Country noc={row.noc} />
          </span>
          <PhoneLine spoken items={apparatusItems(apparatus, row.apparatusTotals)} />
        </>
      ),
    },
    ...apparatus.map((app): Column<TeamRow> => ({
      header: app,
      label: APPARATUS_LABELS[app],
      spoken: true,
      align: "right",
      wide: true,
      sortValue: (row) => row.apparatusTotals[app],
      cell: (row) => formatScore(row.apparatusTotals[app]),
    })),
    ...penaltyColumn(rows),
    {
      header: "Total",
      align: "right",
      sortValue: (row) => row.total,
      cell: (row) => <span className="font-semibold">{formatScore(row.total)}</span>,
    },
  ];
  if (qualification) {
    columns.push({
      header: "Q",
      label: "Qualification",
      cell: (row) => <QualificationBadge result={row.qualification} />,
    });
  }

  return (
    <ExpandableTable caption="Team results" columns={columns} defaultSort="#" rows={rows} rowKey={(row) => row.noc} />
  );
}

/** A split round's combined standings on one apparatus, each part's score under the total. */
export function StandingsTable({ apparatus, rows }: { apparatus: Apparatus; rows: ApparatusStandingRow[] }) {
  return (
    <ExpandableTable
      caption={`${APPARATUS_LABELS[apparatus]} combined standings`}
      columns={[
        { header: "#", label: "Rank", cell: (row) => <Rank rank={row.rank} /> },
        { header: "Gymnast", cell: (row) => <Gymnast athlete={row.athlete} noc={row.noc} club={row.club} /> },
        {
          header: "Total",
          align: "right",
          cell: (row) => (
            <WithParts score={<span className="font-semibold">{formatScore(row.total)}</span>} parts={row.parts} />
          ),
        },
      ]}
      rows={rows}
      rowKey={(row) => `${row.bib}-${row.athlete.id}`}
    />
  );
}
