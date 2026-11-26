import { useSuspenseQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { data, Link, useSearchParams } from "react-router";

import type { Route } from "./+types/competition";
import { eventQuery, queryClient, competitionResultsQuery } from "~/api/client";
import type { CompetitionResults } from "~/api/types";
import {
  AllAroundTable,
  ScoreTable,
  StandingsTable,
  TeamTable,
  VaultTable,
  firstVaults,
  standingsApparatus,
  vaultFinalQualifying,
} from "~/components/results/tables";
import { formatCompetitionDate } from "~/lib/format";
import { ranksFirstVault, VAULT_FINAL_QUALIFYING } from "~/lib/labels";
import { Abbreviation, ApparatusCode, Division } from "~/components/Abbreviation";

/** Finds the competition the address names, then loads its results. */
export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const event = await queryClient.ensureQueryData(eventQuery(params.eventSlug));
  const competition = event.divisions
    .find(
      (division) =>
        division.discipline.toLowerCase() === params.discipline &&
        division.ageCategory.toLowerCase() === params.ageCategory,
    )
    ?.competitions.find((candidate) => candidate.slug === params.competitionSlug);
  if (!competition) {
    throw data(null, { status: 404 });
  }
  await queryClient.ensureQueryData(competitionResultsQuery(competition.id));
  return { competitionId: competition.id, eventTitle: event.title, title: competition.name };
}

export function meta({ loaderData }: Route.MetaArgs): Route.MetaDescriptors {
  return [{ title: `${loaderData.title}, ${loaderData.eventTitle}: Gym Meet` }];
}

type View = { key: string; label: ReactNode };

/**
 * The views a competition's results offer, in the order a results book prints
 * them. A championship qualification's vault is two views: the first vault,
 * which counts for team and all-around, and the two-vault ranking for the
 * vault final.
 */
function viewsOf(results: CompetitionResults, rankedOnFirstVault: boolean): View[] {
  return [
    ...(results.teams.length ? [{ key: "teams", label: "Team" }] : []),
    ...(results.allAround.length
      ? [{ key: "all-around", label: <Abbreviation short="AA" label="All-Around" spoken /> }]
      : []),
    ...results.apparatus.flatMap(({ apparatus, scores }) => [
      { key: apparatus, label: <ApparatusCode apparatus={apparatus} /> },
      ...(apparatus === "VT" && rankedOnFirstVault && scores.some((row) => row.secondRoutine)
        ? [
            {
              key: VAULT_FINAL_QUALIFYING,
              label: (
                <>
                  <ApparatusCode apparatus="VT" /> Final Qual
                </>
              ),
            },
          ]
        : []),
    ]),
    ...results.apparatusStandings.map(({ apparatus }) => ({
      key: `combined-${apparatus}`,
      label: <ApparatusCode apparatus={apparatus} />,
    })),
  ];
}

export default function Competition({ loaderData, params }: Route.ComponentProps) {
  const { data: results } = useSuspenseQuery(competitionResultsQuery(loaderData.competitionId));
  const [searchParams] = useSearchParams();
  const { competition } = results;

  // Q columns only where the standings qualify to a later competition, not where they decided a title
  const { purposes } = competition;
  const qualifying = {
    teams: purposes.team === "QUALIFYING",
    allAround: purposes.allAround === "QUALIFYING",
    apparatus: purposes.apparatus === "QUALIFYING",
  };
  const rankedOnFirstVault = ranksFirstVault(competition);
  const views = viewsOf(results, rankedOnFirstVault);
  const current = views.find((view) => view.key === searchParams.get("view")) ?? views[0];
  // A link from an athlete's page highlights their rows, kept as the views change
  const athleteParam = Number(searchParams.get("athlete"));
  const athleteId = Number.isInteger(athleteParam) && athleteParam > 0 ? athleteParam : undefined;
  const viewPath = (key: string) =>
    `?${new URLSearchParams({ view: key, ...(athleteId != null && { athlete: String(athleteId) }) })}`;
  const columns = standingsApparatus(results);

  return (
    <>
      <nav className="text-sm">
        <Link to={`/events/${params.eventSlug}`} className="text-blue-700 underline dark:text-blue-400">
          {results.event.title}
        </Link>
      </nav>
      <h1 className="mt-2 text-2xl font-semibold">{loaderData.title}</h1>
      <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
        <Division discipline={competition.discipline} ageCategory={competition.ageCategory} /> ·{" "}
        {formatCompetitionDate(competition.date, competition.endDate)}
      </p>

      {views.length > 1 && (
        <nav aria-label="Results" className="mt-4">
          <ul className="flex flex-wrap gap-2">
            {views.map((view) => (
              <li key={view.key}>
                <Link
                  to={viewPath(view.key)}
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
          <p className="text-gray-600 dark:text-gray-400">No results have been published for this competition.</p>
        )}
        {current?.key === "teams" && (
          <TeamTable rows={results.teams} apparatus={columns} qualification={qualifying.teams} />
        )}
        {current?.key === "all-around" && (
          <AllAroundTable
            rows={results.allAround}
            apparatus={columns}
            qualification={qualifying.allAround}
            athleteId={athleteId}
          />
        )}
        {results.apparatus
          .filter(({ apparatus }) => apparatus === current?.key)
          .map(({ apparatus, scores }) =>
            apparatus !== "VT" ? (
              <ScoreTable
                key={apparatus}
                apparatus={apparatus}
                scores={scores}
                qualification={qualifying.apparatus}
                athleteId={athleteId}
              />
            ) : rankedOnFirstVault ? (
              // The vault final's qualifiers are marked in its own view
              <ScoreTable
                key={apparatus}
                apparatus={apparatus}
                scores={firstVaults(scores)}
                qualification={false}
                athleteId={athleteId}
              />
            ) : (
              <VaultTable key={apparatus} scores={scores} qualification={qualifying.apparatus} athleteId={athleteId} />
            ),
          )}
        {current?.key === VAULT_FINAL_QUALIFYING &&
          results.apparatus
            .filter(({ apparatus }) => apparatus === "VT")
            .map(({ scores }) => (
              <VaultTable
                key={VAULT_FINAL_QUALIFYING}
                scores={vaultFinalQualifying(scores)}
                qualification
                caption="Vault final qualification"
                athleteId={athleteId}
              />
            ))}
        {results.apparatusStandings
          .filter(({ apparatus }) => `combined-${apparatus}` === current?.key)
          .map(({ apparatus, rows }) => (
            <StandingsTable key={apparatus} apparatus={apparatus} rows={rows} athleteId={athleteId} />
          ))}
      </div>

      <p className="mt-6 text-xs text-gray-500">
        Results as published in the official results of the {results.event.title}. Ranks, ties and totals are shown as
        printed, not recalculated.
      </p>
    </>
  );
}
