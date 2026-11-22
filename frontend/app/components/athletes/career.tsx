import type { ReactNode } from "react";
import { Link } from "react-router";

import type {
  Apparatus,
  AthleteDetail,
  AthleteEntry,
  Discipline,
  EntrySession,
  QualificationResult,
  Routine,
} from "~/api/types";
import { formatDateRange, formatScore, formatSessionDate, formatValue } from "~/lib/format";
import {
  APPARATUS_ORDER,
  resultsPath,
  sessionLabel,
  sessionPath,
  shortSessionLabel,
  VAULT_FINAL_QUALIFYING,
} from "~/lib/labels";
import { Abbreviation, ApparatusCode } from "../Abbreviation";
import { ApparatusIcon } from "../ApparatusIcon";
import { Country, difficultyText, Placing, QualificationBadge, RoutineScore } from "../results/parts";

type Best = {
  key: string;
  code: ReactNode;
  icon?: Apparatus;
  score: number;
  breakdown?: Routine;
  event: AthleteEntry["event"];
  session: EntrySession["session"];
  view: string;
};

/**
 * The athlete's best routine on each apparatus and best all-around, a tile
 * each. A tile links to the results it was scored in, opened at that
 * apparatus with the athlete's row highlighted.
 */
export function PersonalBests({ athlete }: { athlete: AthleteDetail }) {
  const { personalBests, allAroundBest } = athlete;
  const bests: Best[] = personalBests.map((best) => ({
    key: best.apparatus,
    code: <ApparatusCode apparatus={best.apparatus} routine={best.vault ?? undefined} />,
    icon: best.apparatus,
    score: best.score,
    breakdown: best.routine,
    event: best.event,
    session: best.session,
    view: bestView(best),
  }));
  if (allAroundBest) {
    bests.push({
      key: "AA",
      code: <Abbreviation short="AA" label="All-Around" spoken />,
      score: allAroundBest.total,
      event: allAroundBest.event,
      session: allAroundBest.session,
      view: "all-around",
    });
  }
  if (bests.length === 0) {
    return null;
  }
  return (
    <ul className={`grid grid-cols-2 gap-2 ${COLUMNS[bests.length] ?? "sm:grid-cols-4"}`}>
      {bests.map((best, index) => (
        <li
          key={best.key}
          // An odd tile out on a phone takes the whole row rather than leave a gap
          className={index === bests.length - 1 && bests.length % 2 === 1 ? "col-span-2 sm:col-span-1" : ""}
        >
          <BestTile best={best} athleteId={athlete.id} />
        </li>
      ))}
    </ul>
  );
}

// From the small breakpoint up, one row of tiles where they fit, else rows of four
const COLUMNS: Record<number, string> = {
  5: "sm:grid-cols-5",
  6: "sm:grid-cols-6",
  7: "sm:grid-cols-4 lg:grid-cols-7",
};

/**
 * The view of the session's results a best is shown in: its apparatus, except
 * a championship qualification's second vault, which only the vault final's
 * two-vault ranking shows.
 */
function bestView(best: AthleteDetail["personalBests"][number]): string {
  const championshipQualification = best.session.round === "QUAL" && best.session.apparatus == null;
  return best.apparatus === "VT" && best.vault === 2 && championshipQualification
    ? VAULT_FINAL_QUALIFYING
    : best.apparatus;
}

function BestTile({ best, athleteId }: { best: Best; athleteId: number }) {
  return (
    <Link
      to={resultsPath(best.event.slug, best.session, best.view, athleteId)}
      className="flex h-full flex-col rounded-lg border border-gray-200 p-3 hover:border-gray-400 hover:bg-gray-50 dark:border-gray-800 dark:hover:border-gray-600 dark:hover:bg-gray-900"
    >
      <span className="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400">
        {best.code}
        {best.icon && <ApparatusIcon apparatus={best.icon} />}
      </span>
      <span className="mt-1 text-xl font-semibold tabular-nums">{formatScore(best.score)}</span>
      {best.breakdown && <Breakdown routine={best.breakdown} />}
      <span className="mt-auto pt-2 text-xs text-gray-500">
        <span className="block" title={best.event.title}>
          {best.event.shortName}
        </span>
        <span className="block">{shortSessionLabel(best.session)}</span>
      </span>
    </Link>
  );
}

