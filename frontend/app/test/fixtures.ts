import type { CompetitionSummary, DivisionCompetitions, EventDetail, RankingSummary } from "~/api/types";

/** Builders for API responses in tests, with only the fields a test is about given. */

let id = 0;

export function competition(
  fields: Partial<CompetitionSummary> & Pick<CompetitionSummary, "slug" | "name">,
): CompetitionSummary {
  return {
    id: ++id,
    shortName: fields.name,
    discipline: "WAG",
    ageCategory: "SR",
    type: "C1",
    apparatus: null,
    round: null,
    part: null,
    purposes: { team: null, allAround: null, apparatus: null },
    date: "2026-10-18",
    endDate: null,
    ...fields,
  };
}

export function division(
  competitions: CompetitionSummary[],
  rankings: RankingSummary[] = [],
  fields: Partial<DivisionCompetitions> = {},
): DivisionCompetitions {
  return { discipline: "WAG", ageCategory: "SR", rankings, competitions, ...fields };
}

export function event(divisions: DivisionCompetitions[], fields: Partial<EventDetail> = {}): EventDetail {
  return {
    slug: "2026-world-championships",
    title: "2026 World Championships",
    startDate: "2026-10-17",
    endDate: "2026-10-25",
    city: "Rotterdam",
    countryCode: "NED",
    venue: null,
    level: "WORLD_CHAMPIONSHIPS",
    figEventNumber: null,
    apparatusSuppliers: null,
    divisions,
    ...fields,
  };
}
