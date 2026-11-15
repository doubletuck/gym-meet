import { useSuspenseQuery } from "@tanstack/react-query";
import { data, Link, useSearchParams } from "react-router";

import type { Route } from "./+types/session";
import { eventQuery, queryClient, sessionResultsQuery } from "~/api/client";
import type { Apparatus, SessionResults } from "~/api/types";
import { AllAroundTable, ScoreTable, StandingsTable, TeamTable } from "~/components/results/tables";
import { formatSessionDate } from "~/lib/format";
import { APPARATUS_SHORT_LABELS, divisionLabel, sessionLabel } from "~/lib/labels";

/** Finds the session the address names, then loads its results. */
export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const event = await queryClient.ensureQueryData(eventQuery(params.eventSlug));
  const session = event.divisions
    .find(
      (division) =>
        division.discipline.toLowerCase() === params.discipline &&
        division.ageCategory.toLowerCase() === params.ageCategory,
    )
    ?.sessions.find((candidate) => candidate.slug === params.sessionSlug);
  if (!session) {
    throw data(null, { status: 404 });
  }
  await queryClient.ensureQueryData(sessionResultsQuery(session.id));
  return { sessionId: session.id, eventTitle: event.title, title: sessionLabel(session) };
}

export function meta({ loaderData }: Route.MetaArgs): Route.MetaDescriptors {
  return [{ title: `${loaderData.title}, ${loaderData.eventTitle}: Gym Meet` }];
}

type View = { key: string; label: string };

/** The views a session's results offer, in the order a results book prints them. */
function viewsOf(results: SessionResults): View[] {
  return [
    ...(results.teams.length ? [{ key: "teams", label: "Teams" }] : []),
    ...(results.allAround.length ? [{ key: "all-around", label: "All-around" }] : []),
    ...results.apparatus.map(({ apparatus }) => ({ key: apparatus, label: APPARATUS_SHORT_LABELS[apparatus] })),
    ...results.apparatusStandings.map(({ apparatus }) => ({
      key: `combined-${apparatus}`,
      label: APPARATUS_SHORT_LABELS[apparatus],
    })),
  ];
}

export default function Session({ loaderData, params }: Route.ComponentProps) {
  const { data: results } = useSuspenseQuery(sessionResultsQuery(loaderData.sessionId));
  const [searchParams] = useSearchParams();
  const { session } = results;

  const views = viewsOf(results);
  const current = views.find((view) => view.key === searchParams.get("view")) ?? views[0];
  const qualification = session.round === "QUAL";
  const teamScoring = results.teams.length > 0;
  const apparatusOrder: Apparatus[] = results.apparatus.map(({ apparatus }) => apparatus);
  const allAroundApparatus: Apparatus[] = apparatusOrder.length
    ? apparatusOrder
    : results.apparatusStandings.map(({ apparatus }) => apparatus);

  return (
    <>
      <nav className="text-sm">
        <Link to={`/events/${params.eventSlug}`} className="text-blue-700 underline dark:text-blue-400">
          {results.event.title}
        </Link>
      </nav>
      <h1 className="mt-2 text-2xl font-semibold">{loaderData.title}</h1>
      <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
        {divisionLabel(session.discipline, session.ageCategory)} · {formatSessionDate(session.date)}
      </p>

      {views.length > 1 && (
        <nav aria-label="Results" className="-mx-4 mt-4 overflow-x-auto px-4">
          <ul className="flex gap-2">
            {views.map((view) => (
              <li key={view.key}>
                <Link
                  to={`?view=${view.key}`}
                  replace
                  preventScrollReset
                  aria-current={view.key === current?.key ? "page" : undefined}
                  className={`block whitespace-nowrap rounded-full px-3 py-1.5 text-sm ${
                    view.key === current?.key
                      ? "bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900"
                      : "bg-gray-100 dark:bg-gray-800"
                  }`}
                >
                  {view.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}

      <div className="mt-4">
        {!current && (
          <p className="text-gray-600 dark:text-gray-400">No results have been published for this session.</p>
        )}
        {current?.key === "teams" && (
          <TeamTable rows={results.teams} apparatus={apparatusOrder} qualification={qualification} />
        )}
        {current?.key === "all-around" && (
          <AllAroundTable rows={results.allAround} apparatus={allAroundApparatus} qualification={qualification} />
        )}
        {results.apparatus
          .filter(({ apparatus }) => apparatus === current?.key)
          .map(({ apparatus, scores }) => (
            <ScoreTable
              key={apparatus}
              apparatus={apparatus}
              scores={scores}
              qualification={qualification}
              teamScoring={teamScoring}
              rankedOnFirstVault={qualification && session.apparatus == null}
            />
          ))}
        {results.apparatusStandings
          .filter(({ apparatus }) => `combined-${apparatus}` === current?.key)
          .map(({ apparatus, rows }) => (
            <StandingsTable key={apparatus} apparatus={apparatus} rows={rows} />
          ))}
      </div>

      <p className="mt-6 text-xs text-gray-500">
        Results as published in the official results of the {results.event.title}. Ranks, ties and totals are shown as
        printed, not recalculated.
      </p>
    </>
  );
}
