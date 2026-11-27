import { data, redirect } from "react-router";

import type { Route } from "./+types/division";
import { eventQuery, queryClient } from "~/api/client";
import { competitionTabs } from "~/lib/competitionTabs";

/** A division's results ("/events/2026-world-championships/wag/sr"), opened on its first competition. */
export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const event = await queryClient.ensureQueryData(eventQuery(params.eventSlug));
  const division = event.divisions.find(
    (candidate) =>
      candidate.discipline.toLowerCase() === params.discipline &&
      candidate.ageCategory.toLowerCase() === params.ageCategory,
  );
  const first = division && competitionTabs(division)[0]?.members[0];
  if (!first) {
    throw data(null, { status: 404 });
  }
  return redirect(`/events/${params.eventSlug}/${params.discipline}/${params.ageCategory}/${first.slug}`);
}

export default function Division() {
  return null;
}