/** What the score is made of: D and E, and bonus and penalties where there are any. */
function Breakdown({ routine }: { routine: Routine }) {
  const items: [short: string, label: string, value: string][] = [
    ["D", "Difficulty", difficultyText(routine)],
    ["E", "Execution", formatScore(routine.execution)],
    ["B", "Bonus", routine.bonus ? formatValue(routine.bonus) : ""],
    ["P", "Penalty", routine.penalty ? formatValue(routine.penalty) : ""],
    ["SJ", "Superior Jury penalty", routine.sjPenalty ? formatValue(routine.sjPenalty) : ""],
  ];
  return (
    <span className="mt-0.5 flex flex-wrap gap-x-2 text-xs text-gray-500 tabular-nums">
      {items
        .filter(([, , value]) => value !== "")
        .map(([short, label, value]) => (
          <span key={short} className="whitespace-nowrap">
            <Abbreviation short={short} label={label} /> {value}
          </span>
        ))}
    </span>
  );
}

/** Columns shown only when a result on the page needs them, the same for every meet so the tables line up. */
type Columns = { bonus: boolean; penalty: boolean; qualification: boolean };

function columnsFor(entries: AthleteEntry[]): Columns {
  const sessions = entries.flatMap((entry) => entry.sessions);
  const scores = sessions.flatMap((entrySession) => entrySession.scores);
  const routines = scores.flatMap((score) =>
    score.secondRoutine ? [score.routine, score.secondRoutine] : [score.routine],
  );
  return {
    bonus: routines.some((routine) => routine.bonus) || scores.some((score) => score.combinedBonus),
    penalty: routines.some((routine) => routine.penalty || routine.sjPenalty),
    qualification:
      scores.some((score) => score.qualification) ||
      sessions.some((entrySession) => entrySession.allAround?.qualification),
  };
}

/** Every meet the athlete has results in, a table each. */
export function CareerResults({ athlete }: { athlete: AthleteDetail }) {
  const columns = columnsFor(athlete.entries);
  const homeNoc = athlete.entries[0]?.noc;
  return (
    <div className="space-y-4">
      {athlete.entries.map((entry) => (
        <EntryResults key={entry.event.slug} entry={entry} athleteId={athlete.id} columns={columns} homeNoc={homeNoc} />
      ))}
    </div>
  );
}

/**
 * One meet: where and when, who they competed for where that isn't their
 * current country, and their results in each round.
 */
function EntryResults({
  entry,
  athleteId,
  columns,
  homeNoc,
}: {
  entry: AthleteEntry;
  athleteId: number;
  columns: Columns;
  homeNoc?: string;
}) {
  const columnCount = 5 + Number(columns.bonus) + Number(columns.penalty) + Number(columns.qualification);
  return (
    <section className="rounded-lg border border-gray-200 px-4 pt-3 pb-2 dark:border-gray-800">
      <h3 className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
        <Link to={`/events/${entry.event.slug}`} className="font-semibold hover:underline">
          {entry.event.title}
        </Link>
        <span className="text-sm text-gray-500">{formatDateRange(entry.event.startDate, entry.event.endDate)}</span>
        {(entry.club || entry.noc !== homeNoc) && (
          <span className="text-sm text-gray-600 dark:text-gray-400">
            <Country noc={entry.noc} club={entry.club} />
          </span>
        )}
      </h3>
      <div className="mt-1 overflow-x-auto">
        <table className="w-full max-w-2xl min-w-[26rem] table-fixed border-collapse text-sm tabular-nums">
          <caption className="sr-only">{entry.event.title}: results</caption>
          <colgroup>
            <col />
            <col className="w-16" />
            <col className="w-16" />
            {columns.bonus && <col className="w-14" />}
            {columns.penalty && <col className="w-14" />}
            <col className="w-20" />
            <col className="w-12" />
            {columns.qualification && <col className="w-10" />}
          </colgroup>
          <thead>
            <tr className="text-xs text-gray-500">
              <th scope="col" className="py-1 pr-2 text-left font-medium">
                <span className="sr-only">Apparatus</span>
              </th>
              <ColumnHeader short="D" label="Difficulty" />
              <ColumnHeader short="E" label="Execution" />
              {columns.bonus && <ColumnHeader short="B" label="Bonus" />}
              {columns.penalty && <ColumnHeader short="Pen" label="Penalty" />}
              <th scope="col" className="px-2 py-1 text-right font-medium">
                Score
              </th>
              <th scope="col" className="py-1 pl-2 text-right font-medium">
                Rank
              </th>
              {columns.qualification && (
                <th scope="col" className="py-1 pl-2">
                  <span className="sr-only">Qualification</span>
                </th>
              )}
            </tr>
          </thead>
          {roundsOf(entry).map((round) => (
            <tbody key={round.key}>
              <tr>
                <th
                  scope="colgroup"
                  colSpan={columnCount}
                  className="pt-3 pb-1 text-left text-xs font-semibold text-gray-600 dark:text-gray-400"
                >
                  {round.sessions.length === 1 ? (
                    <Link to={sessionPath(entry.event.slug, round.sessions[0].session)} className="hover:underline">
                      {round.label}
                    </Link>
                  ) : (
                    round.label
                  )}
                  {round.sessions.length === 1 && (
                    <span className="ml-2 font-normal text-gray-500">
                      {formatSessionDate(round.sessions[0].session.date, round.sessions[0].session.endDate)}
                    </span>
                  )}
                </th>
              </tr>
              {round.sessions
                .flatMap((entrySession) => linesOf(entry.event.slug, entrySession, athleteId))
                .sort(byApparatus(round.sessions[0].session.discipline))
                .flatMap((block) => block.lines)
                .map((line) => (
                  <ResultLine key={line.key} line={line} final={round.final} columns={columns} />
                ))}
            </tbody>
          ))}
        </table>
      </div>
    </section>
  );
}

