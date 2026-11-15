import type { AgeCategory, Apparatus, Discipline, EventLevel, SessionSummary } from "~/api/types";

export const DISCIPLINE_LABELS: Record<Discipline, string> = {
  MAG: "Men's",
  WAG: "Women's",
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

/** For tabs and narrow column headings. */
export const APPARATUS_SHORT_LABELS: Record<Apparatus, string> = {
  VT: "Vault",
  UB: "Bars",
  BB: "Beam",
  FX: "Floor",
  PH: "Pommel",
  SR: "Rings",
  PB: "P-Bars",
  HB: "High Bar",
};

export const LEVEL_LABELS: Record<EventLevel, string> = {
  OLYMPIC_GAMES: "Olympic Games",
  WORLD_CHAMPIONSHIPS: "World Championships",
  YOUTH_OLYMPIC_GAMES: "Youth Olympic Games",
  CONTINENTAL_GAMES: "Continental Games",
  CONTINENTAL_CHAMPIONSHIPS: "Continental Championships",
  WORLD_CUP: "World Cup",
  WORLD_CHALLENGE_CUP: "World Challenge Cup",
  INTERNATIONAL_TOURNAMENTS: "International Tournament",
  NATIONAL_CHAMPIONSHIPS: "National Championships",
  DOMESTIC_COMPETITION: "Domestic Competition",
  UNKNOWN: "Competition",
};

/** "Women's Senior" */
export function divisionLabel(discipline: Discipline, ageCategory: AgeCategory): string {
  return `${DISCIPLINE_LABELS[discipline]} ${AGE_CATEGORY_LABELS[ageCategory]}`;
}

/** The session's name as a results book heads it: "Qualification", "Balance Beam Final", "All-Around Final, Part 1". */
export function sessionLabel(session: Pick<SessionSummary, "round" | "apparatus" | "part">): string {
  const apparatus = session.apparatus ? APPARATUS_LABELS[session.apparatus] : "";
  const round = {
    QUAL: apparatus ? `${apparatus} Qualification` : "Qualification",
    TEAM: "Team Final",
    AA: "All-Around Final",
    EVENT: `${apparatus} Final`,
  }[session.round];
  return session.part != null ? `${round}, Part ${session.part}` : round;
}

/** The address segment for a discipline and age category: "wag/sr". */
export function divisionPath(discipline: Discipline, ageCategory: AgeCategory): string {
  return `${discipline.toLowerCase()}/${ageCategory.toLowerCase()}`;
}
