import { useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import type { Route } from "./+types/events";
import { eventsQuery, queryClient } from "~/api/client";
import { Division } from "~/components/Abbreviation";
import { countryName } from "~/lib/countries";
import { formatDateRange } from "~/lib/format";
import { divisionPath, LEVEL_LABELS } from "~/lib/labels";

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
            <li
              key={event.slug}
              className="relative rounded-lg border border-gray-200 p-4 hover:border-gray-400 dark:border-gray-800 dark:hover:border-gray-600"
            >
              <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{LEVEL_LABELS[event.level]}</p>
              <h2 className="mt-1 font-semibold">
                {/* The whole card opens the event; its division chips, layered over it, open that division's results */}
                <Link to={`/events/${event.slug}`} className="after:absolute after:inset-0 hover:underline">
                  {event.title}
                </Link>
              </h2>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                {formatDateRange(event.startDate, event.endDate)} · {event.city}, {countryName(event.countryCode)}
              </p>
              <ul aria-label="Results" className="relative z-10 mt-2 flex flex-wrap gap-2">
                {event.divisions.map((division) => (
                  <li key={`${division.discipline}-${division.ageCategory}`}>
                    <Link
                      to={`/events/${event.slug}/${divisionPath(division.discipline, division.ageCategory)}`}
                      className="block rounded-full border border-gray-200 bg-gray-100 px-2.5 py-0.5 text-xs hover:border-blue-700 hover:text-blue-700 dark:border-gray-700 dark:bg-gray-800 dark:hover:border-blue-400 dark:hover:text-blue-400"
                    >
                      <Division discipline={division.discipline} ageCategory={division.ageCategory} />
                      <span aria-hidden="true"> ›</span>
                      <span className="sr-only"> results, {event.title}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