function ColumnHeader({ short, label }: { short: string; label: string }) {
  return (
    <th scope="col" className="px-2 py-1 text-right font-medium">
      <Abbreviation short={short} label={label} spoken />
    </th>
  );
}

type Round = { key: string; label: string; final: boolean; sessions: EntrySession[] };

/**
 * An entry's sessions as rounds. A World Cup publishes each apparatus's
 * qualification as its own session, and each apparatus final is a session of
 * its own: each kind is one round here, so a World Cup reads like a
 * championship.
 */
function roundsOf(entry: AthleteEntry): Round[] {
  const rounds = new Map<string, EntrySession[]>();
  for (const entrySession of entry.sessions) {
    const key = `${entrySession.session.round}-${entrySession.session.part ?? ""}`;
    rounds.set(key, [...(rounds.get(key) ?? []), entrySession]);
  }
  return [...rounds].map(([key, sessions]) => {
    const { session } = sessions[0];
    const label =
      session.round === "QUAL"
        ? sessionLabel({ ...session, apparatus: null })
        : sessions.length > 1
          ? "Apparatus Finals"
          : sessionLabel(session);
    return { key, label, final: session.round !== "QUAL", sessions };
  });
}

type LineKind = "apparatus" | "vault" | "last-vault" | "all-around";

type Line = {
  key: string;
  kind: LineKind;
  label: ReactNode;
  to: string;
  routine?: Routine;
  bonus?: number | null;
  score: ReactNode;
  rank?: number | null;
  qualification?: QualificationResult | null;
};

type Block = { apparatus?: Apparatus; lines: Line[] };

/**
 * A session's results as lines, an apparatus to a block: two vaults are their
 * result, then each vault under it. The all-around comes last.
 */
function linesOf(eventSlug: string, entrySession: EntrySession, athleteId: number): Block[] {
  const { session, scores, apparatusStandings, allAround } = entrySession;
  const to = (view: string) => resultsPath(eventSlug, session, view, athleteId);
  // A championship qualification ranks vault on the first vault, and the vault final on both
  const championshipQualification = session.round === "QUAL" && session.apparatus == null;
  const blocks: Block[] = scores.map((score) => {
    const { apparatus, routine, secondRoutine } = score;
    const key = `${session.id}-${apparatus}`;
    if (!secondRoutine) {
      return {
        apparatus,
        lines: [
          {
            key,
            kind: "apparatus",
            label: <ApparatusCode apparatus={apparatus} />,
            to: to(apparatus),
            routine,
            bonus: routine.bonus,
            score: <RoutineScore routine={routine} />,
            rank: score.rank,
            qualification: score.qualification,
          },
        ],
      };
    }
    const vault = (number: 1 | 2, vaultRoutine: Routine): Line => ({
      key: `${key}${number}`,
      kind: number === 1 ? "vault" : "last-vault",
      label: <ApparatusCode apparatus={apparatus} routine={number} />,
      to: to(apparatus),
      routine: vaultRoutine,
      bonus: vaultRoutine.bonus,
      score: <RoutineScore routine={vaultRoutine} />,
      // The first vault's own ranking, which counts for team and all-around
      rank: number === 1 && championshipQualification ? score.rank : null,
    });
    return {
      apparatus,
      lines: [
        {
          key,
          kind: "apparatus",
          label: <Abbreviation short={apparatus} label="Vault result" spoken />,
          to: to(championshipQualification ? VAULT_FINAL_QUALIFYING : apparatus),
          bonus: score.combinedBonus,
          score: formatScore(score.total),
          rank: championshipQualification ? score.qualificationRank : score.rank,
          qualification: score.qualification,
        },
        vault(1, routine),
        vault(2, secondRoutine),
      ],
    };
  });
  for (const standing of apparatusStandings) {
    blocks.push({
      apparatus: standing.apparatus,
      lines: [
        {
          key: `${session.id}-combined-${standing.apparatus}`,
          kind: "apparatus",
          label: <ApparatusCode apparatus={standing.apparatus} />,
          to: to(`combined-${standing.apparatus}`),
          score: formatScore(standing.total),
          rank: standing.rank,
        },
      ],
    });
  }
  if (allAround) {
    blocks.push({
      lines: [
        {
          key: `${session.id}-AA`,
          kind: "all-around",
          label: <Abbreviation short="AA" label="All-Around" spoken />,
          to: to("all-around"),
          score: formatScore(allAround.total),
          rank: allAround.rank,
          qualification: allAround.qualification,
        },
      ],
    });
  }
  return blocks;
}

