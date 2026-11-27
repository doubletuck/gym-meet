import { useSuspenseQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { data, Link, useSearchParams } from "react-router";

import type { Route } from "./+types/competition";
import { competitionResultsQuery, eventQuery, queryClient, rankingResultsQuery } from "~/api/client";
import type { CompetitionResults, RankingResults } from "~/api/types";
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
import { columnKey, isMixed, ranksFirstVault, VAULT_FINAL_QUALIFYING, type ApparatusColumn } from "~/lib/labels";
import { Abbreviation, ApparatusCode, Division } from "~/components/Abbreviation";
import { CompetitionNav, DivisionNav } from "~/components/results/CompetitionNav";

/**
 * Finds the competition the address names, or a ranking with no competition of its own (a mixed
 * team's qualification), then loads its results.
 */
export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const event = await queryClient.ensureQueryData(eventQuery(params.eventSlug));
  const division = event.divisions.find(
    (candidate) =>
      candidate.discipline.toLowerCase() === params.discipline &&
      candidate.ageCategory.toLowerCase() === params.ageCategory,
  );
  const competition = division?.competitions.find((candidate) => candidate.slug === params.competitionSlug);
  if (competition) {
    await queryClient.ensureQueryData(competitionResultsQuery(competition.id));
    return { kind: "competition" as const, id: competition.id, eventTitle: event.title, title: competition.name };
  }
  const ranking = division?.rankings.find((candidate) => candidate.slug === params.competitionSlug);
  if (ranking) {
    await queryClient.ensureQueryData(rankingResultsQuery(ranking.id));
    return { kind: "ranking" as const, id: ranking.id, eventTitle: event.title, title: ranking.name };
  }
  throw data(null, { status: 404 });
}

export function meta({ loaderData }: Route.MetaArgs): Route.MetaDescriptors {
  return [{ title: `${loaderData.title}, ${loaderData.eventTitle}: Gym Meet` }];
}

type View = { key: string; label: ReactNode };

/** An apparatus's view: its code, with the discipline where both are shown (a mixed team's "M FX"). */
function apparatusView(column: ApparatusColumn, mixed: boolean): View {
  return {
    key: columnKey(column, mixed),
    label: <ApparatusCode apparatus={column.apparatus} discipline={mixed ? column.discipline : undefined} />,
  };
}

/**
 * The views a competition's results offer, in the order a results book prints
 * them. A championship qualification's vault is two views: the first vault,
 * which counts for team and all-around, and the two-vault ranking for the
 * vault final.
 */
