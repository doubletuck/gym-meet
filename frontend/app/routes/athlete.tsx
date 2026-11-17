import { useSuspenseQuery } from "@tanstack/react-query";
import { data } from "react-router";

import type { Route } from "./+types/athlete";
import { athleteQuery, queryClient } from "~/api/client";
import { EntryResults, PersonalBests } from "~/components/athletes/career";
import { Country } from "~/components/results/parts";
import { athleteName } from "~/lib/format";
import { DISCIPLINE_LABELS } from "~/lib/labels";

function athleteId(params: Route.ClientLoaderArgs["params"]): number {
  const id = Number(params.athleteId);
  if (!Number.isInteger(id)) {
    throw data(null, { status: 404 });
  }
  return id;
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const athlete = await queryClient.ensureQueryData(athleteQuery(athleteId(params)));
  return { id: athlete.id, name: athleteName(athlete) };
}

export function meta({ loaderData }: Route.MetaArgs): Route.MetaDescriptors {
  return [{ title: `${loaderData.name}: Gym Meet` }];
}

export default function Athlete({ loaderData }: Route.ComponentProps) {
  const { data: athlete } = useSuspenseQuery(athleteQuery(loaderData.id));
  const latest = athlete.entries[0];

  return (
    <>
      <h1 className="text-2xl font-semibold">{athleteName(athlete)}</h1>
      <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
        {latest && (
          <>
            <Country noc={latest.noc} /> ·{" "}
          </>
        )}
        {DISCIPLINE_LABELS[athlete.discipline]}
        {athlete.birthYear != null && <> · Born {athlete.birthYear}</>}
      </p>
      {athlete.otherNames.length > 0 && (
        <p className="mt-1 text-sm text-gray-500">Also printed as {athlete.otherNames.join(", ")}</p>
      )}

      {(athlete.personalBests.length > 0 || athlete.allAroundBest) && (
        <section className="mt-6">
          <h2 className="font-semibold">Personal bests</h2>
          <div className="mt-2">
            <PersonalBests athlete={athlete} />
          </div>
        </section>
      )}

      <section className="mt-6">
        <h2 className="font-semibold">Results</h2>
        <div className="mt-2 space-y-4">
          {athlete.entries.map((entry) => (
            <EntryResults key={entry.event.slug} entry={entry} />
          ))}
        </div>
      </section>
    </>
  );
}