/** Olympic order, the all-around last. */
function byApparatus(discipline: Discipline) {
  const position = (block: Block) =>
    block.apparatus ? APPARATUS_ORDER[discipline].indexOf(block.apparatus) : APPARATUS_ORDER[discipline].length;
  return (a: Block, b: Block) => position(a) - position(b);
}

const LINE_STYLES: Record<LineKind, { row: string; cell: string; label: string }> = {
  apparatus: { row: "border-t border-gray-100 dark:border-gray-900", cell: "py-1.5", label: "" },
  // Each vault sits under its result, tied to it by a guide line
  vault: {
    row: "text-xs text-gray-500",
    cell: "py-0.5",
    label: "relative pl-5 before:absolute before:inset-y-0 before:left-2 before:border-l",
  },
  "last-vault": {
    row: "text-xs text-gray-500",
    cell: "pt-0.5 pb-1.5",
    label: "relative pl-5 before:absolute before:top-0 before:bottom-1/2 before:left-2 before:border-l",
  },
  "all-around": {
    row: "border-t-[1.5px] border-gray-200 font-semibold dark:border-gray-800",
    cell: "py-1.5",
    label: "",
  },
};

const GUIDE =
  "before:border-gray-300 after:absolute after:top-1/2 after:left-2 after:w-2 after:border-t after:border-gray-300 dark:before:border-gray-700 dark:after:border-gray-700";

function ResultLine({ line, final, columns }: { line: Line; final: boolean; columns: Columns }) {
  const styles = LINE_STYLES[line.kind];
  const vault = line.kind === "vault" || line.kind === "last-vault";
  const { routine } = line;
  return (
    <tr className={styles.row}>
      <th scope="row" className={`pr-2 text-left font-normal ${styles.cell} ${styles.label} ${vault ? GUIDE : ""}`}>
        <Link to={line.to} className="hover:underline">
          {line.label}
        </Link>
      </th>
      <td className={`px-2 text-right ${styles.cell}`}>{routine && difficultyText(routine)}</td>
      <td className={`px-2 text-right ${styles.cell}`}>{routine && formatScore(routine.execution)}</td>
      {columns.bonus && <td className={`px-2 text-right ${styles.cell}`}>{formatValue(line.bonus)}</td>}
      {columns.penalty && (
        <td
          className={`px-2 text-right ${styles.cell}`}
          title={
            routine?.sjPenalty
              ? `Penalty ${formatValue(routine.penalty) || "0"}, Superior Jury ${formatValue(routine.sjPenalty)}`
              : undefined
          }
        >
          {routine && formatValue(penaltyOf(routine))}
        </td>
      )}
      <td className={`px-2 text-right ${vault ? "" : "font-semibold"} ${styles.cell}`}>{line.score}</td>
      <td className={`pl-2 text-right text-gray-500 ${styles.cell}`}>
        <Placing rank={line.rank} final={final} />
      </td>
      {columns.qualification && (
        <td className={`pl-2 text-left ${styles.cell}`}>
          <QualificationBadge result={line.qualification ?? null} />
        </td>
      )}
    </tr>
  );
}

/** The penalty and Superior Jury penalty together, so a row adds up to its score. */
function penaltyOf(routine: Routine): number | null {
  if (!routine.penalty && !routine.sjPenalty) {
    return null;
  }
  return Math.round(((routine.penalty ?? 0) + (routine.sjPenalty ?? 0)) * 1000) / 1000;
}
