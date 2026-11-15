import { useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import type { Route } from "./+types/events";
import { eventsQuery, queryClient } from "~/api/client";
import { countryName } from "~/lib/countries";
import { formatDateRange } from "~/lib/format";
import { divisionLabel, LEVEL_LABELS } from "~/lib/labels";

export function meta(): Route.MetaDescriptors {
  return [
    { title: "Gym Meet: elite gymnastics results" },
    { name: "description", content: "Results and scores from elite artistic gymnastics competitions." },
  ];
}

export async function clientLoader() {
  return queryClient.ensureQueryData(eventsQuery());
}

export default function Events() {
  const { data: events } = useSuspenseQuery(eventsQuery());

  return (
    <>
      <h1 className="text-2xl font-semibold">Competitions</h1>
      {events.length === 0 ? (
        <p className="mt-4 text-gray-600 dark:text-gray-400">No results have been published yet.</p>
      ) : (
        <ul className="mt-4 space-y-3">
          {events.map((event) => (
            <li key={event.slug}>
              <Link
                to={`/events/${event.slug}`}
                className="block rounded-lg border border-gray-200 p-4 hover:border-gray-400 dark:border-gray-800 dark:hover:border-gray-600"
              >
                <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{LEVEL_LABELS[event.level]}</p>
                <h2 className="mt-1 font-semibold">{event.title}</h2>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                  {formatDateRange(event.startDate, event.endDate)} · {event.city}, {countryName(event.countryCode)}
                </p>
                <p className="mt-2 flex flex-wrap gap-2">
                  {event.divisions.map((division) => (
                    <span
                      key={`${division.discipline}-${division.ageCategory}`}
                      className="rounded-full bg-gray-100 px-2 py-0.5 text-xs dark:bg-gray-800"
                    >
                      {divisionLabel(division.discipline, division.ageCategory)}
                    </span>
                  ))}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
