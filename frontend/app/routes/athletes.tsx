import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";

import type { Route } from "./+types/athletes";
import { athleteSearchQuery } from "~/api/client";
import { Country } from "~/components/results/parts";
import { athleteName } from "~/lib/format";
import { DISCIPLINE_LABELS } from "~/lib/labels";

/** Shorter queries match too much of every name to be useful. */
const MIN_QUERY = 2;

export function meta(): Route.MetaDescriptors {
  return [{ title: "Athletes: Gym Meet" }];
}

export default function Athletes() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [text, setText] = useState(searchParams.get("q") ?? "");
  const q = (searchParams.get("q") ?? "").trim();

  // The address follows the box once typing pauses, so a search can be shared or bookmarked
  useEffect(() => {
    const timer = setTimeout(() => setSearchParams(text.trim() ? { q: text.trim() } : {}, { replace: true }), 250);
    return () => clearTimeout(timer);
  }, [text, setSearchParams]);

  const search = useQuery({
    ...athleteSearchQuery(q),
    enabled: q.length >= MIN_QUERY,
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <h1 className="text-2xl font-semibold">Athletes</h1>
      <label className="mt-4 block">
        <span className="sr-only">Search by name</span>
        <input
          type="search"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Search by name"
          autoFocus
          className="w-full rounded-lg border border-gray-300 bg-transparent px-3 py-2 dark:border-gray-700"
        />
      </label>
      {q.length < MIN_QUERY ? (
        <p className="mt-4 text-sm text-gray-500">Type at least {MIN_QUERY} letters of a name.</p>
      ) : search.isError ? (
        <p className="mt-4 text-sm text-gray-500">The search couldn't be run. Try again in a moment.</p>
      ) : search.data === undefined ? (
        <p className="mt-4 text-sm text-gray-500">Searching…</p>
      ) : search.data.length === 0 ? (
        <p className="mt-4 text-sm text-gray-500">No athletes match “{q}”.</p>
      ) : (
        <ul className="mt-4 divide-y divide-gray-200 rounded-lg border border-gray-200 dark:divide-gray-800 dark:border-gray-800">
          {search.data.map((athlete) => (
            <li key={athlete.id}>
              <Link
                to={`/athletes/${athlete.id}`}
                className="flex items-baseline justify-between gap-4 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-900"
              >
                <span>
                  <span className="font-medium">{athleteName(athlete)}</span>
                  {athlete.noc && (
                    <span className="block text-xs text-gray-500">
                      <Country noc={athlete.noc} />
                    </span>
                  )}
                </span>
                <span className="shrink-0 text-sm text-gray-500">{DISCIPLINE_LABELS[athlete.discipline]}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
