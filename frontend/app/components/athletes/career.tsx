import { Link } from "react-router";

import type { ApparatusScore, AthleteDetail, AthleteEntry, EntrySession, Routine } from "~/api/types";
import { formatDateRange, formatScore, formatValue } from "~/lib/format";
import { APPARATUS_LABELS, sessionLabel, sessionPath } from "~/lib/labels";
import { Country, QualificationBadge, RoutineScore } from "../results/parts";

const cell = "px-2 py-2 align-top";

/** The athlete's best routine on each apparatus and best all-around, each linking to where it was scored. */
export function PersonalBests({ athlete }: { athlete: AthleteDetail }) {
  const { personalBests, allAroundBest } = athlete;
  if (personalBests.length === 0 && !allAroundBest) {
    return null;
  }
  return (
    <table className="w-full border-collapse text-sm tabular-nums">
      <caption className="sr-only">Personal bests</caption>
      <thead>
        <tr className="border-b border-gray-300 text-left text-xs text-gray-500 dark:border-gray-700">
          <th scope="col" className="px-2 py-2 font-medium">
            Apparatus
          </th>
          <th scope="col" className="px-2 py-2 text-right font-medium">
            <abbr title="Difficulty" className="no-underline">
              D
            </abbr>
          </th>
          <th scope="col" className="px-2 py-2 text-right font-medium">
            <abbr title="Execution" className="no-underline">
              E
            </abbr>
          </th>
          <th scope="col" className="px-2 py-2 text-right font-medium">
            Score
          </th>
          <th scope="col" className="hidden px-2 py-2 font-medium sm:table-cell">
            Where
          </th>
        </tr>
      </thead>
      <tbody>
        {personalBests.map((best) => (
          <tr key={best.apparatus} className="border-b border-gray-200 dark:border-gray-800">
            <th scope="row" className={`${cell} text-left font-normal`}>
              {APPARATUS_LABELS[best.apparatus]}
              <Where event={best.event} session={best.session} className="sm:hidden" />
            </th>
            <td className={`${cell} text-right`}>{formatValue(best.difficulty)}</td>
            <td className={`${cell} text-right`}>{formatScore(best.execution)}</td>
            <td className={`${cell} text-right font-semibold`}>{formatScore(best.score)}</td>
            <td className={`${cell} hidden sm:table-cell`}>
              <Where event={best.event} session={best.session} />
            </td>
          </tr>
        ))}
        {allAroundBest && (
          <tr className="border-b border-gray-200 dark:border-gray-800">
            <th scope="row" className={`${cell} text-left font-normal`}>
              All-around
              <Where event={allAroundBest.event} session={allAroundBest.session} className="sm:hidden" />
            </th>
            <td className={cell} />
            <td className={cell} />
            <td className={`${cell} text-right font-semibold`}>{formatScore(allAroundBest.total)}</td>
            <td className={`${cell} hidden sm:table-cell`}>
              <Where event={allAroundBest.event} session={allAroundBest.session} />
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

function Where({
  event,
  session,
  className = "",
}: {
  event: AthleteEntry["event"];
  session: EntrySession["session"];
  className?: string;
}) {
  return (
    <Link
      to={sessionPath(event.slug, session)}
      className={`block text-xs text-gray-500 hover:underline sm:text-sm sm:text-inherit ${className}`}
    >
      {event.title}, {sessionLabel(session)}
    </Link>
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
                  {APPARATUS_LABELS[standing.apparatus]}
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
          const routines: [string, Routine][] = score.secondRoutine
            ? [
                [`${APPARATUS_LABELS[score.apparatus]} 1`, score.routine],
                [`${APPARATUS_LABELS[score.apparatus]} 2`, score.secondRoutine],
              ]
            : [[APPARATUS_LABELS[score.apparatus], score.routine]];
          const rows = routines.map(([label, routine], index) => (
            <tr key={label} className="border-t border-gray-100 dark:border-gray-900">
              <th scope="row" className="py-1.5 pr-2 text-left font-normal">
                {label}
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
