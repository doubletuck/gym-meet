import type { AgeCategory, Apparatus, CompetitionSummary, Discipline, EventLevel, RankStatus } from "~/api/types";

export const DISCIPLINE_LABELS: Record<Discipline, string> = {
  MAG: "Men's Artistic Gymnastics",
  WAG: "Women's Artistic Gymnastics",
  MIX: "Mixed Artistic Gymnastics",
};

export const AGE_CATEGORY_LABELS: Record<AgeCategory, string> = {
  SR: "Senior",
  JR: "Junior",
  JR16: "Junior 16",
  JR17: "Junior 17",
};

export const APPARATUS_LABELS: Record<Apparatus, string> = {
  VT: "Vault",
  UB: "Uneven Bars",
  BB: "Balance Beam",
  FX: "Floor Exercise",
  PH: "Pommel Horse",
  SR: "Still Rings",
  PB: "Parallel Bars",
  HB: "Horizontal Bar",
};

/** "Men's", "Women's": a mixed team's apparatus by discipline. */
export const DISCIPLINE_OWNER: Record<Discipline, string> = { MAG: "Men's", WAG: "Women's", MIX: "Mixed" };

/** An apparatus as a results column, with its discipline: a mixed competition has both floors. */
export type ApparatusColumn = { discipline: Discipline; apparatus: Apparatus };

/**
 * A results view's key for an apparatus: its code ("UB"), or where both disciplines are shown (a mixed
 * team) the discipline too ("MAG-FX").
 */
export function columnKey(column: ApparatusColumn, mixed: boolean): string {
  return mixed ? `${column.discipline}-${column.apparatus}` : column.apparatus;
}

/** Whether the columns span both disciplines. */
export function isMixed(columns: ApparatusColumn[]): boolean {
  return new Set(columns.map((column) => column.discipline)).size > 1;
}

/** Each discipline's apparatus in Olympic order, the order results are printed in. */
export const APPARATUS_ORDER: Record<Discipline, Apparatus[]> = {
  MAG: ["FX", "PH", "SR", "VT", "PB", "HB"],
  WAG: ["VT", "UB", "BB", "FX"],
  // A mixed team's apparatus belong to both disciplines (men's and women's floor): see ApparatusColumn
  MIX: [],
};

export const LEVEL_LABELS: Record<EventLevel, string> = {
  OLYMPIC_GAMES: "Olympic Games",
  WORLD_CHAMPIONSHIPS: "World Championships",
  YOUTH_OLYMPIC_GAMES: "Youth Olympic Games",
  CONTINENTAL_GAMES: "Continental Games",
  CONTINENTAL_CHAMPIONSHIPS: "Continental Championships",
  REGIONAL_GAMES: "Regional Games",
  REGIONAL_COMPETITION: "Regional Competition",
  WORLD_CUP: "World Cup",
  WORLD_CHALLENGE_CUP: "World Challenge Cup",
  INTERNATIONAL_TOURNAMENTS: "International Tournament",
  NATIONAL_CHAMPIONSHIPS: "National Championships",
  DOMESTIC_COMPETITION: "Domestic Competition",
  UNKNOWN: "Competition",
};

/**
 * Why a result has no rank, as briefly as the rank cell can put it: a short
 * code and what it means.
 */
export const RANK_STATUS_LABELS: Record<Exclude<RankStatus, "RANKED">, [short: string, label: string]> = {
  HORS_CONCOURS: ["HC", "Hors concours: competed outside the competition"],
  NOC_LIMIT: ["NR", "Not ranked: over the limit per country"],
  INCOMPLETE: ["INC", "Incomplete: didn't compete every apparatus"],
  DID_NOT_FINISH: ["DNF", "Did not finish"],
  UNPLACED: ["–", "Unplaced: no place published"],
};

/** The address segment for a discipline and age category: "wag/sr". */
export function divisionPath(discipline: Discipline, ageCategory: AgeCategory): string {
  return `${discipline.toLowerCase()}/${ageCategory.toLowerCase()}`;
}

/** A competition's results page: "/events/2026-world-championships/wag/sr/beam-final". */
export function competitionPath(
  eventSlug: string,
  competition: Pick<CompetitionSummary, "discipline" | "ageCategory" | "slug">,
): string {
  return `/events/${eventSlug}/${divisionPath(competition.discipline, competition.ageCategory)}/${competition.slug}`;
}

/** The view of a championship qualification's two-vault ranking for the vault final. */
export const VAULT_FINAL_QUALIFYING = "VT-final";

/**
 * Whether the competition ranks vault on the first vault, the one counting for
 * team and all-around: a championship's Competition I that qualifies to the
 * apparatus finals, whose vault final is decided on two vaults. Elsewhere vault
 * is ranked on its result.
 */
export function ranksFirstVault(competition: Pick<CompetitionSummary, "type" | "apparatus" | "purposes">): boolean {
  return competition.type === "C1" && competition.apparatus == null && competition.purposes.apparatus === "QUALIFYING";
}

/**
 * A competition's results opened at a view, with an athlete's rows highlighted:
 * "/events/2026-world-championships/wag/sr/qualification?view=UB&athlete=12".
 */
export function resultsPath(
  eventSlug: string,
  competition: Pick<CompetitionSummary, "discipline" | "ageCategory" | "slug">,
  view: string,
  athleteId: number,
): string {
  return `${competitionPath(eventSlug, competition)}?${new URLSearchParams({ view, athlete: String(athleteId) })}`;
}
