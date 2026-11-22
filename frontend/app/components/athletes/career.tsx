import type { ReactNode } from "react";
import { Link } from "react-router";

import type { Apparatus, ApparatusScore, AthleteDetail, AthleteEntry, EntrySession, Routine } from "~/api/types";
import { formatDateRange, formatScore, formatValue } from "~/lib/format";
import { resultsPath, sessionLabel, sessionPath, shortSessionLabel, VAULT_FINAL_QUALIFYING } from "~/lib/labels";
import { Abbreviation, ApparatusCode } from "../Abbreviation";
import { ApparatusIcon } from "../ApparatusIcon";
import { Country, difficultyText, QualificationBadge, RoutineScore } from "../results/parts";

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
      code: <Abbreviation short="AA" label="All-around" spoken />,
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

/** One meet: where and when, who they competed for, and their results in each session. */
export function EntryResults({ entry }: { entry: AthleteEntry }) {
  return (
    <section className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">
      <h3 className="font-semibold">
        <Link to={`/events/${entry.event.slug}`} className="hover:underline">
          {entry.event.title}
        </Link>
      </h3>
      <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
        {formatDateRange(entry.event.startDate, entry.event.endDate)} · <Country noc={entry.noc} club={entry.club} />
      </p>
      <div className="mt-3 max-w-xl space-y-4">
        {entry.sessions.map((entrySession) => (
          <SessionResult key={entrySession.session.id} eventSlug={entry.event.slug} entrySession={entrySession} />
        ))}
      </div>
    </section>
  );
}

function SessionResult({ eventSlug, entrySession }: { eventSlug: string; entrySession: EntrySession }) {
  const { session, allAround, scores, apparatusStandings } = entrySession;
  return (
    <div>
      <h4 className="flex flex-wrap items-baseline justify-between gap-x-4 text-sm">
        <Link to={sessionPath(eventSlug, session)} className="font-medium hover:underline">
          {sessionLabel(session)}
        </Link>
        {allAround && (
          <span className="text-gray-600 tabular-nums dark:text-gray-400">
            All-around <span className="font-semibold text-inherit">{formatScore(allAround.total)}</span>
            {allAround.rank != null && <> · #{allAround.rank}</>}{" "}
            <QualificationBadge result={allAround.qualification} />
          </span>
        )}
      </h4>
      {scores.length > 0 && <ScoresTable session={sessionLabel(session)} scores={scores} />}
      {apparatusStandings.length > 0 && (
        <table className="mt-1 w-full border-collapse text-sm tabular-nums">
          <caption className="sr-only">{sessionLabel(session)}: combined apparatus standings</caption>
          <tbody>
            {apparatusStandings.map((standing) => (
              <tr key={standing.apparatus} className="border-b border-gray-100 dark:border-gray-900">
                <th scope="row" className="py-1.5 pr-2 text-left font-normal">
                  <ApparatusCode apparatus={standing.apparatus} />
                </th>
                <td className="px-2 py-1.5 text-right font-semibold">{formatScore(standing.total)}</td>
                <td className="w-12 py-1.5 pl-2 text-right text-gray-500">
                  {standing.rank != null && `#${standing.rank}`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

/** Each apparatus's routine, or both vaults and the result they're ranked on. */
function ScoresTable({ session, scores }: { session: string; scores: ApparatusScore[] }) {
  return (
    <table className="mt-1 w-full border-collapse text-sm tabular-nums">
      <caption className="sr-only">{session}: scores</caption>
      <thead>
        <tr className="text-xs text-gray-500">
          <th scope="col" className="py-1 pr-2 text-left font-medium">
            <span className="sr-only">Apparatus</span>
          </th>
          <th scope="col" className="px-2 py-1 text-right font-medium">
            <abbr title="Difficulty" className="no-underline">
              D
            </abbr>
          </th>
          <th scope="col" className="px-2 py-1 text-right font-medium">
            <abbr title="Execution" className="no-underline">
              E
            </abbr>
          </th>
          <th scope="col" className="px-2 py-1 text-right font-medium">
            Score
          </th>
          <th scope="col" className="w-12 py-1 pl-2 text-right font-medium">
            <abbr title="Rank" className="no-underline">
              #
            </abbr>
          </th>
        </tr>
      </thead>
      <tbody>
        {scores.flatMap((score) => {
          const routines: [number | undefined, Routine][] = score.secondRoutine
            ? [
                [1, score.routine],
                [2, score.secondRoutine],
              ]
            : [[undefined, score.routine]];
          const rows = routines.map(([number, routine], index) => (
            <tr key={`${score.apparatus}${number ?? ""}`} className="border-t border-gray-100 dark:border-gray-900">
              <th scope="row" className="py-1.5 pr-2 text-left font-normal">
                <ApparatusCode apparatus={score.apparatus} routine={number} />
              </th>
              <td className="px-2 py-1.5 text-right">{formatValue(routine.difficulty)}</td>
              <td className="px-2 py-1.5 text-right">{formatScore(routine.execution)}</td>
              <td className="px-2 py-1.5 text-right font-semibold">
                <RoutineScore routine={routine} />
              </td>
              <td className="py-1.5 pl-2 text-right text-gray-500">
                {index === 0 && <RankAndQualification score={score} />}
              </td>
            </tr>
          ));
          if (score.secondRoutine) {
            rows.push(
              <tr key={`${score.apparatus}-total`} className="text-gray-600 dark:text-gray-400">
                <th scope="row" className="py-1 pr-2 text-left text-xs font-normal">
                  Vault result
                </th>
                <td colSpan={3} className="px-2 py-1 text-right font-semibold">
                  {formatScore(score.total)}
                </td>
                <td />
              </tr>,
            );
          }
          return rows;
        })}
      </tbody>
    </table>
  );
}

function RankAndQualification({ score }: { score: ApparatusScore }) {
  return (
    <span className="inline-flex items-center justify-end gap-1.5 whitespace-nowrap">
      {score.rank != null && `#${score.rank}`}
      <QualificationBadge result={score.qualification} />
    </span>
  );
}
