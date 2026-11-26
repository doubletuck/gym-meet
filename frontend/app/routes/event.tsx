import { useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import type { Route } from "./+types/event";
import { eventQuery, queryClient } from "~/api/client";
import { Division } from "~/components/Abbreviation";
import { countryName } from "~/lib/countries";
import { formatDateRange, formatCompetitionDate } from "~/lib/format";
import { competitionPath, LEVEL_LABELS } from "~/lib/labels";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  return queryClient.ensureQueryData(eventQuery(params.eventSlug));
}

export function meta({ loaderData }: Route.MetaArgs): Route.MetaDescriptors {
  return [{ title: `${loaderData.title}: Gym Meet` }];
}

export default function Event({ params }: Route.ComponentProps) {
  const { data: event } = useSuspenseQuery(eventQuery(params.eventSlug));

  return (
    <>
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{LEVEL_LABELS[event.level]}</p>
      <h1 className="mt-1 text-2xl font-semibold">{event.title}</h1>
      <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
        {formatDateRange(event.startDate, event.endDate)} · {event.venue ? `${event.venue}, ` : ""}
        {event.city}, {countryName(event.countryCode)}
      </p>

      <div className="mt-6 grid gap-6 sm:grid-cols-2">
        {event.divisions.map((division) => (
          <section key={`${division.discipline}-${division.ageCategory}`}>
            <h2 className="font-semibold">
              <Division discipline={division.discipline} ageCategory={division.ageCategory} />
            </h2>
            <ul className="mt-2 divide-y divide-gray-200 rounded-lg border border-gray-200 dark:divide-gray-800 dark:border-gray-800">
              {/* A ranking with no competition of its own (a mixed team's qualification) comes first */}
              {[...division.rankings, ...division.competitions].map((competition) => (
                <li key={competition.slug}>
                  <Link
                    to={competitionPath(event.slug, competition)}
                    className="flex items-baseline justify-between gap-4 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-900"
                  >
                    <span>{competition.name}</span>
                    <span className="shrink-0 text-sm text-gray-500">
                      {formatCompetitionDate(competition.date, competition.endDate)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </>
  );
}