function viewsOf(results: CompetitionResults, rankedOnFirstVault: boolean, mixed: boolean): View[] {
  return [
    ...(results.teams.length ? [{ key: "teams", label: "Team" }] : []),
    ...(results.allAround.length
      ? [{ key: "all-around", label: <Abbreviation short="AA" label="All-Around" spoken /> }]
      : []),
    ...results.apparatus.flatMap(({ discipline, apparatus, scores }) => [
      apparatusView({ discipline, apparatus }, mixed),
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

export default function Results({ loaderData, params }: Route.ComponentProps) {
  return loaderData.kind === "competition" ? (
    <Competition id={loaderData.id} title={loaderData.title} eventSlug={params.eventSlug} />
  ) : (
    <Ranking id={loaderData.id} title={loaderData.title} eventSlug={params.eventSlug} />
  );
}

/** The view the address names (`?view=`), and the athlete whose rows to highlight (`?athlete=`). */
function useViews(views: View[]) {
  const [searchParams] = useSearchParams();
  const current = views.find((view) => view.key === searchParams.get("view")) ?? views[0];
  // A link from an athlete's page highlights their rows, kept as the views change
  const athleteParam = Number(searchParams.get("athlete"));
  const athleteId = Number.isInteger(athleteParam) && athleteParam > 0 ? athleteParam : undefined;
  return { current, athleteId };
}

function ViewNav({ views, current, athleteId }: { views: View[]; current?: View; athleteId?: number }) {
  const viewPath = (key: string) =>
    `?${new URLSearchParams({ view: key, ...(athleteId != null && { athlete: String(athleteId) }) })}`;
  if (views.length < 2) {
    return null;
  }
  return (
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
  );
}

/**
 * The event, which division and competition these results are, and the way to the event's other
 * results: its divisions, the division's competitions, and a tab's apparatus, rounds or parts.
 */
function Header({
  eventSlug,
  slug,
  title,
  discipline,
  ageCategory,
  date,
  endDate,
  view,
  athleteId,
}: {
  eventSlug: string;
  slug: string;
  title: string;
  discipline: CompetitionResults["competition"]["discipline"];
  ageCategory: CompetitionResults["competition"]["ageCategory"];
  date: string;
  endDate: string | null;
  view: string | null;
  athleteId?: number;
}) {
  const { data: event } = useSuspenseQuery(eventQuery(eventSlug));
  const where = { event, discipline, ageCategory, slug, view };
  return (
    <>
      <nav aria-label="Breadcrumb" className="text-sm">
        <Link to="/" className="text-blue-700 underline dark:text-blue-400">
          Competitions
        </Link>
        <span className="text-gray-500"> / </span>
        <Link to={`/events/${eventSlug}`} className="text-blue-700 underline dark:text-blue-400">
          {event.title}
        </Link>
      </nav>
      <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold">{event.title}</h1>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
            <Division discipline={discipline} ageCategory={ageCategory} /> · {title} ·{" "}
            {formatCompetitionDate(date, endDate)}
          </p>
        </div>
        <DivisionNav {...where} />
      </div>
      <CompetitionNav {...where} athleteId={athleteId} />
    </>
  );
}

function SourceNote({ eventTitle }: { eventTitle: string }) {
  return (
    <p className="mt-6 text-xs text-gray-500">
      Results as published in the official results of the {eventTitle}. Ranks, ties and totals are shown as printed, not
      recalculated.
    </p>
  );
}

/**
 * A ranking with no competition of its own: a mixed team's qualification, its teams and the scores
 * that counted toward them, from the men's and women's Competition I.
 */
function Ranking({ id, title, eventSlug }: { id: number; title: string; eventSlug: string }) {
  const { data: results } = useSuspenseQuery(rankingResultsQuery(id));
  const { ranking } = results;
  const columns = rankingColumns(results);
  const mixed = isMixed(columns);
  const views = [
    ...(results.teams.length ? [{ key: "teams", label: "Team" }] : []),
    ...columns.map((column) => apparatusView(column, mixed)),
  ];
  const { current, athleteId } = useViews(views);
  return (
    <>
      <Header
        eventSlug={eventSlug}
        slug={ranking.slug}
        title={title}
        discipline={ranking.discipline}
        ageCategory={ranking.ageCategory}
        date={ranking.date}
        endDate={ranking.endDate}
        view={current?.key ?? null}
        athleteId={athleteId}
      />
      <ViewNav views={views} current={current} athleteId={athleteId} />
      <div className="mt-4">
        {current?.key === "teams" && (
          <TeamTable rows={results.teams} apparatus={columns} qualification={ranking.purpose === "QUALIFYING"} />
        )}
        {results.apparatus
          .filter((list) => columnKey(list, mixed) === current?.key)
          .map(({ discipline, apparatus, scores }) => (
            <ScoreTable
              key={columnKey({ discipline, apparatus }, mixed)}
              apparatus={apparatus}
              discipline={mixed ? discipline : undefined}
              scores={scores}
              qualification={false}
              athleteId={athleteId}
            />
          ))}
      </div>
      <SourceNote eventTitle={results.event.title} />
    </>
  );
}

function rankingColumns(results: RankingResults): ApparatusColumn[] {
  return results.apparatus.map(({ discipline, apparatus }) => ({ discipline, apparatus }));
}

function Competition({ id, title, eventSlug }: { id: number; title: string; eventSlug: string }) {
  const { data: results } = useSuspenseQuery(competitionResultsQuery(id));
  const { competition } = results;

  // Q columns only where the standings qualify to a later competition, not where they decided a title
  const { purposes } = competition;
  const qualifying = {
    teams: purposes.team === "QUALIFYING",
    allAround: purposes.allAround === "QUALIFYING",
    apparatus: purposes.apparatus === "QUALIFYING",
  };
  const rankedOnFirstVault = ranksFirstVault(competition);
  const columns = standingsApparatus(results);
  const mixed = isMixed(columns);
  const views = viewsOf(results, rankedOnFirstVault, mixed);
  const { current, athleteId } = useViews(views);

  return (
    <>
      <Header
        eventSlug={eventSlug}
        slug={competition.slug}
        title={title}
        discipline={competition.discipline}
        ageCategory={competition.ageCategory}
        date={competition.date}
        endDate={competition.endDate}
        view={current?.key ?? null}
        athleteId={athleteId}
      />
      <ViewNav views={views} current={current} athleteId={athleteId} />

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
            apparatus={columns.map((column) => column.apparatus)}
            qualification={qualifying.allAround}
            athleteId={athleteId}
          />
        )}
        {results.apparatus
          .filter((list) => columnKey(list, mixed) === current?.key)
          .map(({ discipline, apparatus, scores }) =>
            apparatus !== "VT" ? (
              <ScoreTable
                key={columnKey({ discipline, apparatus }, mixed)}
                apparatus={apparatus}
                discipline={mixed ? discipline : undefined}
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

      <SourceNote eventTitle={results.event.title} />
    </>
  );
}
