import type { AllAroundRow, Apparatus, ApparatusStandingRow, Routine, ScoreRow, TeamRow } from "~/api/types";
import { countryName } from "~/lib/countries";
import { formatScore, formatValue } from "~/lib/format";
import { APPARATUS_LABELS, APPARATUS_SHORT_LABELS } from "~/lib/labels";
import { ExpandableTable, type Column } from "./ExpandableTable";
import { DetailList, Gymnast, QualificationBadge, Rank } from "./parts";

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
    ["Score", routine.status === "COMPLETED" ? formatScore(routine.score) : statusLabel(routine)],
  ];
}

/** D, E, bonus and penalty on one line, for a phone, where their columns are hidden; blanks are left out. */
function RoutineLine({ routine }: { routine: Routine }) {
  const items = (
    [
      ["D", "Difficulty", difficulty(routine)],
      ["E", "Execution", formatScore(routine.execution)],
      ["B", "Bonus", formatValue(routine.bonus)],
      ["P", "Penalty", formatValue(routine.penalty)],
    ] as const
  ).filter(([, , value]) => value !== "");
  if (items.length === 0) {
    return null;
  }
  return (
    <span className="mt-0.5 flex flex-wrap gap-x-2.5 text-xs text-gray-500 tabular-nums sm:hidden">
      {items.map(([short, label, value]) => (
        <span key={short} className="whitespace-nowrap">
          <abbr title={label} className="no-underline">
            {short}
          </abbr>{" "}
          {value}
        </span>
      ))}
    </span>
  );
}

/**
 * Whether an expanded row would show more than the columns and the phone line:
 * vault's second attempt, an itemized bonus, a Superior Jury penalty, or a
 * qualification rank that differs from the rank.
 */
function hasMoreDetail(row: ScoreRow, apparatus: Apparatus): boolean {
  return (
    apparatus === "VT" ||
    (row.routine.bonusDetail?.length ?? 0) > 0 ||
    !!row.routine.sjPenalty ||
    (row.qualificationRank != null && row.qualificationRank !== row.rank)
  );
}

function statusLabel(routine: Routine): string {
  return { COMPLETED: "", DNS: "Did not start", INVALID_VAULT: "Invalid vault", UNKNOWN: "Unknown" }[routine.status];
}

/**
 * One apparatus's scores as published. In qualification the qualification
 * column shows who made the final; scores dropped from a team's total are
 * shown faded. The bonus column appears only when someone earned a bonus,
 * so that a row's D, E, bonus and penalty add up to its total. On a phone,
 * where those columns are hidden, they're on a line under the gymnast instead.
 * Rows expand only when there's more to show (see hasMoreDetail); vault, left
 * for later, always expands and has no phone line.
 *
 * @param rankedOnFirstVault a championship qualification ranks vault on the
 *   first vault, the one that counts for all-around and team, so that is the
 *   total shown; the two-vault total, which decides the vault final, is in
 *   the expanded row
 */
export function ScoreTable({
  apparatus,
  scores,
  qualification,
  teamScoring,
  rankedOnFirstVault,
}: {
  apparatus: Apparatus;
  scores: ScoreRow[];
  qualification: boolean;
  teamScoring: boolean;
  rankedOnFirstVault: boolean;
}) {
  const shown = (row: ScoreRow) => (rankedOnFirstVault ? row.routine.score : row.total);
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
        <Gymnast athlete={row.athlete} noc={row.noc}>
          {apparatus !== "VT" && <RoutineLine routine={row.routine} />}
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
      sortValue: shown,
      cell: (row) =>
        row.routine.status !== "COMPLETED" && shown(row) == null ? (
          <span className="text-gray-500">{statusLabel(row.routine)}</span>
        ) : teamScoring && !row.countsTowardTeam ? (
          <span className="text-gray-400" title="Dropped from the team total">
            {formatScore(shown(row))}
          </span>
        ) : (
          <span className="font-semibold">{formatScore(shown(row))}</span>
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
      detail={(row) =>
        hasMoreDetail(row, apparatus) && (
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
        )
      }
    />
  );
}

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
    { header: "Gymnast", cell: (row) => <Gymnast athlete={row.athlete} noc={row.noc} /> },
    ...apparatus.map((app): Column<AllAroundRow> => ({
      header: app,
      label: APPARATUS_LABELS[app],
      align: "right",
      wide: true,
      sortValue: (row) => row.apparatusScores[app],
      cell: (row) => formatScore(row.apparatusScores[app]),
    })),
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
    <ExpandableTable
      caption="All-around results"
      columns={columns}
      defaultSort="#"
      rows={rows}
      rowKey={(row) => `${row.bib}-${row.athlete.id}`}
      detail={(row) => (
        <DetailList
          items={apparatus.map((app): [string, string] => [
            APPARATUS_SHORT_LABELS[app],
            formatScore(row.apparatusScores[app]),
          ])}
        />
      )}
    />
  );
}

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
    { header: "Team", cell: (row) => <span className="font-medium">{countryName(row.noc)}</span> },
    ...apparatus.map((app): Column<TeamRow> => ({
      header: app,
      label: APPARATUS_LABELS[app],
      align: "right",
      wide: true,
      sortValue: (row) => row.apparatusTotals[app],
      cell: (row) => formatScore(row.apparatusTotals[app]),
    })),
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
    <ExpandableTable
      caption="Team results"
      columns={columns}
      defaultSort="#"
      rows={rows}
      rowKey={(row) => row.noc}
      detail={(row) => (
        <DetailList
          items={apparatus.map((app): [string, string] => [
            APPARATUS_SHORT_LABELS[app],
            formatScore(row.apparatusTotals[app]),
          ])}
        />
      )}
    />
  );
}

/** A split round's combined standings on one apparatus (e.g. US Championships' two-day titles). */
export function StandingsTable({ apparatus, rows }: { apparatus: Apparatus; rows: ApparatusStandingRow[] }) {
  return (
    <ExpandableTable
      caption={`${APPARATUS_LABELS[apparatus]} combined standings`}
      columns={[
        { header: "#", label: "Rank", cell: (row) => <Rank rank={row.rank} /> },
        { header: "Gymnast", cell: (row) => <Gymnast athlete={row.athlete} noc={row.noc} /> },
        {
          header: "Total",
          align: "right",
          cell: (row) => <span className="font-semibold">{formatScore(row.total)}</span>,
        },
      ]}
      rows={rows}
      rowKey={(row) => `${row.bib}-${row.athlete.id}`}
    />
  );
}
